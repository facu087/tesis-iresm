"""
Ronda 5 — recitación acotada (Agente 04).

En la corrida del 2026-09-15 sobre el caso de la tesis, **ninguno** de los PMIDs
que citaron los agentes coincidió con los que el RAG les había puesto en el
prompt, y las 15 citas resultaron discordantes contra PubMed. Los agentes no
usan la literatura que se les recupera: la inventan.

La recitación es el intento acotado de corregir eso. A las hipótesis que
quedaron sin respaldo se les devuelve el motivo concreto por el que falló cada
cita, junto con los artículos que el RAG había recuperado, y se les pide volver
a citar **sobre esa literatura real**. Los PMIDs nuevos se validan contra el
conjunto ofrecido antes de gastar una consulta a PubMed.

Una sola iteración. Lo que siga sin respaldo queda especulativo y se documenta:
el criterio de parada NO es que toda hipótesis alcance respaldo verificable
—con 15 de 15 discordantes eso no terminaría nunca— sino que la ronda corra una
vez. Ninguna hipótesis se descarta.

Este módulo es determinista y sin red: decide *qué* se recita y *qué se acepta*
de lo recitado. Quien habla con los agentes es `agents/agent_04_arbiter.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..models.arbitration import ConsensusHypothesis
from ..models.hypothesis import Hypothesis, Source
from ..models.report import RetrievedArticleRef
from .evidence import HypothesisStatus, classify_hypothesis
from .verification import SourceStatus, SourceVerification, source_key

# Motivos de fallo que se le explican al agente. Decirle *por qué* falló su cita
# es lo que le da la chance de corregir: "inventaste un PMID" y "ese PMID existe
# pero es otro artículo" se arreglan distinto.
_MOTIVOS: dict[SourceStatus, str] = {
    SourceStatus.DISCORDANTE: (
        "ese PMID existe en PubMed pero corresponde a otro artículo"
    ),
    SourceStatus.INEXISTENTE: "ese PMID no existe en PubMed",
    SourceStatus.SIN_PMID: "la referencia no declaró PMID, así que no se pudo verificar",
}


def should_recite(
    consensus: Sequence[ConsensusHypothesis],
    verifications: Mapping[str, SourceVerification],
    retrieved: Sequence[RetrievedArticleRef],
) -> bool:
    """
    Decide si la ronda de recitación tiene sentido.

    No se recita cuando:
    - No hay artículos recuperados: no habría literatura real que ofrecer, y
      pedirle al agente que cite mejor sin darle nada es pedirle que invente.
    - La verificación no pudo ejecutarse: el problema es de infraestructura, no
      de la cita, y las hipótesis quedan `pendiente`, no especulativas.
    """
    if not retrieved or not verifications:
        return False
    return bool(select(consensus, verifications))


def select(
    consensus: Sequence[ConsensusHypothesis],
    verifications: Mapping[str, SourceVerification],
) -> list[int]:
    """
    Elige qué hipótesis del consenso entran en la recitación.

    Solo las que no están `respaldada`, es decir sin ninguna fuente verificada.
    Una `pendiente` —la verificación no concluyó— queda afuera: recitar no
    arregla que PubMed no haya respondido.

    Returns:
        Índices dentro de `consensus`, en orden.
    """
    elegidas: list[int] = []
    for indice, item in enumerate(consensus):
        evaluacion = classify_hypothesis(item.hypothesis, verifications)
        if evaluacion.status is HypothesisStatus.ESPECULATIVA:
            elegidas.append(indice)
    return elegidas


def failure_reasons(
    hypothesis: Hypothesis,
    verifications: Mapping[str, SourceVerification],
) -> list[str]:
    """
    Explica, cita por cita, por qué ninguna resistió la verificación.

    Es lo que se le manda al agente junto con el pedido de recitar.
    """
    motivos: list[str] = []
    for source in hypothesis.sources:
        veredicto = verifications.get(source_key(source))
        if veredicto is None or veredicto.status is SourceStatus.VERIFICADA:
            continue
        motivo = _MOTIVOS.get(veredicto.status)
        if motivo is None:
            continue
        referencia = f"PMID {veredicto.pmid}" if veredicto.pmid else f'"{source.title}"'
        motivos.append(f"{referencia}: {motivo}")
    if not motivos and not hypothesis.sources:
        motivos.append("la hipótesis no citó ninguna referencia")
    return motivos


def allowed_pmids(retrieved: Sequence[RetrievedArticleRef]) -> set[str]:
    """PMIDs que una recitación puede citar: solo los que se le ofrecieron."""
    return {article.pmid for article in retrieved if article.pmid}


def validate_recited(
    sources: Sequence[Source],
    allowed: set[str],
) -> tuple[list[Source], int]:
    """
    Filtra las fuentes recitadas dejando solo las del conjunto ofrecido.

    Una fuente con un PMID que no se le ofreció se descarta **sin consultar
    PubMed**: ya se sabe que el agente volvió a inventar, y gastar una consulta
    para confirmarlo no aporta.

    Returns:
        (fuentes aceptadas sin repetir, cantidad descartada).
    """
    aceptadas: list[Source] = []
    vistas: set[str] = set()
    descartadas = 0

    for source in sources:
        if not source.pmid or source.pmid not in allowed:
            descartadas += 1
            continue
        if source.pmid in vistas:
            continue
        vistas.add(source.pmid)
        aceptadas.append(source)

    return aceptadas, descartadas


def improved(
    hypothesis: Hypothesis,
    verifications: Mapping[str, SourceVerification],
) -> bool:
    """True si la hipótesis ya tiene al menos una fuente verificada."""
    return (
        classify_hypothesis(hypothesis, verifications).status
        is HypothesisStatus.RESPALDADA
    )
