"""
El formato de respuesta lo decide el pedido de cada ronda, no el prompt de sistema.

Los prompts de sistema de los Agentes 01, 02 y 03 fijan el JSON de `hypotheses`
(Ronda 1 y revisiones), y la Ronda 2 pide `critiques`. En la corrida real del
2026-11-17 con la arquitectura de destino, GPT-6.1 Sol (Agente 02) priorizó el
prompt de sistema y respondió la crítica con `hypotheses`: 0 críticas suyas
llegaron al debate. Claude y Gemini siguieron el pedido.
"""

from __future__ import annotations

import pytest

from backend.agents.agent_01_literature import LiteratureAnalystAgent
from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
from backend.agents.agent_03_clinical import ClinicalConsultantAgent
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.report import AgentOutput

AGENTES = (LiteratureAnalystAgent, GenomicsSpecialistAgent, ClinicalConsultantAgent)


def _salida(agent_id: str, nombre: str) -> AgentOutput:
    """Salida mínima de un agente con una hipótesis."""
    return AgentOutput(
        agent_id=agent_id,
        agent_name=nombre,
        hypotheses=[
            Hypothesis(
                text=f"Hipótesis del agente {agent_id}",
                priority=Priority.MEDIUM,
                evidence_level=EvidenceLevel.III,
                rationale="Fundamento de prueba",
                sources=[],
            )
        ],
        raw_response="{}",
    )


@pytest.mark.parametrize("clase", AGENTES, ids=lambda c: c.__name__)
def test_el_prompt_de_sistema_cede_el_formato_al_pedido(clase) -> None:
    """El formato de hipótesis es el de base: un pedido con otro formato manda."""
    prompt = clase.SYSTEM_PROMPT
    assert "Si el mensaje pide otro formato" in prompt
    assert "respondé con el formato que pide el mensaje" in prompt


@pytest.mark.parametrize("clase", AGENTES, ids=lambda c: c.__name__)
def test_el_pedido_de_critica_prohibe_la_clave_de_hipotesis(clase, monkeypatch) -> None:
    """La Ronda 2 dice explícitamente que no se responda con `hypotheses`."""
    agente = clase()
    pedidos: list[str] = []

    def falso_llm(mensaje: str, *, task: str) -> str:
        pedidos.append(mensaje)
        return '{"critiques": []}'

    monkeypatch.setattr(agente, "_call_llm", falso_llm)
    propia = _salida(agente.AGENT_ID, agente.AGENT_NAME)
    otros = [_salida(i, f"Agente {i}") for i in ("01", "02", "03") if i != agente.AGENT_ID]

    agente.critique("Caso de prueba.", propia, otros)

    assert len(pedidos) == 1
    assert 'No uses la clave "hypotheses"' in pedidos[0]
    assert '"critiques"' in pedidos[0]
