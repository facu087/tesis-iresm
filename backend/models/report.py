from pydantic import BaseModel
from .hypothesis import Hypothesis


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
