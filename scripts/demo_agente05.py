"""
Demo de verificación — Agente 05: Navegador de Ensayos.

Muestra entrada → salida del agente sobre el caso base de la tesis (neuropatía
axonal sensitivomotora, paciente masculino de 42 años):

    ENTRADA   hipótesis candidatas, términos ya saneados, demografía detectada
    SALIDA    ensayos con compatibilidad, estado de reclutamiento y sede,
              excluidos por edad/sexo, enfermedades raras de Orphanet,
              estado de cada API y latencia total

El agente es híbrido: el LLM solo traduce las hipótesis a términos de condición
en inglés y etiqueta compatibilidad; la búsqueda, los filtros duros y el orden
son deterministas (`backend/pipeline/trial_matching.py`). El LLM nunca excluye
un ensayo.

Uso:
    python scripts/demo_agente05.py            # consulta de verdad (2 llamadas a Groq)
    python scripts/demo_agente05.py --sin-red  # respuestas grabadas + caídas simuladas

El modo normal necesita GROQ_API_KEY. ORPHANET_API_KEY es opcional: la API
responde sin credencial y el agente la consulta igual.

El modo --sin-red no toca la red: usa respuestas grabadas de una corrida real y
después simula la caída de ClinicalTrials.gov, de Orphanet y del LLM para
mostrar que cada paso tiene su fallback y que el reporte informa qué falló.

Artefactos generados en output/demo_agente05/:
    1. navegacion.json → resultado completo del agente (entrada + salida)
    2. resumen.txt     → el mismo informe que imprime en pantalla
    3. fallbacks.txt   → solo en --sin-red: qué devuelve el agente ante cada caída
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# La consola de Windows usa cp1252 y no puede imprimir las cajas ni las tildes
# de los títulos: sin esto el script termina en UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from backend.agents.agent_05_trials import TrialNavigatorAgent
from backend.external.orphanet import RareDisease
from backend.external.rate_limiter import (
    ApiUnavailableError,
    clinical_trials_breaker,
    orphanet_breaker,
)
from backend.ingestion.biomarker_extractor import extract as extract_biomarkers
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.trial import ClinicalTrial, TrialNavigationResult
from backend.pipeline.trial_matching import (
    build_navigation_input,
    has_preferred_location,
)

_SEP = "═" * 78
_SUB = "─" * 78
_RAIZ = Path(__file__).parent.parent
_OUT_DIR = _RAIZ / "output" / "demo_agente05"
_CASO_TXT = _RAIZ / "output" / "demo" / "caso.txt"

# Caso base de la tesis. Si no está el .txt de la demo, se usa esta copia.
_CASO_BASE = """\
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Compromiso autonómico asociado (hipotensión ortostática,
disfunción sudomotora). Panel genético reducido (CMT panel de 40 genes) negativo.
Electromiograma: axonal difuso sin desmielinización. LCR normal. Anticuerpos
paraneoplásicos estándar (anti-Hu, anti-Yo, anti-Ri) negativos. 3 años de
seguimiento sin diagnóstico. Edad de inicio: 40 años. Antecedentes familiares:
padre con "problemas de equilibrio" no estudiados."""

# Síntesis PICO tal como la produjo el pipeline en una corrida real del caso.
# Se deja fija porque `pico.build()` usa el LLM: la demo del Agente 05 no debería
# gastar cupo de Groq en reconstruir su entrada.
_PICO = PICOSynthesis(
    patient_profile=(
        "Hombre de 42 años con neuropatía axonal sensitivomotora progresiva de "
        "18 meses de evolución y compromiso autonómico (hipotensión ortostática "
        "y disfunción sudomotora)."
    ),
    chief_complaint="Debilidad y pérdida sensitiva progresiva con síntomas autonómicos.",
    condition_en="axonal sensorimotor polyneuropathy",
    relevant_history=[
        "Compromiso autonómico (hipotensión ortostática, disfunción sudomotora)",
        "Antecedente familiar de problemas de equilibrio en el padre",
    ],
    negative_findings=[
        "Panel genético CMT de 40 genes negativo",
        "LCR normal",
        "Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos",
    ],
    disease_duration="18 meses",
    current_treatments=[],
    procedures_done=[
        "Electromiograma",
        "Análisis de líquido cefalorraquídeo",
        "Panel genético CMT de 40 genes",
        "Pruebas de anticuerpos paraneoplásicos",
    ],
    comparison="No aplica",
    primary_outcome="Identificar la etiología de la neuropatía tras 3 años sin diagnóstico.",
    secondary_outcomes=[],
    biomarkers=[],
    genetic_findings=[],
    clinical_narrative=_CASO_BASE,
)

# Hipótesis del reporte final del debate en esa misma corrida real.
_HIPOTESIS = [
    ("Neuropatía por amiloidosis transtiretina hereditaria (ATTRv).", Priority.HIGH, EvidenceLevel.III),
    ("Neuropatía sensitiva y autonómica hereditaria (HSAN) no cubierta por el panel genético CMT.", Priority.HIGH, EvidenceLevel.III),
    ("Neuropatía inflamatoria crónica desmielinizante (CIDP) con variante predominantemente axonal.", Priority.HIGH, EvidenceLevel.III),
    ("Enfermedad de Fabry con neuropatía periférica y disautonomía.", Priority.MEDIUM, EvidenceLevel.III),
    ("Neuropatía vasculítica periférica (vasculitis aislada o sistémica).", Priority.MEDIUM, EvidenceLevel.III),
]

_COMPAT = {
    "alta": "COMPATIBILIDAD ALTA",
    "media": "COMPATIBILIDAD MEDIA",
    "baja": "COMPATIBILIDAD BAJA",
    "sin_evaluar": "SIN EVALUAR",
}


# ── Entrada del agente ─────────────────────────────────────────────────────────

def _caso() -> ClinicalCase:
    """Arma el ClinicalCase del caso base: PICO fija + biomarcadores reales."""
    texto = _CASO_TXT.read_text(encoding="utf-8") if _CASO_TXT.exists() else _CASO_BASE
    case = ClinicalCase(raw_text=texto)
    case.pico = _PICO
    # El extractor de biomarcadores es determinista (regex): se corre de verdad.
    case.biomarkers = extract_biomarkers(texto)
    return case


def _hipotesis() -> list[Hypothesis]:
    return [
        Hypothesis(
            text=texto,
            priority=prioridad,
            evidence_level=nivel,
            rationale="Hipótesis del reporte final del debate.",
        )
        for texto, prioridad, nivel in _HIPOTESIS
    ]


# ── Informe ────────────────────────────────────────────────────────────────────

def _informe_entrada(entrada) -> list[str]:
    lineas = [
        _SEP,
        "  ENTRADA DEL AGENTE 05 (contrato neutral, arma trial_matching)",
        _SEP,
        f"  Condición en inglés : {entrada.condition_en or '—'}",
        f"  Biomarcadores (saneados) : {', '.join(entrada.biomarker_terms) or '—'}",
        "",
        "  Demografía detectada por reglas (nunca sale del proceso):",
        f"    edad : {entrada.demographics.age_years or '— (no se pudo interpretar)'}",
        f"    sexo : {entrada.demographics.sex or '— (no se pudo interpretar)'}",
        "",
        f"  Hipótesis candidatas ({len(entrada.candidates)} de {len(_HIPOTESIS)}, "
        "por prioridad y nivel de evidencia):",
    ]
    for i, c in enumerate(entrada.candidates, 1):
        lineas.append(f"    {i}. [{c.priority.value}/{c.evidence_level.value}] {c.text}")
    lineas.append("")
    return lineas


def _informe_salida(resultado: TrialNavigationResult, segundos: float) -> list[str]:
    s = resultado.summary
    lineas = [
        _SEP,
        "  SALIDA DEL AGENTE 05",
        _SEP,
        f"  Latencia total       : {segundos:.1f} s",
        f"  Planificación (LLM)  : {s.planificacion}",
        f"  Evaluación (LLM)     : {s.evaluacion}",
        f"  ClinicalTrials.gov   : {s.estado_clinicaltrials}",
        f"  Orphanet             : {s.estado_orphanet}",
        "",
        f"  Términos consultados : {len(s.terminos_consultados)}",
    ]
    for termino in s.terminos_consultados:
        lineas.append(f"    · {termino}")
    lineas += [
        "",
        f"  Ensayos únicos encontrados      : {s.encontrados}",
        f"  Excluidos por edad              : {s.excluidos_por_edad}",
        f"  Excluidos por sexo              : {s.excluidos_por_sexo}",
        f"  Evaluaciones descartadas (LLM)  : {s.evaluaciones_descartadas}"
        "   (NCT ID que no se le enviaron)",
        f"  Ensayos en el reporte           : {len(resultado.trials)}",
        "",
        _SUB,
        "  ENSAYOS (orden: compatibilidad → Argentina → ya recluta → descubrimiento)",
        _SUB,
    ]

    if not resultado.trials:
        lineas.append(
            "  Ninguno."
            + (
                "  ClinicalTrials.gov no se pudo consultar: no significa que no existan."
                if s.estado_clinicaltrials == "no_disponible"
                else "  La búsqueda respondió y no hubo ensayos relacionados."
            )
        )
    for i, t in enumerate(resultado.trials, 1):
        etiquetas = [_COMPAT.get(t.compatibility, t.compatibility)]
        if t.status == "NOT_YET_RECRUITING":
            etiquetas.append("AÚN NO RECLUTA")
        if has_preferred_location(t):
            etiquetas.append("SEDE EN ARGENTINA")
        lineas.append(f"  {i}. [{' · '.join(etiquetas)}]  {t.nct_id}")
        lineas.append(f"     {t.title[:100]}")
        if t.compatibility_rationale:
            lineas.append(f"     Fundamento: {t.compatibility_rationale[:180]}")
        for criterio in t.criteria_to_verify[:3]:
            lineas.append(f"     A verificar: {criterio[:150]}")
        if t.related_hypotheses:
            lineas.append(f"     Trajo la hipótesis: {t.related_hypotheses[0][:90]}")
        lineas.append(f"     Estado: {t.status} · Sedes: {', '.join(t.locations[:4]) or '—'}")
        lineas.append("")

    lineas += [
        _SUB,
        "  ENFERMEDADES RARAS (Orphanet — coincidencia EXACTA del nombre preferido)",
        _SUB,
    ]
    if not resultado.rare_diseases:
        lineas.append(
            "  Ninguna hipótesis coincidió de forma exacta. La coincidencia parcial "
            "no marca:\n  etiquetaría una neuropatía axonal del adulto como enfermedad "
            "neonatal letal."
        )
    for marca in resultado.rare_diseases:
        lineas.append(f"  · ORPHA:{marca.orpha_code} — {marca.name}")
        lineas.append(f"    {marca.url}")
        lineas.append(f"    Hipótesis : {marca.hypothesis}")
        lineas.append(f"    Coincidió con el término: {marca.matched_term}")
    lineas.append("")
    lineas.append(
        "  La compatibilidad es orientativa: la elegibilidad la determina el equipo "
        "investigador de cada ensayo."
    )
    lineas.append(_SEP)
    return lineas


# ── Modo normal: consulta de verdad ────────────────────────────────────────────

def _correr_real() -> None:
    entrada = build_navigation_input(_caso(), _hipotesis())

    print(_SEP)
    print("  DEMO AGENTE 05 — NAVEGADOR DE ENSAYOS (consultas reales)")
    print(_SEP)
    print("  Caso base: neuropatía axonal sensitivomotora, hombre de 42 años.")
    print("  APIs: ClinicalTrials.gov (RECRUITING + NOT_YET_RECRUITING) y Orphanet.")
    print(f"  ORPHANET_API_KEY definida: {'sí' if __import__('os').getenv('ORPHANET_API_KEY') else 'no'}"
          "  (la API responde igual: se consulta siempre)")
    print()

    lineas = _informe_entrada(entrada)
    print("\n".join(lineas))
    print("  Consultando… (2 llamadas al LLM + ClinicalTrials.gov + Orphanet)")
    print()

    inicio = time.perf_counter()
    resultado = asyncio.run(TrialNavigatorAgent().navigate(entrada))
    segundos = time.perf_counter() - inicio

    salida = _informe_salida(resultado, segundos)
    lineas += salida
    print("\n".join(salida))

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    resumen_txt = _OUT_DIR / "resumen.txt"
    navegacion_json = _OUT_DIR / "navegacion.json"
    resumen_txt.write_text("\n".join(lineas), encoding="utf-8")
    navegacion_json.write_text(
        json.dumps(
            {
                "entrada": entrada.model_dump(),
                "latencia_segundos": round(segundos, 2),
                "salida": resultado.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Informe de la corrida → {resumen_txt}")
    print(f"    • Entrada + salida JSON → {navegacion_json}")
    print(_SEP)


# ── Modo --sin-red: respuestas grabadas y caídas simuladas ─────────────────────

# Respuestas grabadas de una corrida real, para que la demo corra sin conexión.
_LLM_PLAN = json.dumps({
    "terms": [
        {"candidate": 1, "condition_en": "hereditary transthyretin amyloidosis",
         "synonyms_en": ["hereditary ATTR amyloidosis", "transthyretin amyloid polyneuropathy"]},
        {"candidate": 2, "condition_en": "hereditary sensory and autonomic neuropathy",
         "synonyms_en": ["HSAN"]},
        {"candidate": 3, "condition_en": "chronic inflammatory demyelinating polyneuropathy",
         "synonyms_en": ["CIDP"]},
    ]
})

_LLM_EVAL = json.dumps({
    "evaluations": [
        {"nct_id": "NCT04000001", "compatibility": "alta",
         "rationale": "Estudia polineuropatía amiloidótica por transtiretina en adultos; "
                      "el rango etario y el sexo admiten al paciente.",
         "criteria_to_verify": ["Confirmar variante patogénica en TTR",
                                "Estadio de la polineuropatía según la escala del protocolo"]},
        {"nct_id": "NCT04000002", "compatibility": "media",
         "rationale": "Ensayo de neuropatía axonal en general: la condición encaja, "
                      "pero exige biopsia de nervio previa.",
         "criteria_to_verify": ["Biopsia de nervio sural disponible"]},
        # NCT que el agente nunca envió: se descarta y se cuenta.
        {"nct_id": "NCT99999999", "compatibility": "alta",
         "rationale": "Ensayo inventado por el LLM.", "criteria_to_verify": []},
    ]
})

_TRIALS_GRABADOS = {
    "axonal sensorimotor polyneuropathy": [
        ClinicalTrial(
            nct_id="NCT04000002",
            title="Natural History Study of Axonal Sensorimotor Polyneuropathy",
            status="RECRUITING",
            brief_summary="Estudio observacional de historia natural.",
            conditions=["Axonal Neuropathy"],
            min_age="18 Years", max_age="80 Years", sex="ALL",
            locations=["United States", "Spain"],
            url="https://clinicaltrials.gov/study/NCT04000002",
        ),
        # Excluido por edad: el paciente tiene 42 y el ensayo admite hasta 17.
        ClinicalTrial(
            nct_id="NCT04000003",
            title="Pediatric Inherited Neuropathy Registry",
            status="RECRUITING",
            brief_summary="Registro pediátrico.",
            conditions=["Inherited Neuropathy"],
            min_age="6 Years", max_age="17 Years", sex="ALL",
            locations=["United States"],
            url="https://clinicaltrials.gov/study/NCT04000003",
        ),
    ],
    "hereditary transthyretin amyloidosis": [
        ClinicalTrial(
            nct_id="NCT04000001",
            title="Gene Silencing Therapy in Hereditary ATTR Amyloidosis With Polyneuropathy",
            status="NOT_YET_RECRUITING",
            brief_summary="Ensayo de terapia de silenciamiento génico.",
            conditions=["Hereditary ATTR Amyloidosis"],
            min_age="18 Years", max_age="85 Years", sex="ALL",
            locations=["Argentina", "Brazil", "Spain"],
            url="https://clinicaltrials.gov/study/NCT04000001",
        ),
    ],
}

_ORPHANET_GRABADO = {
    "hereditary ATTR amyloidosis": [
        RareDisease(orpha_code="271861", name="Hereditary ATTR amyloidosis", definition=""),
    ],
    "hereditary transthyretin amyloidosis": [
        RareDisease(orpha_code="85447", name="Hereditary amyloidosis", definition=""),
        RareDisease(orpha_code="271861", name="Hereditary ATTR amyloidosis", definition=""),
    ],
    "axonal sensorimotor polyneuropathy": [
        # Coincidencia solo parcial: NO debe marcar la hipótesis.
        RareDisease(
            orpha_code="64746",
            name="Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy",
            definition="",
        ),
    ],
}


def _buscar_grabado(**kwargs) -> list[ClinicalTrial]:
    """Reemplazo sin red de clinical_trials.search()."""
    return list(_TRIALS_GRABADOS.get(kwargs.get("condition", ""), []))


def _orphanet_patch(side_effect=None):
    """Reemplazo sin red de OrphanetClient (context manager asíncrono)."""
    async def grabado(nombre: str, *args, **kwargs) -> list[RareDisease]:
        return list(_ORPHANET_GRABADO.get(nombre, []))

    cliente = MagicMock()
    cliente.search = AsyncMock(side_effect=side_effect or grabado)
    contexto = MagicMock()
    contexto.__aenter__ = AsyncMock(return_value=cliente)
    contexto.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "backend.agents.agent_05_trials.OrphanetClient", return_value=contexto
    )


def _escenario(
    entrada,
    *,
    llm=None,
    buscar=None,
    orphanet_side_effect=None,
) -> tuple[TrialNavigationResult, float]:
    """Corre navigate() con los reemplazos del escenario y devuelve su resultado."""
    # Los breakers son globales: sin resetear, un escenario contagia al siguiente.
    clinical_trials_breaker.reset()
    orphanet_breaker.reset()

    agent = TrialNavigatorAgent()
    agent._call_llm = MagicMock(  # type: ignore[method-assign]
        side_effect=llm if llm is not None else [_LLM_PLAN, _LLM_EVAL]
    )

    inicio = time.perf_counter()
    with patch(
        "backend.external.clinical_trials.search",
        side_effect=buscar if buscar is not None else _buscar_grabado,
    ), _orphanet_patch(orphanet_side_effect):
        resultado = asyncio.run(agent.navigate(entrada))
    return resultado, time.perf_counter() - inicio


def _correr_sin_red() -> None:
    entrada = build_navigation_input(_caso(), _hipotesis())

    cabecera = [
        _SEP,
        "  DEMO AGENTE 05 — MODO SIN RED (respuestas grabadas y caídas simuladas)",
        _SEP,
        "  Ninguna consulta sale a internet. Primero se muestra el camino feliz con",
        "  respuestas grabadas de una corrida real y después se tira abajo cada",
        "  dependencia para ver su fallback: el agente SIEMPRE devuelve un resultado",
        "  y el reporte informa qué falló.",
        "",
    ]
    print("\n".join(cabecera))
    print("\n".join(_informe_entrada(entrada)))

    escenarios = [
        (
            "1. TODO RESPONDE (respuestas grabadas)",
            "Camino completo: el LLM traduce las hipótesis, se encuentran ensayos,\n"
            "  uno queda excluido por edad, el NCT inventado por el LLM se descarta\n"
            "  y la hipótesis de ATTRv coincide de forma exacta con Orphanet.",
            {},
        ),
        (
            "2. CLINICALTRIALS.GOV CAÍDO",
            "Todas las consultas de ensayos fallan por timeout.",
            {"buscar": TimeoutError("timeout simulado")},
        ),
        (
            "3. ORPHANET CAÍDO",
            "Orphanet no responde; los ensayos tienen que llegar igual.",
            {"orphanet_side_effect": ApiUnavailableError("Orphanet", "503 simulado")},
        ),
        (
            "4. LLM CAÍDO",
            "Groq no responde: sin traducción de hipótesis (solo búsqueda base) y\n"
            "  sin evaluación de compatibilidad.",
            {"llm": RuntimeError("Groq no disponible (simulado)")},
        ),
    ]

    lineas = cabecera + _informe_entrada(entrada)
    for titulo, explicacion, kwargs in escenarios:
        bloque = [_SEP, f"  ESCENARIO {titulo}", _SEP, f"  {explicacion}", ""]
        resultado, segundos = _escenario(entrada, **kwargs)
        bloque += _informe_salida(resultado, segundos)
        lineas += bloque
        print("\n".join(bloque))

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    fallbacks_txt = _OUT_DIR / "fallbacks.txt"
    fallbacks_txt.write_text("\n".join(lineas), encoding="utf-8")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Los cuatro escenarios → {fallbacks_txt}")
    print(_SEP)


def main() -> None:
    if "--sin-red" in sys.argv:
        _correr_sin_red()
    else:
        _correr_real()


if __name__ == "__main__":
    main()
