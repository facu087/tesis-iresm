"""
Orquestador del pipeline NEXUS — Ronda 1.

Responsabilidades:
  1. Normalizar el texto clínico extraído.
  2. Construir la síntesis PICO (contexto estructurado para los agentes).
  3. Extraer biomarcadores e historial terapéutico.
  4. Indexar literatura PubMed relevante en ChromaDB (RAG) y construir
     el perfil genómico (genomic_context) en paralelo.
  5. Enriquecer el contexto de los agentes con bibliografía verificable.
  6. Ejecutar Agentes 01, 02 y 03 en PARALELO (asyncio.gather + to_thread).
  7. Consolidar los outputs en un Report.

Los agentes usan el cliente Groq sincrónico; asyncio.to_thread() los corre
en un thread pool sin bloquear el event loop, logrando verdadera concurrencia
dentro del proceso.
"""

import asyncio
import sys
from typing import Sequence

from ..agents.agent_01_literature import LiteratureAnalystAgent
from ..agents.agent_02_genomics import GenomicsSpecialistAgent
from ..agents.agent_03_clinical import ClinicalConsultantAgent
from ..agents.base_agent import BaseAgent
from ..ingestion.biomarker_extractor import extract as extract_biomarkers
from ..ingestion.normalizer import normalize
from ..models.case import ClinicalCase
from ..models.hypothesis import Hypothesis
from ..models.report import AgentOutput, Report, RetrievedArticleRef
from ..rag.indexer import index_from_clinical_context
from ..rag.retriever import PubMedRetriever
from . import genomic_context as gc_module
from . import pico


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run_agent_async(agent: BaseAgent, context: str) -> AgentOutput:
    """Ejecuta un agente sincrónico en un thread pool para no bloquear el loop."""
    return await asyncio.to_thread(agent.run, context)


def _build_sources_summary(hypotheses: list[Hypothesis]) -> dict[str, int]:
    """Cuenta fuentes únicas por nivel de evidencia."""
    summary: dict[str, int] = {"I": 0, "II": 0, "III": 0}
    seen_pmids: set[str] = set()
    for h in hypotheses:
        for source in h.sources:
            key = source.pmid or source.title
            if key and key not in seen_pmids:
                seen_pmids.add(key)
                summary[h.evidence_level.value] += 1
    return summary


# ── RAG: indexación y enriquecimiento del contexto ────────────────────────────

async def _enrich_context_with_rag(
    case: ClinicalCase, base_context: str
) -> tuple[str, list[RetrievedArticleRef]]:
    """
    Indexa literatura PubMed relevante y agrega bibliografía verificable al contexto.

    Si la indexación o la búsqueda fallan (red caída, cuota excedida, etc.)
    el pipeline continúa con el contexto base sin RAG.

    Devuelve además los artículos recuperados: el Árbitro (Agente 04) los usa
    para medir cuántas de las citas de los agentes salieron efectivamente de la
    literatura que se les ofreció, y para armar la ronda de recitación sobre
    PMIDs reales. Ante cualquier fallo la lista queda vacía y el pipeline sigue.
    """
    genes: list[str] = []
    conditions: list[str] = []
    drugs: list[str] = []

    if case.biomarkers:
        genes = case.biomarkers.genes[:3]
        drugs = case.biomarkers.drugs[:2]

    # PubMed indexa en inglés, igual que ClinicalTrials.gov: se usa condition_en
    # y no chief_complaint, que viene en español del documento clínico. Medido
    # sobre el caso de prueba (scripts/demo_embeddings_comparacion.py), consultar
    # en español baja el score del mejor resultado de 0.866 a 0.781 y degrada el
    # orden del diferencial. Mismo criterio que backend/api/router.py.
    condition_en = ""
    if case.pico:
        condition_en = case.pico.condition_en or case.pico.chief_complaint
        conditions = [condition_en] if condition_en else []

    try:
        await index_from_clinical_context(genes=genes, conditions=conditions, drugs=drugs)
    except Exception as exc:
        print(f"[NEXUS][RAG] Indexación omitida: {exc}", file=sys.stderr)

    # La query semántica se arma con el término en inglés más los genes, que ya
    # son símbolos HGNC (idioma-neutros). primary_outcome queda afuera: está en
    # español y arrastraría la query de vuelta al problema de arriba.
    rag_query = " ".join(filter(None, [condition_en, " ".join(genes)]))

    articles: list[RetrievedArticleRef] = []
    try:
        retriever = PubMedRetriever()
        rag_context, retrieved = retriever.get_context_with_articles(
            rag_query, max_results=5
        )
        articles = [
            RetrievedArticleRef(
                pmid=a.pmid,
                title=a.title,
                journal=a.journal,
                year=a.year,
                excerpt=a.excerpt,
            )
            for a in retrieved
            if a.pmid
        ]
    except Exception as exc:
        print(f"[NEXUS][RAG] Búsqueda semántica omitida: {exc}", file=sys.stderr)
        rag_context = (
            "LITERATURA CIENTÍFICA DISPONIBLE:\n"
            "No se pudo acceder a la base local de PubMed. "
            "Usá evidence_level: 'III' para hipótesis sin respaldo bibliográfico verificado."
        )

    return f"{base_context}\n\n{rag_context}", articles


