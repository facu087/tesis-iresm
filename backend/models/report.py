from pydantic import BaseModel
from .hypothesis import Hypothesis


class RetrievedArticleRef(BaseModel):
    """
    Artículo que el RAG recuperó y ofreció a los agentes en la Ronda 1.

    Equivalente Pydantic liviano de `rag.retriever.RetrievedArticle`, definido
    acá a propósito: importar el dataclass del RAG metería ChromaDB en la cadena
    de imports de `backend.models`, que hoy no depende de nada externo.

    El orquestador conserva estos artículos en el `Report` porque el Árbitro los
    necesita para dos cosas: medir cuántas de las citas de los agentes salieron
    de la literatura que se les ofreció, y armar la ronda de recitación sobre
    PMIDs reales.
    """

    pmid: str
    title: str
    journal: str = ""
    year: str = ""
    excerpt: str = ""


class AgentOutput(BaseModel):
    agent_id: str
    agent_name: str
    hypotheses: list[Hypothesis]
    raw_response: str | None = None


class Critique(BaseModel):
    """Crítica generada por un agente sobre la hipótesis de otro (Ronda 2)."""
    from_agent_id: str
    from_agent_name: str
    target_agent_id: str
    target_hypothesis: str   # texto de la hipótesis criticada
    critique_text: str
    severity: str            # "HIGH" | "MEDIUM" | "LOW"
    alternative: str | None = None


class DebateRound(BaseModel):
    """Resultado de una ronda del debate adversarial."""
    round_number: int
    agent_outputs: list[AgentOutput] = []  # hipótesis revisadas (rondas 3-4)
    critiques: list[Critique] = []         # críticas emitidas (ronda 2)


class Report(BaseModel):
    case_summary: str
    hypotheses: list[Hypothesis] = []
    agent_outputs: list[AgentOutput] = []  # outputs de Ronda 1
    debate_rounds: list[DebateRound] = []  # rondas 2-4
    divergences: list[str] = []
    sources_summary: dict[str, int] = {}

    # Agentes que no produjeron output en la Ronda 1 y por lo tanto quedaron
    # fuera del debate. Se deja constancia para que el reporte no presente como
    # deliberación de N agentes lo que en realidad discutieron menos.
    absent_agents: list[str] = []

    # Artículos que el RAG recuperó y puso en el contexto de la Ronda 1. Queda
    # vacío si la búsqueda semántica falló o no devolvió nada: el pipeline sigue.
    retrieved_articles: list[RetrievedArticleRef] = []
