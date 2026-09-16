"""
Motor de debate adversarial — Rondas 2 a 4.

Protocolo:
  Ronda 2 — Crítica cruzada (paralelo):
    Cada agente recibe los outputs de los demás y genera críticas específicas.

  Ronda 3 — Primera revisión (paralelo):
    Cada agente recibe las críticas dirigidas a sus hipótesis y responde:
    ajusta donde corresponde o defiende con argumentación.

  Ronda 4 — Revisión final (paralelo):
    Segunda iteración de revisión. Los agentes refinan su posición
    considerando el acumulado del debate.

Al finalizar se detectan las divergencias: hipótesis que recibieron
críticas HIGH y fueron mantenidas sin cambio significativo.
"""

import asyncio
import sys

from ..agents.agent_01_literature import LiteratureAnalystAgent
from ..agents.agent_02_genomics import GenomicsSpecialistAgent
from ..agents.agent_03_clinical import ClinicalConsultantAgent
from ..agents.base_agent import BaseAgent
from ..models.case import ClinicalCase
from ..models.report import AgentOutput, Critique, DebateRound, Report
from . import genomic_context as gc_module
from . import pico


# ── Helpers ────────────────────────────────────────────────────────────────────

def _critiques_for(agent_id: str, all_critiques: list[Critique]) -> list[Critique]:
    """Filtra las críticas dirigidas a un agente específico."""
    return [c for c in all_critiques if c.target_agent_id == agent_id]


def _detect_divergences(
    round_2_critiques: list[Critique],
    final_outputs: list[AgentOutput],
) -> list[str]:
    """
    Documenta hipótesis que recibieron crítica HIGH y fueron mantenidas.
    Heurística: si el texto de la hipótesis final comparte más del 60%
    de palabras con la hipótesis criticada, se considera mantenida.
    """
    divergences = []
    final_texts = {
        h.text.lower()
        for output in final_outputs
        for h in output.hypotheses
    }

    for critique in round_2_critiques:
        if critique.severity != "HIGH":
            continue
        target_words = set(critique.target_hypothesis.lower().split())
        maintained = any(
            len(target_words & set(ft.split())) / max(len(target_words), 1) > 0.6
            for ft in final_texts
        )
        if maintained:
            divergences.append(
                f"Agente {critique.target_agent_id} mantuvo hipótesis criticada "
                f"[HIGH] por {critique.from_agent_name}: "
                f'"{critique.target_hypothesis[:120]}"'
            )
    return divergences


# ── Ejecución asíncrona por ronda ─────────────────────────────────────────────

async def _run_critique_async(
    agent: BaseAgent,
    context: str,
    own_output: AgentOutput,
    other_outputs: list[AgentOutput],
) -> list[Critique]:
    return await asyncio.to_thread(agent.critique, context, own_output, other_outputs)


async def _run_revise_async(
    agent: BaseAgent,
    context: str,
    own_output: AgentOutput,
    critiques_received: list[Critique],
) -> AgentOutput:
    return await asyncio.to_thread(agent.revise, context, own_output, critiques_received)


# ── Rondas del debate ──────────────────────────────────────────────────────────

async def _round_2(
    agents: list[BaseAgent],
    context: str,
    outputs_by_id: dict[str, AgentOutput],
) -> DebateRound:
    """Ronda 2: cada agente critica los outputs de los demás (paralelo)."""
    tasks = []
    for agent in agents:
        own = outputs_by_id[agent.AGENT_ID]
        others = [o for aid, o in outputs_by_id.items() if aid != agent.AGENT_ID]
        tasks.append(_run_critique_async(agent, context, own, others))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_critiques: list[Critique] = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            print(
                f"[NEXUS] Agente {agent.AGENT_NAME} falló en Ronda 2: {result}",
                file=sys.stderr,
            )
        else:
            all_critiques.extend(result)

    return DebateRound(round_number=2, critiques=all_critiques)


async def _round_revision(
    round_number: int,
    agents: list[BaseAgent],
    context: str,
    current_outputs: dict[str, AgentOutput],
    critiques: list[Critique],
) -> DebateRound:
    """Ronda 3 o 4: cada agente revisa sus hipótesis en respuesta a críticas (paralelo)."""
    tasks = []
    for agent in agents:
        own = current_outputs[agent.AGENT_ID]
        received = _critiques_for(agent.AGENT_ID, critiques)
        tasks.append(_run_revise_async(agent, context, own, received))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    revised_outputs: list[AgentOutput] = []
    updated: dict[str, AgentOutput] = dict(current_outputs)

    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            print(
                f"[NEXUS] Agente {agent.AGENT_NAME} falló en Ronda {round_number}: {result}",
                file=sys.stderr,
            )
            revised_outputs.append(current_outputs[agent.AGENT_ID])
        else:
            revised_outputs.append(result)
            updated[agent.AGENT_ID] = result

    return DebateRound(round_number=round_number, agent_outputs=revised_outputs), updated


