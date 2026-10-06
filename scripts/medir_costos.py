"""
Medición de costos del pipeline sobre el caso de prueba (Sprint 4, control de
costos — tareas 4.2, 5.4, 7.2 y 7.3 de `control-de-costos-del-pipeline`).

Corre el pipeline de `POST /api/analyze` llamando a sus funciones directamente
(el endpoint exige sesión de médico) y produce, con **una sola pasada del
debate**:

  1. Pasada base: ingesta → PICO → biomarcadores → RAG → Ronda 1 → debate →
     verificación → Árbitro → Agente 05, con la configuración actual de
     `TASK_BUDGETS`, dentro de un registro de telemetría.
  2. Comparación controlada (5.4) sobre las MISMAS entradas de esa pasada, sin
     repetir el debate: agrupación del Árbitro, planificación de términos y
     evaluación de compatibilidad del Agente 05, con GROQ_MAIN y con GROQ_FAST.
     Sus llamadas se contabilizan en registros aparte (`costos_comparacion.jsonl`),
     de modo que el total por caso refleje un análisis normal.
  3. Truncados y holgura de techos por tarea (4.2), números por paso y por
     agente (7.2) y cambio entre las Rondas 3 y 4 (7.3), derivados de la pasada
     base.

Salida en `output/medicion_costos/` (ignorada por git): `medicion.json`,
`resumen.txt` y `costos.jsonl`. Con `--mock` la salida va a la subcarpeta `mock/`
y queda marcada, para que nunca pise ni se confunda con una medición real.
No se vuelca el texto clínico del caso: solo conteos, índices, términos de
condición en inglés e identificadores NCT.

Los resultados se guardan en disco al terminar cada etapa: una falla a mitad de
camino no pierde lo ya pagado. Un fallo en una rama de la comparación se
registra y no detiene las demás.

Con `--grabar` (solo corrida real) la pasada base deja además las respuestas
crudas del modelo en `grabacion.json`, para regenerar las respuestas del modo
mock (`backend/mock/responses.py`). No se graba durante la comparación, que
repite las mismas tareas con otros modelos, ni el prompt ni el mensaje del
usuario. Esas respuestas pueden contener texto del caso: la carpeta es local e
ignorada por git. Con `--mock` no hay nada que grabar y se avisa.

Uso:
    python3 scripts/medir_costos.py --mock            # recorrido completo sin cuota
    python3 scripts/medir_costos.py                   # corrida real (gasta cuota de Groq)
    python3 scripts/medir_costos.py --grabar          # corrida real + grabacion.json
    python3 scripts/medir_costos.py --mock --grabar   # solo avisa: nada que grabar

La corrida real hace entre 25 y 27 llamadas al LLM (ver docstring de `main()`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv()

from backend.agents import model_tasks
from backend.agents.agent_04_arbiter import ArbiterAgent
from backend.agents.agent_05_trials import TrialNavigatorAgent
from backend.api.router import _arbitrate_safe, _navigate_trials_safe, _synthesize_safe
from backend.ingestion.biomarker_extractor import extract as extract_biomarkers
from backend.ingestion.normalizer import normalize
from backend.mock import recorder
from backend.mock.mode import ENV_VAR, is_mock_active
from backend.models.arbitration import ArbitrationResult
from backend.models.case import ClinicalCase
from backend.models.report import Report
from backend.models.trial import ClinicalTrial, TrialNavigationInput, TrialNavigationResult
from backend.pipeline import consensus as consensus_module
from backend.pipeline import debate, orchestrator, pico
from backend.pipeline.consensus import build_arbitration_input
from backend.pipeline.report_builder import build_export
from backend.pipeline.trial_matching import build_navigation_input
from backend.pipeline.verification import SourceVerification, verify_report_sources
from backend.telemetry import medicion
from backend.telemetry import usage as usage_telemetry
from backend.telemetry.usage import CallRecord

# Mismo caso base que `scripts/poc_test.py` (neuropatía axonal, 42 años).
from poc_test import CASO_CLINICO

SALIDA_REAL = RAIZ / "output" / "medicion_costos"
MODELOS = (model_tasks.GROQ_MAIN, model_tasks.GROQ_FAST)

# Llamadas al LLM de la comparación: 3 ramas x 2 modelos.
LLAMADAS_COMPARACION = 6


# ── Registro de resultados parciales ──────────────────────────────────────────

class Medicion:
    """Dict de resultados con guardado atómico a disco tras cada etapa."""

    def __init__(self, carpeta: Path, mock: bool) -> None:
        self.carpeta = carpeta
        self.datos: dict = {
            "mock": mock,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "case": "neuropatía axonal sensitivomotora, paciente masculino de 42 años "
                    "(texto del caso no incluido)",
            "budgets": {
                t: {"model": b.model, "max_tokens": b.max_tokens}
                for t, b in model_tasks.TASK_BUDGETS.items()
            },
            "stages": {},
        }
        carpeta.mkdir(parents=True, exist_ok=True)
        self._preservar_anterior()

    def _preservar_anterior(self) -> None:
        """No pisa una medición previa: la renombra con su fecha de modificación."""
        previo = self.carpeta / "medicion.json"
        if previo.exists():
            sello = datetime.fromtimestamp(previo.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
            previo.rename(self.carpeta / f"medicion.{sello}.json")

    def guardar(self) -> None:
        """Escribe `medicion.json` y `resumen.txt`; falla fuerte si no puede."""
        for nombre, contenido in (
            ("medicion.json", json.dumps(self.datos, ensure_ascii=False, indent=2)),
            ("resumen.txt", medicion.render_summary(self.datos)),
        ):
            tmp = self.carpeta / f"{nombre}.tmp"
            tmp.write_text(contenido, encoding="utf-8")
            tmp.replace(self.carpeta / nombre)

    def etapa(self, nombre: str, estado: str, segundos: float, error: str | None = None) -> None:
        self.datos["stages"][nombre] = {
            "status": estado,
            "seconds": round(segundos, 3),
            "error": error,
        }
        self.guardar()


def preservar_grabacion_anterior(carpeta: Path) -> None:
    """No pisa una grabación previa: la renombra con su fecha de modificación."""
    previa = carpeta / "grabacion.json"
    if previa.exists():
        sello = datetime.fromtimestamp(previa.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
        previa.rename(carpeta / f"grabacion.{sello}.json")


def _error(exc: BaseException) -> str:
    """Solo el tipo de la excepción: el mensaje puede arrastrar texto clínico."""
    return type(exc).__name__


# ── Pasada base ───────────────────────────────────────────────────────────────

@dataclass
class ResultadoBase:
    """Lo que dejó la pasada base y necesitan la comparación y las rondas."""

    case: ClinicalCase | None = None
    report: Report | None = None
    arbitration: ArbitrationResult | None = None
    nav_input: TrialNavigationInput | None = None
    navigation: TrialNavigationResult | None = None
    executive_summary: str | None = None
    tiempos: dict[str, float] = field(default_factory=dict)


async def _paso(res: ResultadoBase, nombre: str, coro: Awaitable):
    """Ejecuta un paso del pipeline midiendo su latencia."""
    inicio = time.perf_counter()
    try:
        return await coro
    finally:
        res.tiempos[nombre] = round(time.perf_counter() - inicio, 3)


async def pasada_base(res: ResultadoBase) -> None:
    """
    Pipeline completo en el mismo orden que `router.analyze()`.

    Deja en `res` lo que se alcanzó a producir aunque un paso levante: la
    comparación y las rondas usan lo que haya.
    """
    normalized = await _paso(res, "normalizacion", asyncio.to_thread(normalize, CASO_CLINICO))
    case = ClinicalCase(raw_text=normalized)

    case_pico, biomarkers = await _paso(res, "pico_y_biomarcadores", asyncio.gather(
        asyncio.to_thread(pico.build, case),
        asyncio.to_thread(extract_biomarkers, normalized),
    ))
    case_pico.biomarkers = biomarkers
    res.case = case_pico

    round_1 = await _paso(res, "ronda_1_con_rag", orchestrator.run_round_1(case_pico))
    res.report = round_1
    final_report = await _paso(res, "debate_rondas_2_a_4", debate.run_debate(case_pico, round_1))
    res.report = final_report

    verifications: dict[str, SourceVerification] = await _paso(
        res, "verificacion_pmids", verify_report_sources(final_report)
    )
    res.arbitration = await _paso(
        res, "arbitro", _arbitrate_safe(final_report, verifications, case_pico)
    )

    consenso = [c.hypothesis for c in res.arbitration.consensus]
    res.nav_input = build_navigation_input(case_pico, consenso or final_report.hypotheses)
    res.navigation = await _paso(res, "agente_05", _navigate_trials_safe(res.nav_input))

    structured = build_export(
        case=case_pico, report=final_report, trials=res.navigation.trials,
        processing_time=sum(res.tiempos.values()), verifications=verifications,
        navigation=res.navigation, arbitration=res.arbitration, mock=is_mock_active(),
    )
    res.executive_summary = await _paso(res, "agente_06", _synthesize_safe(structured))


# ── Comparación controlada (5.4) ──────────────────────────────────────────────

def _uso(calls: list[CallRecord]) -> dict:
    """Consumo de una rama de la comparación."""
    return {
        "calls": len(calls),
        "failed_calls": sum(1 for c in calls if not c.ok),
        "prompt_tokens": sum(c.prompt_tokens or 0 for c in calls),
        "completion_tokens": sum(c.completion_tokens or 0 for c in calls),
        "max_completion_tokens": medicion.max_completion(calls),
        "truncated_calls": sum(1 for c in calls if c.truncated),
    }


def _uso_texto(uso: dict) -> str:
    return (f"{uso['calls']} llamada(s), {uso['prompt_tokens']}+{uso['completion_tokens']} tokens, "
            f"{uso['truncated_calls']} cortada(s)")


async def _en_registro_aparte(
    carpeta: Path, mock: bool, rama: Callable[[], Awaitable]
) -> tuple[object, list[CallRecord]]:
    """
    Corre una rama dentro de su propio registro de telemetría.

    Va a `costos_comparacion.jsonl`, no a `costos.jsonl`: las llamadas de la
    comparación no son parte de un análisis normal. Cierra el registro aunque la
    rama falle, y devuelve las llamadas hechas hasta ahí junto con la excepción
    si la hubo (la excepción se re-lanza después de cerrar).
    """
    token = usage_telemetry.open_registry()
    registro = usage_telemetry.current()
    try:
        resultado = await rama()
        error: BaseException | None = None
    except Exception as exc:  # una rama que falla no tira las demás
        resultado, error = None, exc
    finally:
        usage_telemetry.close_registry(
            token, output_path=carpeta / "costos_comparacion.jsonl", mock=mock
        )
    llamadas = list(registro.calls) if registro else []
    if error is not None:
        raise _RamaFallida(error, llamadas)
    return resultado, llamadas


class _RamaFallida(Exception):
    """Una rama falló; lleva las llamadas que alcanzó a hacer (ya pagadas)."""

    def __init__(self, causa: BaseException, llamadas: list[CallRecord]) -> None:
        super().__init__(type(causa).__name__)
        self.causa = causa
        self.llamadas = llamadas


async def _comparar_por_modelo(
    carpeta: Path, mock: bool, tarea: str,
    rama: Callable[[str], Awaitable[dict]],
) -> dict[str, dict]:
    """
    Corre `rama(modelo)` con cada modelo, cambiando `TASK_BUDGETS[tarea]`
    temporalmente. Devuelve, por modelo, su resultado o su error, más el uso.
    """
    por_modelo: dict[str, dict] = {}
    for modelo in MODELOS:
        try:
            with medicion.swapped_model(tarea, modelo):
                resultado, llamadas = await _en_registro_aparte(
                    carpeta, mock, lambda: rama(modelo)
                )
            uso = _uso(llamadas)
            por_modelo[modelo] = {**resultado, "status": "ok", "usage": uso,
                                  "usage_summary": _uso_texto(uso), "error": None}
        except _RamaFallida as fallo:
            uso = _uso(fallo.llamadas)
            por_modelo[modelo] = {"status": "error", "error": _error(fallo.causa),
                                  "usage": uso, "usage_summary": _uso_texto(uso)}
        except Exception as exc:  # fallo al armar la rama, antes de llamar al LLM
            por_modelo[modelo] = {"status": "error", "error": _error(exc),
                                  "usage": None, "usage_summary": None}
    return por_modelo


async def comparar_agrupacion(m: Medicion, res: ResultadoBase, mock: bool) -> None:
    """Agrupación del Árbitro con cada modelo, sobre las mismas hipótesis."""
    inicio = time.perf_counter()
    if res.report is None:
        m.datos.setdefault("comparison", {})["grouping"] = {
            "status": "omitida", "reason": "la pasada base no llegó a producir el reporte del debate",
        }
        m.etapa("comparacion_agrupacion", "omitida", 0.0)
        return
    entrada = build_arbitration_input(res.report)
    total = len(entrada.hypotheses)

    async def rama(modelo: str) -> dict:
        # Se espía la entrada de `normalize_partition()` para saber qué propuso
        # el modelo antes de la validación determinista. No se toca el agente.
        propuestas: list[list[list[int]]] = []
        original = consensus_module.normalize_partition

        def espia(groups, total_):
            propuestas.append([list(g) for g in groups])
            return original(groups, total_)

        consensus_module.normalize_partition = espia
        try:
            grupos, estado = await ArbiterAgent()._group(entrada)
        finally:
            consensus_module.normalize_partition = original
        propuesta = propuestas[0] if propuestas else None
        clasificacion = medicion.classify_grouping(propuesta, grupos, estado)
        return {
            "partition": grupos,
            "groups": len(grupos),
            "arbiter_status": estado.value,
            "outcome": clasificacion,
        }

    por_modelo = await _comparar_por_modelo(m.carpeta, mock, "arbitro_agrupacion", rama)

    comparacion = None
    ok = [r for r in por_modelo.values() if r["status"] == "ok"]
    if len(ok) == len(MODELOS):
        iguales = medicion.partitions_equal(
            por_modelo[MODELOS[0]]["partition"], por_modelo[MODELOS[1]]["partition"]
        )
        comparacion = {"partitions_equal": iguales, "hypotheses": total}
    m.datos.setdefault("comparison", {})["grouping"] = {
        "status": "ok" if comparacion else "parcial",
        "by_model": por_modelo, "comparison": comparacion,
    }
    m.etapa("comparacion_agrupacion", "ok" if comparacion else "parcial",
            time.perf_counter() - inicio)


async def comparar_terminos(m: Medicion, res: ResultadoBase, mock: bool) -> None:
    """Planificación de términos del Agente 05 con cada modelo, mismas hipótesis."""
    inicio = time.perf_counter()
    if res.nav_input is None:
        m.datos.setdefault("comparison", {})["terms"] = {
            "status": "omitida", "reason": "la pasada base no llegó a armar la entrada del Agente 05",
        }
        m.etapa("comparacion_terminos", "omitida", 0.0)
        return
    entrada = res.nav_input

    async def rama(modelo: str) -> dict:
        planes, estado = await TrialNavigatorAgent()._plan_terms(entrada)
        terminos: dict[int, list[str]] = {}
        for plan in planes:
            # Identidad, no igualdad: `_plan_terms` toma la candidata de la lista.
            indice = next(i for i, c in enumerate(entrada.candidates) if c is plan.candidate)
            terminos[indice] = plan.terms
        return {"terms": {str(i): t for i, t in terminos.items()},
                "_terms_int": terminos, "planning_status": estado,
                "outcome": f"{estado}, {len(terminos)} candidata(s) planificada(s)"}

    por_modelo = await _comparar_por_modelo(m.carpeta, mock, "agente05_planificacion_terminos", rama)

    comparacion = None
    if all(r["status"] == "ok" for r in por_modelo.values()):
        comparacion = medicion.compare_terms(
            por_modelo[MODELOS[0]]["_terms_int"], por_modelo[MODELOS[1]]["_terms_int"]
        )
    for r in por_modelo.values():
        r.pop("_terms_int", None)  # auxiliar con claves enteras, no serializable igual
    m.datos.setdefault("comparison", {})["terms"] = {
        "status": "ok" if comparacion else "parcial",
        "by_model": por_modelo, "comparison": comparacion,
    }
    m.etapa("comparacion_terminos", "ok" if comparacion else "parcial",
            time.perf_counter() - inicio)


async def comparar_evaluacion(m: Medicion, res: ResultadoBase, mock: bool) -> None:
    """Evaluación de compatibilidad con cada modelo, sobre los mismos ensayos."""
    inicio = time.perf_counter()
    trials: list[ClinicalTrial] = res.navigation.trials if res.navigation else []
    if res.nav_input is None or not trials:
        m.datos.setdefault("comparison", {})["evaluation"] = {
            "status": "omitida",
            "reason": "la pasada base no encontró ensayos candidatos que evaluar",
        }
        m.etapa("comparacion_evaluacion", "omitida", 0.0)
        return
    entrada = res.nav_input

    async def rama(modelo: str) -> dict:
        evaluaciones, estado, descartadas = await TrialNavigatorAgent()._evaluate(entrada, trials)
        etiquetas = {nct: e.compatibility for nct, e in evaluaciones.items()}
        return {"labels": etiquetas, "evaluation_status": estado,
                "discarded_evaluations": descartadas, "trials_sent": len(trials),
                "outcome": f"{estado}, {len(etiquetas)}/{len(trials)} evaluado(s), "
                           f"{descartadas} descartada(s) por validación"}

    por_modelo = await _comparar_por_modelo(
        m.carpeta, mock, "agente05_evaluacion_compatibilidad", rama
    )

    comparacion = None
    if all(r["status"] == "ok" for r in por_modelo.values()):
        comparacion = medicion.compare_labels(
            por_modelo[MODELOS[0]]["labels"], por_modelo[MODELOS[1]]["labels"]
        )
    m.datos.setdefault("comparison", {})["evaluation"] = {
        "status": "ok" if comparacion else "parcial",
        "by_model": por_modelo, "comparison": comparacion,
    }
    m.etapa("comparacion_evaluacion", "ok" if comparacion else "parcial",
            time.perf_counter() - inicio)


# ── Derivados de la pasada base ───────────────────────────────────────────────

def rondas_3_y_4(report: Report | None) -> dict:
    """Cambio entre las Rondas 3 y 4, o el motivo por el que no se puede medir."""
    if report is None:
        return {"available": False, "reason": "la pasada base no produjo el reporte del debate"}
    por_numero = {r.round_number: r for r in report.debate_rounds}
    if 3 not in por_numero or 4 not in por_numero:
        return {"available": False,
                "reason": "el Report no conserva las Rondas 3 y 4 (el debate se omitió: "
                          "menos de 2 agentes produjeron hipótesis)"}
    resultado = medicion.compare_rounds(
        por_numero[3].agent_outputs, por_numero[4].agent_outputs
    )
    return {"available": True, **resultado}


# ── Punto de entrada ──────────────────────────────────────────────────────────

async def correr(carpeta: Path, mock: bool, grabar: bool = False) -> int:
    m = Medicion(carpeta, mock)
    presupuestos = dict(model_tasks.TASK_BUDGETS)
    res = ResultadoBase()

    # El grabador se abre solo para la pasada base y solo en corrida real: la
    # comparación repite tareas con otros modelos y en mock no hay nada que grabar.
    token_grabador = None
    if grabar and mock:
        print("[medir_costos] --grabar: en modo mock no hay respuestas reales que "
              "grabar; no se escribe grabacion.json.", file=sys.stderr)
    elif grabar:
        preservar_grabacion_anterior(carpeta)
        token_grabador = recorder.open_recorder()

    # Pasada base, en su propio registro: costos.jsonl.
    token = usage_telemetry.open_registry()
    registro = usage_telemetry.current()
    inicio = time.perf_counter()
    error_base: str | None = None
    try:
        await pasada_base(res)
    except Exception as exc:  # se conserva lo pagado y se sigue con lo que haya
        error_base = _error(exc)
        print(f"[medir_costos] la pasada base se interrumpió ({error_base}); "
              "se miden los pasos que sí corrieron.", file=sys.stderr)
    finally:
        espera = time.perf_counter() - inicio
        usage_telemetry.close_registry(token, output_path=carpeta / "costos.jsonl", mock=mock)
        if token_grabador is not None:
            # Aunque la pasada falle a mitad de camino: lo ya pagado no se pierde.
            entradas = recorder.close_recorder(
                token_grabador, output_path=carpeta / "grabacion.json"
            )
            print(f"[medir_costos] grabación: {len(entradas or [])} respuesta(s) en "
                  f"{carpeta / 'grabacion.json'}", file=sys.stderr)
    llamadas = list(registro.calls) if registro else []

    m.datos["base"] = {
        "step_seconds": res.tiempos,
        "totals": medicion.summarize_totals(llamadas, round(espera, 3)),
        "tasks": medicion.summarize_tasks(llamadas, presupuestos),
        "agents": medicion.summarize_agents(llamadas),
    }
    if res.report is not None:
        m.datos["base"]["pipeline"] = {
            "hypotheses_final": len(res.report.hypotheses),
            "retrieved_articles": len(res.report.retrieved_articles),
            "debate_rounds": len(res.report.debate_rounds),
            "arbiter_status": res.arbitration.summary.status.value if res.arbitration else None,
            "consensus_groups": len(res.arbitration.consensus) if res.arbitration else None,
            "trials": len(res.navigation.trials) if res.navigation else None,
            "trial_planning": res.navigation.summary.planificacion if res.navigation else None,
            "trial_evaluation": res.navigation.summary.evaluacion if res.navigation else None,
        }
    m.datos["debate_rounds_3_4"] = rondas_3_y_4(res.report)
    m.etapa("pasada_base", "error" if error_base else "ok", espera, error_base)

    # Comparación: cada rama es independiente de las otras.
    for rama in (comparar_agrupacion, comparar_terminos, comparar_evaluacion):
        try:
            await rama(m, res, mock)
        except Exception as exc:  # defensa final: la rama ya atrapa sus fallos
            m.etapa(rama.__name__, "error", 0.0, _error(exc))

    # El mapa de producción tiene que haber quedado como estaba.
    if dict(model_tasks.TASK_BUDGETS) != presupuestos:
        model_tasks.TASK_BUDGETS.clear()
        model_tasks.TASK_BUDGETS.update(presupuestos)
        print("[medir_costos] ADVERTENCIA: TASK_BUDGETS quedó alterado y se restauró.",
              file=sys.stderr)

    m.guardar()
    print(f"[medir_costos] listo: {carpeta}", file=sys.stderr)
    return 1 if error_base else 0


def main() -> int:
    """
    Corrida real: pasada base (19 llamadas: PICO 1, biomarcadores 1, Ronda 1 x3,
    críticas x3, revisiones R3 y R4 x6, agrupación 1, veredictos 1, Agente 05 x2
    y la recitación, de 1 a 3 según cuántos agentes tengan hipótesis sin
    respaldo) y comparación (6 llamadas: 3 ramas x 2 modelos).
    """
    parser = argparse.ArgumentParser(description="Medición de costos del pipeline NEXUS.")
    parser.add_argument("--mock", action="store_true",
                        help=f"activa {ENV_VAR}: recorrido completo sin llamar al LLM")
    parser.add_argument("--grabar", action="store_true",
                        help="guarda las respuestas crudas del modelo de la pasada base en "
                             "grabacion.json (solo corrida real)")
    parser.add_argument("--salida", type=Path, default=None,
                        help="carpeta de salida (por defecto output/medicion_costos[/mock])")
    args = parser.parse_args()

    if args.mock:
        os.environ[ENV_VAR] = "1"
    elif is_mock_active():
        print(f"ERROR: {ENV_VAR} está activo (¿en el .env?) pero falta --mock. "
              "Una corrida real no puede usar respuestas grabadas: desactivá la "
              "variable o pasá --mock.", file=sys.stderr)
        return 2
    elif not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY no está configurada. Definila en el .env para una "
              "corrida real, o usá --mock para probar el recorrido sin cuota.",
              file=sys.stderr)
        return 2

    carpeta = args.salida or (SALIDA_REAL / "mock" if args.mock else SALIDA_REAL)
    return asyncio.run(correr(carpeta, args.mock, args.grabar))


if __name__ == "__main__":
    sys.exit(main())
