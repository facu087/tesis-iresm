"""
Tests de texto de los prompts de citas (tarjeta #92, citas ancladas al RAG).

Verifican que la regla esté escrita donde corresponde, no la conducta del
modelo: esa se mide con una corrida real (`scripts/medir_costos.py`).
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.agent_01_literature import LiteratureAnalystAgent
from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
from backend.agents.agent_03_clinical import ClinicalConsultantAgent
from backend.agents.base_agent import REGLA_CITAS
from backend.models.report import AgentOutput
from backend.rag.retriever import PubMedRetriever, RetrievedArticle

REGLA = (
    "Solo podés citar PMIDs que figuren en el bloque LITERATURA CIENTÍFICA del contexto. "
    "Si ningún artículo de ese bloque respalda la hipótesis, dejá `sources` vacío y usá "
    '`evidence_level: "III"`.'
)
PMID_NUMERICO = re.compile(r'"pmid":\s*"\d+')
AGENTES = [LiteratureAnalystAgent, GenomicsSpecialistAgent, ClinicalConsultantAgent]
JSON_VACIO = (
    '{"hypotheses": [{"text": "h", "priority": "LOW", "evidence_level": "III", '
    '"rationale": "r", "sources": [], "case_genetic_findings": []}]}'
)


def _sin_saltos(texto: str) -> str:
    """Los prompts parten la regla en varias líneas; se compara sin saltos."""
    return " ".join(texto.split())


def test_la_constante_es_la_regla_pedida():
    assert REGLA_CITAS == REGLA


@pytest.mark.parametrize("agente", AGENTES, ids=lambda a: a.AGENT_ID)
def test_system_prompt_contiene_la_regla(agente):
    assert REGLA in _sin_saltos(agente.SYSTEM_PROMPT)


@pytest.mark.parametrize("agente", AGENTES, ids=lambda a: a.AGENT_ID)
def test_system_prompt_sin_pmid_numerico_de_ejemplo(agente):
    assert not PMID_NUMERICO.search(agente.SYSTEM_PROMPT)
    assert '"pmid": "PMID del bloque de literatura"' in agente.SYSTEM_PROMPT


@pytest.mark.parametrize("agente", AGENTES, ids=lambda a: a.AGENT_ID)
def test_pedido_de_revision_contiene_la_regla(agente):
    instancia = agente()
    own = AgentOutput(agent_id=instancia.AGENT_ID, agent_name="x", hypotheses=[])
    with patch.object(instancia, "_call_llm", return_value=JSON_VACIO) as llamada:
        instancia.revise("contexto del caso", own, [])
    prompt = llamada.call_args.args[0]
    assert REGLA in _sin_saltos(prompt)


def _retriever_con(articulos: list[RetrievedArticle]) -> PubMedRetriever:
    retriever = PubMedRetriever(collection=MagicMock())
    retriever.search = MagicMock(return_value=articulos)
    return retriever


def test_bloque_del_rag_cierra_con_la_instruccion_obligatoria():
    articulo = RetrievedArticle(
        pmid="11111111", title="Hereditary transthyretin amyloidosis",
        journal="Neurology", year="2020", authors="Autor A", url="",
        excerpt="Resumen.", relevance_score=0.8,
    )
    contexto, _ = _retriever_con([articulo]).get_context_with_articles("query")
    assert contexto.rstrip().endswith(
        "OBLIGATORIO: citá solo PMIDs de esta lista. Cualquier otro PMID se descarta."
    )


def test_bloque_del_rag_sin_articulos_pide_sources_vacio():
    contexto, articulos = _retriever_con([]).get_context_with_articles("query")
    assert articulos == []
    assert "dejá `sources` vacío" in contexto
