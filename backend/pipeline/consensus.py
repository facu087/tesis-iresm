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

import unicodedata
from collections.abc import Iterable, Mapping, Sequence

from ..models.arbitration import (
    ArbitrationInput,
    ArbitrationStatus,
    ArbitrationSummary,
    ConsensusHypothesis,
    Contradiction,
)
from ..models.hypothesis import EvidenceLevel, Hypothesis, Source
from ..models.report import Critique, Report, RetrievedArticleRef
from .evidence import HypothesisStatus, classify_hypothesis
from .verification import SourceVerification, source_key

# Umbral de solapamiento de palabras para considerar que dos enunciados hablan
# de la misma hipótesis. Es el mismo 0,6 que usaba `debate._detect_divergences()`,
# que este módulo reemplaza. Heurística declarada: equivocarse de más reporta una
# contradicción que no era, que es el lado seguro.
_MIN_TEXT_MATCH = 0.60

_STOPWORDS = frozenset(
    """el la los las un una unos unas de del y o en con sin para por a al que se
    es son como mas más este esta estos estas su sus lo le les""".split()
)

# Orden de preferencia para elegir el enunciado representativo de un grupo.
_STATUS_RANK: dict[HypothesisStatus, int] = {
    HypothesisStatus.RESPALDADA: 0,
    HypothesisStatus.PENDIENTE: 1,
    HypothesisStatus.ESPECULATIVA: 2,
}
_LEVEL_RANK: dict[EvidenceLevel, int] = {
    EvidenceLevel.I: 0,
    EvidenceLevel.II: 1,
    EvidenceLevel.III: 2,
}


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


# ── Comparación de enunciados ─────────────────────────────────────────────────

def _tokens(text: str) -> set[str]:
    """Reduce un enunciado a sus palabras significativas, sin acentos ni signos."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    limpio = "".join(c.lower() if c.isalnum() else " " for c in sin_acentos)
    return {t for t in limpio.split() if len(t) > 2 and t not in _STOPWORDS}


def text_match(a: str, b: str) -> float:
    """
    Mide cuánto se solapan dos enunciados, entre 0 y 1.

    Containment sobre el conjunto más chico, igual que
    `verification._title_match_score()`: un agente puede redactar la misma
    hipótesis con más detalle que otro sin que deje de ser la misma.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


# ── 4.1 Validación de la partición propuesta por el modelo ────────────────────

def normalize_partition(groups: Sequence[Sequence[int]], total: int) -> list[list[int]]:
    """
    Valida y repara la partición de hipótesis que propuso el LLM.

    El modelo devuelve grupos como listas de índices, nunca texto (D1/D2), así
    que validarlo se reduce a chequear enteros. Reglas:

    - Un índice fuera de `range(total)` se ignora.
    - Un índice repetido queda en el primer grupo que lo reclamó.
    - Un índice que ningún grupo menciona se agrega como grupo propio.
    - Los grupos que quedan vacíos se descartan.

    Garantiza la propiedad que exige la spec: toda hipótesis cae en exactamente
    un grupo. Agrupar nunca descarta.

    Args:
        groups: Partición propuesta, como listas de índices.
        total:  Cantidad de hipótesis que se le entregaron al modelo.

    Returns:
        Partición saneada, en el orden en que la propuso el modelo, con los
        índices huérfanos agregados al final en orden creciente.
    """
    vistos: set[int] = set()
    saneados: list[list[int]] = []

    for grupo in groups:
        limpio: list[int] = []
        for indice in grupo:
            if not isinstance(indice, int) or isinstance(indice, bool):
                continue
            if 0 <= indice < total and indice not in vistos:
                vistos.add(indice)
                limpio.append(indice)
        if limpio:
            saneados.append(limpio)

    # Ninguna hipótesis puede perderse porque el modelo la haya omitido.
    for indice in range(total):
        if indice not in vistos:
            saneados.append([indice])

    return saneados


# ── 4.2 y 4.3 Armado de un grupo ──────────────────────────────────────────────

