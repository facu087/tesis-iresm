"""
Router FastAPI — endpoints del pipeline NEXUS.
"""

import asyncio
import sys
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..agents.agent_01_literature import LiteratureAnalystAgent
from ..agents.agent_02_genomics import GenomicsSpecialistAgent
from ..agents.agent_03_clinical import ClinicalConsultantAgent
from ..agents.agent_04_arbiter import ArbiterAgent
from ..agents.agent_05_trials import TrialNavigatorAgent
from ..agents.base_agent import BaseAgent
from ..ingestion.biomarker_extractor import extract as extract_biomarkers
from ..ingestion.extractor import extract
from ..ingestion.normalizer import normalize
from ..models.arbitration import ArbitrationResult, ArbitrationStatus
from ..models.case import ClinicalCase
from ..models.report import Report
from ..models.trial import ApiStatus, TrialNavigationInput, TrialNavigationResult, TrialSearchSummary
from ..pipeline import debate, orchestrator, pico
from ..pipeline.pdf_exporter import generate_pdf
from ..pipeline.report_builder import build_export
from ..pipeline.consensus import build_arbitration_input, degraded, summarize
from ..pipeline.trial_matching import build_navigation_input
from ..pipeline.verification import SourceVerification, verify_report_sources
from .schemas import StructuredReport

router = APIRouter(prefix="/api", tags=["análisis"])

_MAX_TEXT_BYTES = 500_000  # ~500 KB


async def _navigate_trials_safe(
    nav_input: TrialNavigationInput,
) -> TrialNavigationResult:
    """
    Red de seguridad del router alrededor del Agente 05.

    El agente ya tiene un fallback por paso; esto cubre una excepción no
    prevista para que `POST /api/analyze` nunca falle por la navegación de
    ensayos. Solo se loggea el tipo: el mensaje puede arrastrar texto clínico.
    """
    try:
        return await TrialNavigatorAgent().navigate(nav_input)
    except Exception as exc:
        print(
            f"[NEXUS] Agente 05 — navegación de ensayos: fallback ({type(exc).__name__})",
            file=sys.stderr,
        )
        return TrialNavigationResult(
            summary=TrialSearchSummary(
                estado_clinicaltrials=ApiStatus.NO_DISPONIBLE.value,
                estado_orphanet=ApiStatus.NO_DISPONIBLE.value,
            )
        )


async def _arbitrate_safe(
    report: Report,
    verifications: dict[str, SourceVerification],
    case: ClinicalCase,
) -> ArbitrationResult:
    """
    Red de seguridad del router alrededor del Agente 04.

    El agente ya tiene fallback por paso; esto cubre una excepción no prevista
    para que `POST /api/analyze` nunca falle por el arbitraje. Ante el fallo se
    devuelve el consenso degradado —cada hipótesis su propio grupo—, que es como
    se veía el reporte antes del Árbitro. Solo se loggea el tipo de excepción:
    el mensaje puede arrastrar texto clínico.
    """
    entrada = build_arbitration_input(report)
    try:
        return await ArbiterAgent().arbitrate(
            entrada, verifications, agents=_debate_agents(report, case)
        )
    except Exception as exc:
        print(
            f"[NEXUS] Agente 04 — arbitraje: fallback ({type(exc).__name__})",
            file=sys.stderr,
        )
        consenso = degraded(entrada)
        return ArbitrationResult(
            consensus=consenso,
            summary=summarize(
                consenso, entrada, entrada.retrieved_articles,
                status=ArbitrationStatus.DEGRADADO,
            ),
        )


def _debate_agents(report: Report, case: ClinicalCase) -> dict[str, BaseAgent]:
    """
    Instancia los agentes que participaron del debate, para la Ronda 5.

    Solo los que produjeron output: pedirle una recitación a un agente que se
    cayó en la Ronda 1 no tiene sentido.

    El Agente 02 se construye con el perfil genómico del caso, igual que en el
    debate: sin él recitaría a ciegas, que es lo que su override de
    `_build_recitation_prompt()` evita.
    """
    disponibles = {o.agent_id for o in report.agent_outputs}
    agentes: dict[str, BaseAgent] = {}
    if "01" in disponibles:
        agentes["01"] = LiteratureAnalystAgent()
    if "02" in disponibles and case.genomic_context is not None:
        agentes["02"] = GenomicsSpecialistAgent(genomic_context=case.genomic_context)
    if "03" in disponibles:
        agentes["03"] = ClinicalConsultantAgent()
    return agentes


