"""
Demo de verificación — Agente 04: Árbitro Verificador.

Muestra entrada → salida del agente sobre el caso base de la tesis (neuropatía
axonal sensitivomotora, paciente masculino de 42 años):

    ENTRADA   las hipótesis que dejó el debate, con su autor, y las críticas
              cruzadas de la Ronda 2
    SALIDA    la partición del agrupamiento (qué se agrupó con qué y por qué),
              las contradicciones que quedaron abiertas, los veredictos, el
              resultado de la Ronda 5 de recitación y el solapamiento entre la
              literatura que el RAG recuperó y la que los agentes citaron

El agente es híbrido: el LLM solo propone qué hipótesis son equivalentes —y lo
hace devolviendo índices, nunca texto— y redacta los veredictos. El
agrupamiento se valida, el enunciado de cada hipótesis de consenso sale de un
agente y no del modelo, y las contradicciones salen de las críticas ya
estructuradas del debate (`backend/pipeline/consensus.py`).

Uso:
    python scripts/demo_agente04.py            # consulta de verdad (2 llamadas a Groq)
    python scripts/demo_agente04.py --sin-red  # respuestas grabadas + caídas simuladas

El modo normal necesita GROQ_API_KEY.

El modo --sin-red no toca la red: usa respuestas grabadas y después simula la
caída del LLM y de PubMed para mostrar que cada paso tiene su fallback y que el
análisis termina igual.

Artefactos generados en output/demo_agente04/:
    1. arbitraje.json → resultado completo (entrada + salida)
    2. resumen.txt    → el mismo informe que imprime en pantalla
    3. fallbacks.txt  → solo en --sin-red: qué devuelve el agente ante cada caída
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.agents.agent_01_literature import LiteratureAnalystAgent  # noqa: E402
from backend.agents.agent_03_clinical import ClinicalConsultantAgent  # noqa: E402
from backend.agents.agent_04_arbiter import ArbiterAgent  # noqa: E402
from backend.models.arbitration import ArbitrationInput  # noqa: E402
from backend.models.hypothesis import (  # noqa: E402
    EvidenceLevel,
    Hypothesis,
    Priority,
    Source,
)
from backend.models.report import Critique, RetrievedArticleRef  # noqa: E402
from backend.pipeline.verification import (  # noqa: E402
    SourceStatus,
    SourceVerification,
)

_OUT = Path(__file__).resolve().parent.parent / "output" / "demo_agente04"
_ANCHO = 78


# ── Caso de prueba ─────────────────────────────────────────────────────────────

# Las mismas hipótesis repetidas por agentes distintos, que es exactamente lo
# que deja hoy el debate: `run_debate()` concatena los outputs sin consolidar.
_HIPOTESIS = [
    ("01", "Amiloidosis hereditaria por transtiretina (ATTRv) como causa de la "
           "neuropatía axonal de fibra fina", ["28712356"], EvidenceLevel.II, Priority.HIGH),
    ("01", "Déficit de vitamina B12 inducido por metformina",
     ["22439958"], EvidenceLevel.II, Priority.MEDIUM),
    ("02", "Variante patogénica en TTR con compromiso de fibra pequeña y disautonomía",
     ["30678901"], EvidenceLevel.II, Priority.HIGH),
    ("02", "Enfermedad de Fabry no diagnosticada (variante en GLA)",
     ["28712356"], EvidenceLevel.III, Priority.LOW),
    ("03", "Neuropatía amiloidótica familiar por transtiretina",
     ["26012344"], EvidenceLevel.II, Priority.HIGH),
    ("03", "Ganglionopatía autonómica autoinmune (anti-AChR ganglionar)",
     ["32245678"], EvidenceLevel.II, Priority.LOW),
]

_CRITICAS = [
    ("03", "Consultor Clínico", "01",
     "Amiloidosis hereditaria por transtiretina (ATTRv) como causa de la neuropatía "
     "axonal de fibra fina",
     "Sin biopsia con rojo Congo ni estudio genético de TTR, la hipótesis no se "
     "sostiene como principal: el diferencial con neuropatía diabética queda abierto.",
     "HIGH"),
    ("01", "Analista de Literatura", "03",
     "Ganglionopatía autonómica autoinmune (anti-AChR ganglionar)",
     "La prevalencia es muy baja y no hay anticuerpos solicitados en el caso.",
     "MEDIUM"),
]

# Lo que el RAG recuperó y puso en el prompt de la Ronda 1. Ninguno de estos
# PMIDs coincide con los que citaron los agentes: eso es lo que el demo muestra.
_RECUPERADOS = [
    ("33245678", "Hereditary transthyretin amyloidosis: a rapidly evolving therapeutic landscape",
     "Nat Rev Neurol", "2021"),
    ("31234567", "Small fiber neuropathy: diagnostic approach and etiologies",
     "Muscle Nerve", "2019"),
    ("34567890", "Diagnostic delay in hereditary ATTR amyloidosis with polyneuropathy",
     "Orphanet J Rare Dis", "2021"),
]


def _entrada() -> ArbitrationInput:
    """Arma el contrato de entrada tal como lo deja el debate sobre el caso base."""
    hypotheses: list[Hypothesis] = []
    agents: list[str] = []
    por_agente: dict[str, list[Hypothesis]] = {}

    for agent_id, texto, pmids, nivel, prioridad in _HIPOTESIS:
        h = Hypothesis(
            text=texto,
            priority=prioridad,
            evidence_level=nivel,
            rationale="Fundamento producido por el agente durante el debate.",
            sources=[Source(pmid=p, title=f"Artículo citado {p}") for p in pmids],
        )
        hypotheses.append(h)
        agents.append(agent_id)
        por_agente.setdefault(agent_id, []).append(h)

    critiques = [
        Critique(
            from_agent_id=fid, from_agent_name=fname, target_agent_id=tid,
            target_hypothesis=thyp, critique_text=texto, severity=sev,
        )
        for fid, fname, tid, thyp, texto, sev in _CRITICAS
    ]

    return ArbitrationInput(
        hypotheses=hypotheses,
        hypothesis_agents=agents,
        critiques=critiques,
        round_1_by_agent=por_agente,
        final_by_agent=por_agente,
        agent_names={
            "01": "Analista de Literatura",
            "02": "Especialista Genómica",
            "03": "Consultor Clínico",
        },
        retrieved_articles=[
            RetrievedArticleRef(pmid=p, title=t, journal=j, year=y,
                                excerpt=f"Resumen indexado de {t}.")
            for p, t, j, y in _RECUPERADOS
        ],
    )


def _verificaciones(entrada: ArbitrationInput) -> dict[str, SourceVerification]:
    """
    Veredictos de la verificación bibliográfica, como los produjo la corrida real.

    Uno solo resiste el contraste: el resto son PMIDs que existen en PubMed pero
    apuntan a otro artículo. Es el hallazgo que motivó al Árbitro.
    """
    verificados = {"26012344"}
    veredictos: dict[str, SourceVerification] = {}
    for h in entrada.hypotheses:
        for s in h.sources:
            if not s.pmid or s.pmid in veredictos:
                continue
            if s.pmid in verificados:
                veredictos[s.pmid] = SourceVerification(
                    pmid=s.pmid, status=SourceStatus.VERIFICADA,
                    claimed_title=s.title, actual_title=s.title, match_score=1.0,
                    publication_types=["Case Reports"],
                )
            else:
                veredictos[s.pmid] = SourceVerification(
                    pmid=s.pmid, status=SourceStatus.DISCORDANTE,
                    claimed_title=s.title,
                    actual_title="Breeding replacement gilts for organic pig herds",
                    match_score=0.0,
                )
    return veredictos


# ── Impresión ──────────────────────────────────────────────────────────────────

class _Informe:
    """Acumula el informe para imprimirlo y guardarlo a la vez."""

    def __init__(self) -> None:
        self.lineas: list[str] = []

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.lineas.append(texto)

    def titulo(self, texto: str) -> None:
        self("═" * _ANCHO)
        self(f"  {texto}")
        self("═" * _ANCHO)

    def seccion(self, texto: str) -> None:
        self()
        self(f"── {texto} " + "─" * max(0, _ANCHO - len(texto) - 4))

    def texto(self) -> str:
        return "\n".join(self.lineas)


def _mostrar_entrada(log: _Informe, entrada: ArbitrationInput) -> None:
    log.seccion("ENTRADA — lo que dejó el debate")
    log(f"  {len(entrada.hypotheses)} hipótesis, sin consolidar, de "
        f"{len(set(entrada.hypothesis_agents))} agentes:")
    log()
    for i, h in enumerate(entrada.hypotheses, 1):
        agente = entrada.name_of(entrada.agent_of(i - 1))
        pmids = ", ".join(s.pmid or "—" for s in h.sources)
        log(f"  {i}. [{agente}] {h.text}")
        log(f"     evidencia {h.evidence_level.value} · prioridad {h.priority.value} "
            f"· cita PMID {pmids}")
    log()
    log(f"  {len(entrada.critiques)} críticas de la Ronda 2 "
        f"({sum(1 for c in entrada.critiques if c.severity == 'HIGH')} de severidad HIGH)")
    log(f"  {len(entrada.retrieved_articles)} artículos recuperados por el RAG:")
    for a in entrada.retrieved_articles:
        log(f"     PMID {a.pmid} — {a.title[:60]}")


def _mostrar_salida(log: _Informe, entrada: ArbitrationInput, resultado) -> None:
    log.seccion("SALIDA — el consenso del Árbitro")
    log(f"  Estado del arbitraje: {resultado.summary.status.value}")
    log(f"  {resultado.summary.input_hypotheses} hipótesis de entrada → "
        f"{resultado.summary.consensus_hypotheses} de consenso")
    log()

    for i, item in enumerate(resultado.consensus, 1):
        log(f"  #{i} {item.hypothesis.text}")
        log(f"      agrupa {len(item.grouped)} hipótesis del debate")
        log(f"      la sostienen: {', '.join(item.supporting_agents) or '—'}")
        if item.refuting_agents:
            log(f"      la objetan:   {', '.join(item.refuting_agents)}")
        for c in item.contradictions:
            log(f"        · {c.from_agent_name} [{c.severity}]: {c.critique_text[:100]}")
        if item.verdict:
            log(f"      veredicto: {item.verdict}")
        if item.recitation.value != "no_aplica":
            log(f"      recitación: {item.recitation.value}")
        if len(item.grouped) > 1:
            log("      hipótesis agrupadas:")
            for g in item.grouped:
                marca = "←" if g.text == item.hypothesis.text else " "
                log(f"        {marca} {g.text[:66]}")
        log()


def _mostrar_metricas(log: _Informe, resultado) -> None:
    r = resultado.summary
    log.seccion("MÉTRICAS — por qué existe el Árbitro")
    log(f"  Referencias citadas por los agentes:      {r.cited_sources}")
    log(f"  Artículos que el RAG les había ofrecido:  {r.retrieved_articles}")
    log(f"  Citas que salieron de esa literatura:     {r.rag_overlap} de {r.cited_sources}")
    if r.cited_sources and not r.rag_overlap:
        log("    → los agentes ignoraron por completo la literatura recuperada")
    log(f"  Objeciones sin resolver:                  {r.contradictions}")
    log(f"  Referencias inventadas y descartadas:     {r.discarded_references}")
    log()
    rec = r.recitation
    log(f"  Ronda 5 ejecutada:                        {'sí' if rec.executed else 'no'}")
    if rec.executed:
        log(f"  Hipótesis que volvieron a citar:          {rec.recited}")
        log(f"  Consiguieron respaldo verificable:        {rec.improved}")
        log(f"  PMIDs rechazados por no estar ofrecidos:  {rec.rejected_pmids}")
        if rec.failed_agents:
            log(f"  Agentes cuya recitación falló:            {', '.join(rec.failed_agents)}")


# ── Modos ──────────────────────────────────────────────────────────────────────

_GRABADO_GRUPOS = json.dumps({"groups": [[1, 3, 5], [2], [4], [6]]})
_GRABADO_VEREDICTOS = json.dumps({"verdicts": [
    {"hypothesis": 1, "verdict": "Los tres agentes coinciden en la amiloidosis por "
     "transtiretina. La única referencia que resiste el contraste contra PubMed es un "
     "reporte de caso, así que el nivel efectivo queda en III. El Consultor Clínico "
     "mantiene que sin biopsia ni estudio genético la hipótesis no puede encabezar el "
     "diferencial."},
    {"hypothesis": 2, "verdict": "Sostenida por un solo agente. Ninguna de sus "
     "referencias resistió la verificación, así que queda especulativa: plausible por "
     "el historial de metformina, pero sin respaldo bibliográfico confirmado."},
    {"hypothesis": 3, "verdict": "Hipótesis de baja prioridad y sin respaldo "
     "verificable. Se conserva porque el tamizaje de Fabry es barato y el hallazgo "
     "cambiaría la conducta."},
    {"hypothesis": 4, "verdict": "Sin respaldo verificable y con una objeción de "
     "prevalencia del Analista de Literatura que no llegó a severidad alta."},
]})


class _AgenteGrabado:
    """
    Agente que recita con una respuesta grabada, para el modo --sin-red.

    Devuelve un PMID que sí estaba entre los recuperados (el agente aprendió) y
    otro inventado (no aprendió del todo), para que se vea la validación.
    """

    def __init__(self, indices: dict) -> None:
        self._indices = indices

    def recite(self, hypotheses_with_reasons, articles):  # noqa: ANN001
        return self._indices


async def _correr_real() -> tuple[ArbitrationInput, object]:
    """
    Corre el Árbitro de verdad contra Groq.

    2 llamadas fijas (agrupar y veredictos) más una por agente con hipótesis a
    recitar en la Ronda 5.
    """
    entrada = _entrada()
    verificaciones = _verificaciones(entrada)
    agentes = {"01": LiteratureAnalystAgent(), "03": ClinicalConsultantAgent()}
    inicio = time.perf_counter()
    resultado = await ArbiterAgent().arbitrate(entrada, verificaciones, agentes)
    print(f"\n  (latencia del arbitraje: {time.perf_counter() - inicio:.1f} s)")
    return entrada, resultado


async def _correr_sin_red() -> tuple[ArbitrationInput, object]:
    """Corre el Árbitro con respuestas grabadas, sin tocar la red."""
    entrada = _entrada()
    verificaciones = _verificaciones(entrada)
    respuestas = [_GRABADO_GRUPOS, _GRABADO_VEREDICTOS]

    def fake_llm(self, prompt):  # noqa: ANN001
        return respuestas.pop(0) if respuestas else "{}"

    # El primer agente recita bien; el segundo vuelve a inventar un PMID.
    agentes = {
        "01": _AgenteGrabado({0: [Source(pmid="33245678",
                                         title=_RECUPERADOS[0][1])]}),
        "03": _AgenteGrabado({0: [Source(pmid="99999999", title="Inventado otra vez")]}),
    }

    async def fake_verify(sources):  # noqa: ANN001
        return {
            s.pmid: SourceVerification(
                pmid=s.pmid, status=SourceStatus.VERIFICADA, claimed_title=s.title,
                actual_title=s.title, match_score=1.0,
                publication_types=["Randomized Controlled Trial"],
            )
            for s in sources if s.pmid
        }

    with patch("backend.agents.base_agent.BaseAgent._call_llm", fake_llm), \
         patch("backend.agents.agent_04_arbiter.verify_sources", fake_verify):
        resultado = await ArbiterAgent().arbitrate(entrada, verificaciones, agentes)
    return entrada, resultado


async def _mostrar_fallbacks(log: _Informe) -> str:
    """Simula cada caída y muestra qué devuelve el Árbitro en cada una."""
    lineas: list[str] = []

    def anotar(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    anotar("═" * _ANCHO)
    anotar("  FALLBACKS — qué pasa cuando algo se cae")
    anotar("═" * _ANCHO)

    entrada = _entrada()
    verificaciones = _verificaciones(entrada)

    # 1. El LLM no responde al agrupar.
    def cae(self, prompt):  # noqa: ANN001
        raise ConnectionError("Groq no disponible (simulado)")

    with patch("backend.agents.base_agent.BaseAgent._call_llm", cae):
        r = await ArbiterAgent().arbitrate(entrada, verificaciones)
    anotar()
    anotar("1. El LLM se cae al agrupar")
    anotar(f"   estado: {r.summary.status.value}")
    anotar(f"   hipótesis en el reporte: {len(r.consensus)} (las {len(entrada.hypotheses)} "
           f"del debate, sin consolidar)")
    anotar(f"   contradicciones detectadas igual: {r.summary.contradictions} "
           f"(no dependen del LLM)")
    anotar("   → el análisis termina y POST /api/analyze responde normalmente")

    # 2. El LLM devuelve algo que no es JSON.
    with patch("backend.agents.base_agent.BaseAgent._call_llm",
               lambda self, p: "Claro, te ayudo con el análisis clínico."):
        r = await ArbiterAgent().arbitrate(entrada, verificaciones)
    anotar()
    anotar("2. El LLM responde texto libre en vez de JSON")
    anotar(f"   estado: {r.summary.status.value}")
    anotar(f"   hipótesis conservadas: {sum(len(c.grouped) for c in r.consensus)}")

    # 3. El LLM inventa una referencia en un veredicto.
    respuestas = [
        _GRABADO_GRUPOS,
        json.dumps({"verdicts": [
            {"hypothesis": 1, "verdict": "Respaldada por el meta-análisis PMID 98765432."}
        ]}),
    ]
    with patch("backend.agents.base_agent.BaseAgent._call_llm",
               lambda self, p: respuestas.pop(0) if respuestas else "{}"):
        r = await ArbiterAgent().arbitrate(entrada, verificaciones)
    anotar()
    anotar("3. El LLM cita un PMID que nadie le mandó")
    anotar(f"   veredicto descartado entero: {r.summary.discarded_references}")
    anotar(f"   texto que llega al médico: {r.consensus[0].verdict or '(ninguno)'!r}")
    anotar("   → no se le deja inyectar referencias al reporte")

    # 4. La verificación bibliográfica no pudo ejecutarse.
    respuestas = [_GRABADO_GRUPOS, _GRABADO_VEREDICTOS]
    with patch("backend.agents.base_agent.BaseAgent._call_llm",
               lambda self, p: respuestas.pop(0) if respuestas else "{}"):
        r = await ArbiterAgent().arbitrate(entrada, {})
    anotar()
    anotar("4. PubMed no respondió: no hay veredictos de verificación")
    anotar(f"   estado: {r.summary.status.value}")
    anotar(f"   hipótesis de consenso: {len(r.consensus)}")
    anotar(f"   Ronda 5 ejecutada: {'sí' if r.summary.recitation.executed else 'no'}")
    anotar("   → no se recita: el problema es de infraestructura, no de la cita")

    anotar()
    anotar("═" * _ANCHO)
    return "\n".join(lineas)


# ── Entrada ────────────────────────────────────────────────────────────────────

def main() -> None:
    sin_red = "--sin-red" in sys.argv
    _OUT.mkdir(parents=True, exist_ok=True)

    log = _Informe()
    log.titulo("DEMO — Agente 04: Árbitro Verificador")
    log(f"  Modo: {'sin red (respuestas grabadas)' if sin_red else 'corrida real contra Groq'}")
    log("  Caso: neuropatía axonal sensitivomotora, paciente masculino de 42 años")

    entrada, resultado = asyncio.run(_correr_sin_red() if sin_red else _correr_real())

    _mostrar_entrada(log, entrada)
    _mostrar_salida(log, entrada, resultado)
    _mostrar_metricas(log, resultado)

    (_OUT / "arbitraje.json").write_text(
        json.dumps(
            {
                "entrada": entrada.model_dump(mode="json"),
                "salida": resultado.model_dump(mode="json"),
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    (_OUT / "resumen.txt").write_text(log.texto(), encoding="utf-8")

    if sin_red:
        print()
        texto_fallbacks = asyncio.run(_mostrar_fallbacks(log))
        (_OUT / "fallbacks.txt").write_text(texto_fallbacks, encoding="utf-8")

    log.seccion("ARTEFACTOS GENERADOS (abrir y capturar para Trello)")
    log(f"  • Arbitraje completo (JSON) → {_OUT / 'arbitraje.json'}")
    log(f"  • Informe legible           → {_OUT / 'resumen.txt'}")
    if sin_red:
        log(f"  • Fallbacks                 → {_OUT / 'fallbacks.txt'}")
    log("═" * _ANCHO)


if __name__ == "__main__":
    main()