def _sort_key(
    index: int,
    entrada: ArbitrationInput,
    verifications: Mapping[str, SourceVerification],
) -> tuple[int, int, str, int]:
    """Clave de preferencia de una hipótesis para representar a su grupo."""
    hypothesis = entrada.hypotheses[index]
    evaluacion = classify_hypothesis(hypothesis, verifications)
    return (
        _STATUS_RANK[evaluacion.status],
        _LEVEL_RANK[evaluacion.effective_level],
        entrada.agent_of(index) or "￿",  # sin agente conocido va último
        index,
    )


def choose_representative(
    group: Sequence[int],
    entrada: ArbitrationInput,
    verifications: Mapping[str, SourceVerification],
) -> int:
    """
    Elige qué enunciado del grupo representa a la hipótesis de consenso.

    Regla determinista: mejor estado bibliográfico → mejor nivel efectivo →
    menor ID de agente → orden de entrega. El LLM **no** redacta este enunciado
    (D3): sale siempre de una hipótesis que un agente escribió, así que cada
    hipótesis del reporte es trazable a su autor.

    Returns:
        El índice elegido dentro de `entrada.hypotheses`.
    """
    return min(group, key=lambda i: _sort_key(i, entrada, verifications))


def merge_sources(hypotheses: Iterable[Hypothesis]) -> list[Source]:
    """
    Junta las fuentes de las hipótesis agrupadas, sin repetir.

    Deduplica por la misma clave que usa la verificación (`source_key`: el PMID,
    o el título cuando la fuente no declaró PMID), para que una referencia que
    dos agentes citaron no cuente dos veces.
    """
    vistas: set[str] = set()
    fuentes: list[Source] = []
    for hypothesis in hypotheses:
        for source in hypothesis.sources:
            clave = source_key(source)
            if clave and clave not in vistas:
                vistas.add(clave)
                fuentes.append(source)
    return fuentes


# ── 4.4 Contradicciones ───────────────────────────────────────────────────────

def _agent_conceded(critique: Critique, entrada: ArbitrationInput) -> bool:
    """
    Decide si el agente criticado incorporó la crítica o la mantuvo.

    Reemplaza a `debate._detect_divergences()`, que comparaba la hipótesis
    criticada contra **todas** las hipótesis finales de **todos** los agentes:
    bastaba que otro agente dijera algo parecido para dar por mantenida una
    hipótesis que su autor sí había corregido. Acá se mira solo al agente
    criticado, y se compara su Ronda 1 contra su ronda final.

    Devuelve True si en su salida final ya no hay nada que se parezca a lo que
    se le criticó — es decir, cedió.
    """
    finales = entrada.final_by_agent.get(critique.target_agent_id)
    if finales is None:
        # No hay rastro de la ronda final del agente: no se puede afirmar que
        # cedió, y el lado seguro es documentar la contradicción.
        return False

    return not any(
        text_match(critique.target_hypothesis, h.text) >= _MIN_TEXT_MATCH
        for h in finales
    )


def _group_for_critique(
    critique: Critique,
    groups: Sequence[Sequence[int]],
    entrada: ArbitrationInput,
) -> int | None:
    """
    Encuentra a qué grupo del consenso apunta una crítica.

    Busca el grupo que contenga la hipótesis más parecida al enunciado que el
    crítico citó. Devuelve None si ninguna llega al umbral: una crítica que no
    se puede atribuir no se inventa contra un grupo cualquiera.
    """
    mejor_score = _MIN_TEXT_MATCH
    mejor_grupo: int | None = None

    for numero, grupo in enumerate(groups):
        for indice in grupo:
            score = text_match(critique.target_hypothesis, entrada.hypotheses[indice].text)
            if score >= mejor_score:
                mejor_score = score
                mejor_grupo = numero

    return mejor_grupo


