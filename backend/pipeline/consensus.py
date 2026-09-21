"""
Lógica determinista del Agente 04 (Árbitro Verificador).

Todo lo que decide algo vive acá, fuera del LLM: la validación de la partición
que propone el modelo, la elección del texto representativo de cada grupo, la
consolidación de fuentes, la detección de contradicciones y la métrica de
solapamiento entre la literatura recuperada y la citada.

El modelo solo agrupa (devolviendo índices, nunca texto) y redacta fundamentos.
Cualquier cosa que llegue de él pasa por este módulo antes de usarse.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..models.hypothesis import Hypothesis
from ..models.report import RetrievedArticleRef


def cited_pmids(hypotheses: Iterable[Hypothesis]) -> set[str]:
    """Devuelve los PMIDs únicos que citaron los agentes en sus hipótesis."""
    return {
        source.pmid
        for hypothesis in hypotheses
        for source in hypothesis.sources
        if source.pmid
    }


def rag_overlap(
    hypotheses: Sequence[Hypothesis],
    retrieved: Sequence[RetrievedArticleRef],
) -> tuple[int, int]:
    """
    Mide cuántas de las citas de los agentes salieron de la literatura ofrecida.

    Es el número que justifica que el Árbitro exista: en la corrida del
    2026-09-15 sobre el caso de la tesis dio 0 de 15, o sea que los agentes
    ignoraron por completo los artículos que el RAG les puso en el prompt y
    citaron PMIDs inventados.

    Args:
        hypotheses: Hipótesis tal como las entregó el debate.
        retrieved:  Artículos que el RAG recuperó y ofreció en la Ronda 1.

    Returns:
        (solapamiento, total de PMIDs citados únicos). Con `retrieved` vacío el
        solapamiento es 0: no se le puede reprochar al agente no haber citado
        una literatura que nunca se le ofreció, pero tampoco se cuenta a favor.
    """
    citados = cited_pmids(hypotheses)
    ofrecidos = {article.pmid for article in retrieved if article.pmid}
    return len(citados & ofrecidos), len(citados)
