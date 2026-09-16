"""
Router FastAPI — endpoints del pipeline NEXUS.
"""

import asyncio
import sys
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..agents.agent_05_trials import TrialNavigatorAgent
from ..ingestion.biomarker_extractor import extract as extract_biomarkers
from ..ingestion.extractor import extract
from ..ingestion.normalizer import normalize
from ..models.case import ClinicalCase
from ..models.trial import ApiStatus, TrialNavigationInput, TrialNavigationResult, TrialSearchSummary
from ..pipeline import debate, orchestrator, pico
from ..pipeline.pdf_exporter import generate_pdf
from ..pipeline.report_builder import build_export
from ..pipeline.trial_matching import build_navigation_input
from ..pipeline.verification import verify_report_sources
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

    # ── 6 y 7. Navegación de ensayos (Agente 05) + verificación (Agente 04) ───
    # Ambos dependen solo del reporte final del debate y usan APIs distintas
    # (ClinicalTrials.gov/Orphanet vs. PubMed), así que corren en paralelo.
    # Cuando exista el Árbitro, el orden pasa a ser árbitro → navigate(consenso).
    nav_input = build_navigation_input(case_with_pico, final_report.hypotheses)
    navigation, verifications = await asyncio.gather(
        _navigate_trials_safe(nav_input),
        verify_report_sources(final_report),
    )

    return build_export(
        case=case_with_pico,
        report=final_report,
        trials=navigation.trials,
        processing_time=time.perf_counter() - start,
        verifications=verifications,
        navigation=navigation,
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