@router.post("/analyze", response_model=StructuredReport, summary="Analizar caso clínico")
async def analyze(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
) -> StructuredReport:
    """
    Recibe un documento clínico (PDF o texto plano) y ejecuta el pipeline completo:
    ingesta → normalización → PICO → biomarcadores → debate multi-agente →
    búsqueda de ensayos clínicos activos.

    Devuelve un Report con hipótesis priorizadas por nivel de evidencia (I, II, III).

    NEXUS no emite diagnósticos. Genera hipótesis de investigación para el médico responsable.
    """
    if file is None and not text:
        raise HTTPException(
            status_code=422,
            detail="Se requiere al menos un campo: 'file' (PDF) o 'text' (texto clínico).",
        )

    start = time.perf_counter()

    # ── 1. Extracción de texto ─────────────────────────────────────────────────
    if file is not None:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=422, detail="El archivo enviado está vacío.")
        try:
            clinical_text = await asyncio.to_thread(
                extract, file.filename or "document.pdf", content
            )
        except ValueError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e
    else:
        clinical_text = text  # type: ignore[assignment]

    if not clinical_text or not clinical_text.strip():
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del documento.")

    # Truncar si supera el límite para proteger las APIs downstream
    if len(clinical_text.encode()) > _MAX_TEXT_BYTES:
        clinical_text = clinical_text[:_MAX_TEXT_BYTES]

    # ── 2. Normalización ───────────────────────────────────────────────────────
    normalized = await asyncio.to_thread(normalize, clinical_text)
    case = ClinicalCase(raw_text=normalized)

    # ── 3. Síntesis PICO y extracción de biomarcadores (paralelo) ──────────────
    case_with_pico, biomarkers = await asyncio.gather(
        asyncio.to_thread(pico.build, case),
        asyncio.to_thread(extract_biomarkers, normalized),
    )
    case_with_pico.biomarkers = biomarkers

    # ── 4. Ronda 1: análisis paralelo de agentes ───────────────────────────────
    round_1_report = await orchestrator.run_round_1(case_with_pico)

    # ── 5. Debate adversarial: Rondas 2–4 ─────────────────────────────────────
    final_report = await debate.run_debate(case_with_pico, round_1_report)

    # ── 6. Verificación bibliográfica de los PMIDs citados (Agente 04) ────────
    verifications = await verify_report_sources(final_report)

    # ── 7. Arbitraje: consenso, contradicciones y Ronda 5 (Agente 04) ────────
    # Va después de la verificación porque el Árbitro necesita saber qué citas
    # resistieron para decidir qué hipótesis se recitan.
    arbitration = await _arbitrate_safe(final_report, verifications, case_with_pico)

    # ── 8. Navegación de ensayos (Agente 05) ─────────────────────────────────
    # Ahora busca sobre el consenso y no sobre la concatenación del debate: son
    # menos hipótesis y sin duplicados, así que la búsqueda trae menos ruido.
    # `build_navigation_input()` ya estaba preparado para esto y no cambia.
    consensus_hypotheses = [c.hypothesis for c in arbitration.consensus]
    nav_input = build_navigation_input(
        case_with_pico,
        consensus_hypotheses or final_report.hypotheses,
    )
    navigation = await _navigate_trials_safe(nav_input)

    return build_export(
        case=case_with_pico,
        report=final_report,
        trials=navigation.trials,
        processing_time=time.perf_counter() - start,
        verifications=verifications,
        navigation=navigation,
        arbitration=arbitration,
    )


@router.post(
    "/report/pdf",
    summary="Exportar reporte a PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def export_pdf(report: StructuredReport) -> Response:
    """
    Recibe un StructuredReport (resultado de POST /api/analyze) y devuelve el PDF.

    El frontend llama primero a /api/analyze para obtener el JSON,
    lo muestra al usuario y, si quiere descargarlo, llama a este endpoint.
    """
    pdf_bytes = await asyncio.to_thread(generate_pdf, report)
    filename = (
        f"nexus_reporte_{report.metadata.generated_at.strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