def detect_contradictions(
    groups: Sequence[Sequence[int]],
    entrada: ArbitrationInput,
) -> dict[int, list[Contradiction]]:
    """
    Documenta las objeciones de peso que quedaron sin resolver, por grupo.

    Una crítica cuenta como contradicción abierta si tiene severidad HIGH y el
    agente criticado no la incorporó. Las críticas MEDIUM y LOW no se reportan
    como contradicción: el debate está para eso, y marcarlas todas volvería
    ruido la señal.

    No hace falta ninguna llamada al LLM: las críticas ya vienen estructuradas
    de la Ronda 2, con autor, severidad y texto.

    Returns:
        Dict {índice de grupo → contradicciones}. Los grupos sin objeciones no
        aparecen.
    """
    por_grupo: dict[int, list[Contradiction]] = {}

    for critique in entrada.critiques:
        if critique.severity != "HIGH":
            continue
        if _agent_conceded(critique, entrada):
            continue

        numero = _group_for_critique(critique, groups, entrada)
        if numero is None:
            continue

        por_grupo.setdefault(numero, []).append(
            Contradiction(
                from_agent_id=critique.from_agent_id,
                from_agent_name=critique.from_agent_name,
                severity=critique.severity,
                critique_text=critique.critique_text,
                target_hypothesis=critique.target_hypothesis,
                alternative=critique.alternative,
            )
        )

    return por_grupo


# ── Ensamblado del consenso ───────────────────────────────────────────────────

def assemble(
    groups: Sequence[Sequence[int]],
    entrada: ArbitrationInput,
    verifications: Mapping[str, SourceVerification],
) -> list[ConsensusHypothesis]:
    """
    Arma las hipótesis de consenso a partir de una partición ya saneada.

    Todo lo que hace acá es determinista: elegir el representante, juntar las
    fuentes, listar quién respalda y quién refuta. Los veredictos los redacta
    después el agente, sobre este resultado.

    Args:
        groups:        Partición saneada por `normalize_partition()`.
        entrada:       Contrato de entrada del Árbitro.
        verifications: Veredictos de la verificación bibliográfica.

    Returns:
        Una `ConsensusHypothesis` por grupo, en el orden de la partición.
    """
    contradicciones = detect_contradictions(groups, entrada)
    consenso: list[ConsensusHypothesis] = []

    for numero, grupo in enumerate(groups):
        representante = choose_representative(grupo, entrada, verifications)
        agrupadas = [entrada.hypotheses[i] for i in grupo]

        # La representativa lleva las fuentes de todo el grupo: si dos agentes
        # sostienen lo mismo con bibliografía distinta, la hipótesis de consenso
        # se apoya en ambas.
        hypothesis = entrada.hypotheses[representante].model_copy(
            update={"sources": merge_sources(agrupadas)}
        )

        respaldan: list[str] = []
        for indice in grupo:
            nombre = entrada.name_of(entrada.agent_of(indice))
            if nombre and nombre not in respaldan:
                respaldan.append(nombre)

        objeciones = contradicciones.get(numero, [])
        refutan: list[str] = []
        for contra in objeciones:
            if contra.from_agent_name not in refutan:
                refutan.append(contra.from_agent_name)

        consenso.append(
            ConsensusHypothesis(
                hypothesis=hypothesis,
                grouped=agrupadas,
                supporting_agents=respaldan,
                refuting_agents=refutan,
                contradictions=objeciones,
            )
        )

    return consenso


# ── 4.5 Consenso degradado ────────────────────────────────────────────────────

def degraded(entrada: ArbitrationInput) -> list[ConsensusHypothesis]:
    """
    Consenso de emergencia: cada hipótesis es su propio grupo, sin veredicto.

    Se usa cuando la agrupación asistida por el LLM falla. El reporte queda como
    antes del Árbitro —las hipótesis sin consolidar— pero el análisis termina y
    `POST /api/analyze` no falla. Las contradicciones sí se detectan: no
    dependen del modelo.
    """
    grupos = [[i] for i in range(len(entrada.hypotheses))]
    contradicciones = detect_contradictions(grupos, entrada)

    consenso: list[ConsensusHypothesis] = []
    for numero, hypothesis in enumerate(entrada.hypotheses):
        objeciones = contradicciones.get(numero, [])
        nombre = entrada.name_of(entrada.agent_of(numero))
        consenso.append(
            ConsensusHypothesis(
                hypothesis=hypothesis,
                grouped=[hypothesis],
                supporting_agents=[nombre] if nombre else [],
                refuting_agents=list(dict.fromkeys(c.from_agent_name for c in objeciones)),
                contradictions=objeciones,
            )
        )
    return consenso


