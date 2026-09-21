"""
Modelos de datos del Agente 04 (Árbitro Verificador).

El debate entrega hoy una concatenación plana de las hipótesis de cada agente:
la misma afirmación aparece repetida con distinta redacción y en ningún lado
consta que tres agentes coincidieron ni que un cuarto la contradijo. El Árbitro
agrupa esas hipótesis en un **consenso** y emite un veredicto por grupo.

`ConsensusHypothesis` **envuelve** a `Hypothesis` en vez de reemplazarla: la
clasificación EBM de `pipeline/evidence.py` sigue recibiendo `Hypothesis` y no
cambia de firma.

Agrupar nunca descarta: toda hipótesis que entrega el debate cae en exactamente
un grupo, cualquiera sea su nivel de evidencia o su estado bibliográfico.
"""

from enum import Enum

from pydantic import BaseModel

from .hypothesis import Hypothesis
from .report import Critique


class ArbitrationStatus(str, Enum):
    """Resultado del arbitraje como paso del pipeline."""

    OK = "ok"                # El agrupamiento asistido por el LLM se completó
    DEGRADADO = "degradado"  # Falló: cada hipótesis quedó como su propio grupo
    SIN_HIPOTESIS = "sin_hipotesis"  # El debate no entregó hipótesis que arbitrar


class RecitationOutcome(str, Enum):
    """Qué pasó con una hipótesis en la ronda de recitación (Ronda 5)."""

    NO_APLICA = "no_aplica"    # No entró en la recitación
    MEJORADA = "mejorada"      # Recitó y consiguió al menos una fuente verificada
    SIN_CAMBIO = "sin_cambio"  # Recitó y sigue sin respaldo verificable
    FALLIDA = "fallida"        # La recitación de ese agente falló


class Contradiction(BaseModel):
    """
    Objeción de un agente contra una hipótesis del consenso, sin resolver.

    Sale de las críticas de la Ronda 2 que el agente criticado no incorporó en
    sus revisiones. Se documenta aunque no se resuelva: el reporte no debe
    presentar como consenso unánime algo que recibió una objeción de peso.
    """

    from_agent_id: str
    from_agent_name: str
    severity: str           # "HIGH" | "MEDIUM" | "LOW", como en Critique
    critique_text: str
    target_hypothesis: str  # texto de la hipótesis criticada, como la citó el crítico
    alternative: str | None = None


class ConsensusHypothesis(BaseModel):
    """
    Una hipótesis del consenso: un grupo de hipótesis equivalentes del debate.

    `hypothesis` es la representativa, elegida por regla determinista (mejor
    estado bibliográfico → mejor nivel efectivo → menor ID de agente) y **no**
    redactada por el LLM: así cada hipótesis del reporte es trazable a un agente
    concreto. `grouped` conserva todas las del grupo, incluida la representativa.
    """

    hypothesis: Hypothesis
    grouped: list[Hypothesis] = []
    supporting_agents: list[str] = []   # nombres de los agentes que la sostienen
    refuting_agents: list[str] = []     # nombres de los que la objetaron sin ceder
    contradictions: list[Contradiction] = []
    verdict: str = ""                   # veredicto del Árbitro, en lenguaje llano
    recitation: RecitationOutcome = RecitationOutcome.NO_APLICA

    @property
    def support_count(self) -> int:
        """Cuántos agentes sostienen la hipótesis. Pesa en el orden del reporte."""
        return len(self.supporting_agents)


class ArbitrationInput(BaseModel):
    """
    Entrada del Árbitro: todo lo que produjo el debate, ya verificado.

    Contrato neutral, igual que `TrialNavigationInput` del Agente 05: el agente
    no conoce el `Report` ni el router.
    """

    hypotheses: list[Hypothesis] = []
    critiques: list[Critique] = []
    # Hipótesis por agente en la primera y la última ronda, para decidir si un
    # agente cedió ante una crítica. Clave: agent_id.
    round_1_by_agent: dict[str, list[Hypothesis]] = {}
    final_by_agent: dict[str, list[Hypothesis]] = {}
    agent_names: dict[str, str] = {}  # agent_id → nombre legible


class RecitationSummary(BaseModel):
    """Qué produjo la Ronda 5. Se reporta aunque no haya mejorado nada."""

    recited: int = 0            # hipótesis que entraron en la recitación
    improved: int = 0           # las que pasaron a respaldada gracias a ella
    rejected_pmids: int = 0     # fuentes descartadas por PMID fuera del conjunto
    failed_agents: list[str] = []  # agentes cuya recitación falló
    executed: bool = False      # si la ronda llegó a ejecutarse


class ArbitrationSummary(BaseModel):
    """
    Resumen del arbitraje para el reporte exportado.

    `rag_overlap` es el dato que justifica que el Árbitro exista: cuántas de las
    fuentes que citaron los agentes corresponden a artículos que el RAG les había
    puesto en el prompt. Medido en 0/15 en la corrida del 2026-09-15.
    """

    status: ArbitrationStatus = ArbitrationStatus.OK
    input_hypotheses: int = 0       # las que entregó el debate
    consensus_hypotheses: int = 0   # los grupos resultantes
    contradictions: int = 0
    recitation: RecitationSummary = RecitationSummary()
    cited_sources: int = 0          # fuentes citadas por los agentes, únicas
    rag_overlap: int = 0            # cuántas de esas estaban entre las recuperadas
    retrieved_articles: int = 0     # artículos que el RAG ofreció
    discarded_references: int = 0   # referencias que el LLM inventó y se descartaron


class ArbitrationResult(BaseModel):
    """Salida del Árbitro: el consenso más el resumen de cómo se llegó a él."""

    consensus: list[ConsensusHypothesis] = []
    summary: ArbitrationSummary = ArbitrationSummary()