# ── Punto de entrada ───────────────────────────────────────────────────────────

async def run_debate(case: ClinicalCase, round_1_report: Report) -> Report:
    """
    Ejecuta las rondas 2-4 del debate adversarial.

    Args:
        case:            ClinicalCase con pico ya construido.
        round_1_report:  Report con los agent_outputs de Ronda 1.

    Returns:
        Report completo con debate_rounds, hipótesis finales y divergencias.
    """
    if case.pico is None:
        raise ValueError("case.pico es None — ejecutar pico.build() antes del debate.")
    if not round_1_report.agent_outputs:
        raise ValueError("round_1_report no tiene agent_outputs — ejecutar Ronda 1 primero.")

    context = pico.format_for_agents(case.pico)

    # Reutilizar el perfil genómico del orquestador; si falta, construirlo sin red
    genomic_ctx = case.genomic_context or gc_module.build(case)
    agents: list[BaseAgent] = [
        LiteratureAnalystAgent(),
        GenomicsSpecialistAgent(genomic_context=genomic_ctx),
        ClinicalConsultantAgent(),
    ]

    # Indexar outputs de Ronda 1 por agent_id
    outputs_by_id: dict[str, AgentOutput] = {
        o.agent_id: o for o in round_1_report.agent_outputs
    }

    # Solo participan del debate los agentes que produjeron output en Ronda 1
    agents = [a for a in agents if a.AGENT_ID in outputs_by_id]
    absent = [
        f"{a.AGENT_NAME} (ID:{a.AGENT_ID})"
        for a in [LiteratureAnalystAgent(), GenomicsSpecialistAgent(), ClinicalConsultantAgent()]
        if a.AGENT_ID not in outputs_by_id
    ]
    if absent:
        print(
            f"[NEXUS] Debate sin {', '.join(absent)}: no produjeron hipótesis en la Ronda 1.",
            file=sys.stderr,
        )

    if not agents:
        raise RuntimeError(
            "Ningún agente del debate coincide con los outputs de la Ronda 1 "
            f"(IDs recibidos: {sorted(outputs_by_id)}). Revisá la numeración de agentes."
        )

    if len(agents) < 2:
        print(
            "[NEXUS] Debate omitido: se necesitan al menos 2 agentes y quedó "
            f"{len(agents)}. Se devuelven las hipótesis de la Ronda 1.",
            file=sys.stderr,
        )
        return Report(
            case_summary=round_1_report.case_summary,
            hypotheses=round_1_report.hypotheses,
            agent_outputs=round_1_report.agent_outputs,
            debate_rounds=[],
            divergences=[],
            sources_summary=round_1_report.sources_summary,
            absent_agents=absent,
        )

    # ── Ronda 2: críticas ─────────────────────────────────────────
    round_2 = await _round_2(agents, context, outputs_by_id)

    # ── Ronda 3: primera revisión ─────────────────────────────────
    round_3, outputs_r3 = await _round_revision(3, agents, context, outputs_by_id, round_2.critiques)

    # ── Ronda 4: revisión final ───────────────────────────────────
    round_4, outputs_r4 = await _round_revision(4, agents, context, outputs_r3, round_2.critiques)

    # ── Consolidar resultado ───────────────────────────────────────
    final_hypotheses = [h for o in outputs_r4.values() for h in o.hypotheses]
    divergences = _detect_divergences(round_2.critiques, list(outputs_r4.values()))

    sources_summary: dict[str, int] = {"I": 0, "II": 0, "III": 0}
    seen: set[str] = set()
    for h in final_hypotheses:
        for s in h.sources:
            key = s.pmid or s.title
            if key and key not in seen:
                seen.add(key)
                sources_summary[h.evidence_level.value] += 1

    return Report(
        case_summary=round_1_report.case_summary,
        hypotheses=final_hypotheses,
        agent_outputs=round_1_report.agent_outputs,
        debate_rounds=[round_2, round_3, round_4],
        divergences=divergences,
        sources_summary=sources_summary,
    )
