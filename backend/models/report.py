from pydantic import BaseModel
from .hypothesis import Hypothesis


class AgentOutput(BaseModel):
    agent_id: str
    agent_name: str
    hypotheses: list[Hypothesis]
    raw_response: str | None = None


class Report(BaseModel):
    case_summary: str
    hypotheses: list[Hypothesis] = []
    agent_outputs: list[AgentOutput] = []
    divergences: list[str] = []
    sources_summary: dict[str, int] = {}