# ── Ronda 1: análisis paralelo ─────────────────────────────────────────────────

async def run_round_1(case: ClinicalCase) -> Report:
    """
    Ronda 1: corre Agentes 01 y 03 en paralelo sobre el contexto PICO + RAG.

    Precondición: case.pico debe estar completo (llamar pico.build() antes).
    Si un agente falla, se registra en stderr y el pipeline continúa
    con los agentes restantes.
    """
    if case.pico is None:
        raise ValueError("case.pico es None — llamar a pico.build() antes de run_round_1().")

    base_context = pico.format_for_agents(case.pico)

    # RAG y perfil genómico se construyen en paralelo antes de la Ronda 1
    ctx_base = gc_module.build(case)
    (context, retrieved_articles), genomic_ctx = await asyncio.gather(
        _enrich_context_with_rag(case, base_context),
        gc_module.enrich(ctx_base),
    )
    case.genomic_context = genomic_ctx

    agents: Sequence[BaseAgent] = [
        LiteratureAnalystAgent(),
        GenomicsSpecialistAgent(genomic_context=genomic_ctx),
        ClinicalConsultantAgent(),
    ]

    results = await asyncio.gather(
        *(_run_agent_async(agent, context) for agent in agents),
        return_exceptions=True,
    )

    valid_outputs: list[AgentOutput] = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            print(
                f"[NEXUS] Agente {agent.AGENT_NAME} (ID:{agent.AGENT_ID}) falló "
                f"en Ronda 1: {result}",
                file=sys.stderr,
            )
        else:
            valid_outputs.append(result)

    if not valid_outputs:
        raise RuntimeError("Todos los agentes fallaron en Ronda 1. Verificá la API key y el modelo.")

    all_hypotheses = [h for output in valid_outputs for h in output.hypotheses]

    return Report(
        case_summary=case.pico.clinical_narrative,
        hypotheses=all_hypotheses,
        agent_outputs=valid_outputs,
        sources_summary=_build_sources_summary(all_hypotheses),
        retrieved_articles=retrieved_articles,
    )


# ── Pipeline completo (entrada sincrónica) ─────────────────────────────────────

def run(clinical_text: str) -> Report:
    """
    Ejecuta el pipeline completo de forma sincrónica:
      normalización → PICO → biomarcadores → Ronda 1 (paralelo).

    Uso desde scripts y tests de integración.
    En FastAPI usar run_round_1() directamente desde un endpoint async.
    """
    normalized = normalize(clinical_text)

    case = ClinicalCase(raw_text=normalized)
    case = pico.build(case)
    case.biomarkers = extract_biomarkers(normalized)

    return asyncio.run(run_round_1(case))