def summarize(
    consensus: Sequence[ConsensusHypothesis],
    entrada: ArbitrationInput,
    retrieved: Sequence[RetrievedArticleRef],
    status: ArbitrationStatus = ArbitrationStatus.OK,
    discarded_references: int = 0,
) -> ArbitrationSummary:
    """Arma el resumen del arbitraje que viaja al reporte exportado."""
    solapan, citadas = rag_overlap(entrada.hypotheses, retrieved)
    return ArbitrationSummary(
        status=status,
        input_hypotheses=len(entrada.hypotheses),
        consensus_hypotheses=len(consensus),
        contradictions=sum(len(c.contradictions) for c in consensus),
        cited_sources=citadas,
        rag_overlap=solapan,
        retrieved_articles=len(retrieved),
        discarded_references=discarded_references,
    )


# ── Adaptador desde el reporte del debate ─────────────────────────────────────

def build_arbitration_input(report: Report) -> ArbitrationInput:
    """
    Arma el contrato de entrada del Árbitro desde el reporte del debate.

    Mismo criterio que `trial_matching.build_navigation_input()` para el Agente
    05: el agente no conoce el `Report` ni el router, recibe un contrato neutral.

    La atribución hipótesis → agente sale de la última ronda con outputs, que es
    de donde `run_debate()` toma las hipótesis finales. Si no hubo debate (un
    solo agente), sale de la Ronda 1.

    Args:
        report: Report final de `debate.run_debate()`.

    Returns:
        ArbitrationInput con las hipótesis, su autoría, las críticas de la ronda
        de crítica cruzada, las rondas por agente y la literatura recuperada.
    """
    rondas_con_output = [r for r in report.debate_rounds if r.agent_outputs]
    finales = rondas_con_output[-1].agent_outputs if rondas_con_output else report.agent_outputs

    final_by_agent = {o.agent_id: list(o.hypotheses) for o in finales}
    round_1_by_agent = {o.agent_id: list(o.hypotheses) for o in report.agent_outputs}
    agent_names = {o.agent_id: o.agent_name for o in report.agent_outputs}
    for output in finales:
        agent_names.setdefault(output.agent_id, output.agent_name)

    # `run_debate()` concatena las hipótesis de la última ronda en ese mismo
    # orden, así que recorrer los outputs reconstruye la autoría posición a
    # posición. Si por lo que sea no coinciden, se completa con "" y el consenso
    # simplemente no atribuye esa hipótesis, en vez de atribuirla mal.
    hypotheses: list[Hypothesis] = []
    hypothesis_agents: list[str] = []
    for output in finales:
        for hypothesis in output.hypotheses:
            hypotheses.append(hypothesis)
            hypothesis_agents.append(output.agent_id)

    if [h.text for h in hypotheses] != [h.text for h in report.hypotheses]:
        # El reporte manda: es lo que se verificó y lo que se va a exportar.
        hypotheses = list(report.hypotheses)
        por_texto = {
            h.text: output.agent_id for output in finales for h in output.hypotheses
        }
        hypothesis_agents = [por_texto.get(h.text, "") for h in hypotheses]

    critiques = [c for r in report.debate_rounds for c in r.critiques]

    return ArbitrationInput(
        hypotheses=hypotheses,
        hypothesis_agents=hypothesis_agents,
        critiques=critiques,
        round_1_by_agent=round_1_by_agent,
        final_by_agent=final_by_agent,
        agent_names=agent_names,
        retrieved_articles=list(report.retrieved_articles),
    )
