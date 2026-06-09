"""
Orquestador del pipeline NEXUS — Ronda 1.

Responsabilidades:
  1. Normalizar el texto clínico extraído.
  2. Construir la síntesis PICO (contexto estructurado para los agentes).
  3. Extraer biomarcadores e historial terapéutico.
  4. Ejecutar Agentes 01 y 03 en PARALELO (asyncio.gather + to_thread).
  5. Consolidar los outputs en un Report.

Los agentes usan el cliente Groq sincrónico; asyncio.to_thread() los corre
en un thread pool sin bloquear el event loop, logrando verdadera concurrencia
dentro del proceso.
"""

import asyncio
import sys
from typing import Sequence

from ..agents.agent_01_literature import LiteratureAnalystAgent
from ..agents.agent_03_clinical import ClinicalConsultantAgent
from ..agents.base_agent import BaseAgent
from ..ingestion.biomarker_extractor import extract as extract_biomarkers
from ..ingestion.normalizer import normalize
from ..models.case import ClinicalCase
from ..models.hypothesis import Hypothesis
from ..models.report import AgentOutput, Report
from . import pico


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run_agent_async(agent: BaseAgent, context: str) -> AgentOutput:
    """Ejecuta un agente sincrónico en un thread pool para no bloquear el loop."""
    return await asyncio.to_thread(agent.run, context)


def _build_sources_summary(hypotheses: list[Hypothesis]) -> dict[str, int]:
    """Cuenta fuentes únicas por nivel de evidencia."""
    summary: dict[str, int] = {"I": 0, "II": 0, "III": 0}
    seen_pmids: set[str] = set()
    for h in hypotheses:
        for source in h.sources:
            key = source.pmid or source.title
            if key and key not in seen_pmids:
                seen_pmids.add(key)
                summary[h.evidence_level.value] += 1
    return summary


# ── Ronda 1: análisis paralelo ─────────────────────────────────────────────────

async def run_round_1(case: ClinicalCase) -> Report:
    """
    Ronda 1: corre Agentes 01 y 03 en paralelo sobre el contexto PICO.

    Precondición: case.pico debe estar completo (llamar pico.build() antes).
    Si un agente falla, se registra en stderr y el pipeline continúa
    con los agentes restantes.
    """
    if case.pico is None:
        raise ValueError("case.pico es None — llamar a pico.build() antes de run_round_1().")

    context = pico.format_for_agents(case.pico)
    agents: Sequence[BaseAgent] = [LiteratureAnalystAgent(), ClinicalConsultantAgent()]

    results = await asyncio.gather(
        *(_run_agent_async(agent, context) for agent in agents),
        return_exceptions=True,
    )

    valid_outputs: list[AgentOutput] = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            print(
                f"[NEXUS] Agente {agent.AGENT_NAME} (ID:{agent.AGENT_ID}) falló "
                f"en Ronda 1: {result}",
                file=sys.stderr,
            )
        else:
            valid_outputs.append(result)

    if not valid_outputs:
        raise RuntimeError("Todos los agentes fallaron en Ronda 1. Verificá la API key y el modelo.")

    all_hypotheses = [h for output in valid_outputs for h in output.hypotheses]

    return Report(
        case_summary=case.pico.clinical_narrative,
        hypotheses=all_hypotheses,
        agent_outputs=valid_outputs,
        sources_summary=_build_sources_summary(all_hypotheses),
    )


# ── Pipeline completo (entrada sincrónica) ─────────────────────────────────────

def run(clinical_text: str) -> Report:
    """
    Ejecuta el pipeline completo de forma sincrónica:
      normalización → PICO → biomarcadores → Ronda 1 (paralelo).

    Uso desde scripts y tests de integración.
    En FastAPI usar run_round_1() directamente desde un endpoint async.
    """
    normalized = normalize(clinical_text)

    case = ClinicalCase(raw_text=normalized)
    case = pico.build(case)
    case.biomarkers = extract_biomarkers(normalized)

    return asyncio.run(run_round_1(case))
