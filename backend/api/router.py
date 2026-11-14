"""
Router FastAPI — endpoints del pipeline NEXUS.
"""

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from ..agents.agent_01_literature import LiteratureAnalystAgent
from ..auth.deps import requerir_medico_verificado
from ..auth.origen import validar_origen
from ..models.cuenta import CuentaMedico
from ..agents.agent_02_genomics import GenomicsSpecialistAgent
from ..agents.agent_03_clinical import ClinicalConsultantAgent
from ..agents.agent_04_arbiter import ArbiterAgent
from ..agents.agent_05_trials import TrialNavigatorAgent
from ..agents.agent_06_synthesizer import SynthesizerAgent
from ..agents.base_agent import BaseAgent
from ..ingestion.anonimizador import anonimizar
from ..ingestion.biomarker_extractor import extract as extract_biomarkers
from ..ingestion.extractor import extract
from ..ingestion.normalizer import normalize
from ..models.arbitration import ArbitrationResult, ArbitrationStatus
from ..models.case import ClinicalCase
from ..models.report import Report
from ..models.trial import ApiStatus, TrialNavigationInput, TrialNavigationResult, TrialSearchSummary
from ..pipeline import debate, orchestrator, pico, progreso
from ..pipeline.pdf_exporter import generate_pdf
from ..pipeline.report_builder import build_export
from ..pipeline.consensus import build_arbitration_input, degraded, summarize
from ..pipeline.trial_matching import build_navigation_input
from ..pipeline.verification import (
    SourceVerification,
    estado_verificacion,
    registro_de_consultas,
    verify_report_sources,
)
from ..mock import responses as mock_responses
from ..mock.mode import is_mock_active
from ..telemetry import usage as usage_telemetry
from .schemas import AgentProviderInfo, StructuredReport

router = APIRouter(prefix="/api", tags=["análisis"])

_MAX_TEXT_BYTES = 500_000  # ~500 KB

# Tamaño máximo del archivo subido, en MB, si MAX_FILE_SIZE_MB no está definida
# o no es un entero positivo.
_MAX_FILE_SIZE_MB_DEFAULT = 50


def _limite_subida_mb() -> int:
    """
    Límite de tamaño del archivo subido, leído de `MAX_FILE_SIZE_MB`.

    Se lee en cada pedido para que un cambio de configuración no exija
    reimportar el módulo. Un valor que no es un entero positivo avisa por
    stderr y cae al valor por defecto: un error de tipeo en el `.env` no debe
    dejar el endpoint sin límite ni impedir analizar.
    """
    crudo = os.getenv("MAX_FILE_SIZE_MB", "").strip()
    if not crudo:
        return _MAX_FILE_SIZE_MB_DEFAULT
    try:
        valor = int(crudo)
    except ValueError:
        valor = 0
    if valor <= 0:
        print(
            f"[NEXUS] MAX_FILE_SIZE_MB={crudo!r} no es un entero positivo; "
            f"se usa {_MAX_FILE_SIZE_MB_DEFAULT} MB.",
            file=sys.stderr,
        )
        return _MAX_FILE_SIZE_MB_DEFAULT
    return valor


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


async def _synthesize_safe(structured: StructuredReport) -> str | None:
    """
    Red de seguridad del router alrededor del Agente 06: un fallo no previsto
    deja el reporte sin resumen ejecutivo en lugar de hacer fallar el análisis.
    """
    try:
        return await SynthesizerAgent().synthesize(structured)
    except Exception as exc:
        print(
            f"[NEXUS] Agente 06 — síntesis: fallback ({type(exc).__name__})",
            file=sys.stderr,
        )
        return None


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


@dataclass(frozen=True)
class _Entrada:
    """Lo que mandó el cliente, ya leído y dentro de los límites de tamaño."""

    nombre: str | None = None
    contenido: bytes | None = None
    texto: str | None = None


async def _leer_entrada(file: UploadFile | None, text: str | None) -> _Entrada:
    """
    Lee el archivo o el texto del pedido y rechaza lo que no se puede analizar.

    Levanta 422 si no hay ni archivo ni texto o si el archivo está vacío, y
    413 si supera `MAX_FILE_SIZE_MB`.
    """
    if file is None and not text:
        raise HTTPException(
            status_code=422,
            detail="Se requiere al menos un campo: 'file' (PDF) o 'text' (texto clínico).",
        )
    if file is None:
        return _Entrada(texto=text)

    # Se lee como mucho un byte más que el límite: alcanza para saber
    # si lo supera sin cargar en memoria un archivo arbitrariamente
    # grande. El proxy de producción puede cortar antes (ver
    # docs/instalacion-y-despliegue.md).
    limite_mb = _limite_subida_mb()
    limite_bytes = limite_mb * 1024 * 1024
    content = await file.read(limite_bytes + 1)
    if len(content) > limite_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {limite_mb} MB.",
        )
    if not content:
        raise HTTPException(status_code=422, detail="El archivo enviado está vacío.")
    return _Entrada(nombre=file.filename or "document.pdf", contenido=content)


async def _ejecutar_pipeline(entrada: _Entrada, start: float) -> StructuredReport:
    """
    Corre el pipeline completo sobre una entrada ya leída.

    Lo comparten `POST /api/analyze` y `POST /api/analyze/stream`. Avisa el
    comienzo de cada paso por `pipeline/progreso.py`; los identificadores son
    los de `frontend/src/lib/pipelineSteps.ts`. Quien llama abre y cierra el
    registro de telemetría y la sesión de reproducción del modo mock.
    """
    # ── 1. Extracción de texto ─────────────────────────────────────────────
    progreso.paso("01")
    if entrada.contenido is not None:
        try:
            clinical_text = await asyncio.to_thread(
                extract, entrada.nombre or "document.pdf", entrada.contenido
            )
        except ValueError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e
    else:
        clinical_text = entrada.texto  # type: ignore[assignment]

    if not clinical_text or not clinical_text.strip():
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del documento.")

    # Truncar si supera el límite para proteger las APIs downstream
    if len(clinical_text.encode()) > _MAX_TEXT_BYTES:
        clinical_text = clinical_text[:_MAX_TEXT_BYTES]

    # ── 2. Normalización ────────────────────────────────────────────────────
    progreso.paso("02")
    normalized = await asyncio.to_thread(normalize, clinical_text)

    # ── 2.b Anonimización ───────────────────────────────────────────────────
    # Última parada antes de que el texto salga del sistema: de acá en
    # adelante va a Groq (PICO, biomarcadores y los seis agentes), PubMed,
    # ClinicalTrials.gov, Orphanet y PharmGKB. El informe lleva conteos por
    # categoría, nunca los valores encontrados.
    normalized, informe_anonimizacion = await asyncio.to_thread(anonimizar, normalized)
    print(f"[NEXUS] {informe_anonimizacion.resumen()}", file=sys.stderr)

    case = ClinicalCase(raw_text=normalized)

    # ── 3. Síntesis PICO y extracción de biomarcadores (paralelo) ───────────
    progreso.paso("03")
    case_with_pico, biomarkers = await asyncio.gather(
        asyncio.to_thread(pico.build, case),
        asyncio.to_thread(extract_biomarkers, normalized),
    )
    case_with_pico.biomarkers = biomarkers

    # ── 4. Ronda 1: análisis paralelo de agentes ────────────────────────────
    progreso.paso("04")
    round_1_report = await orchestrator.run_round_1(case_with_pico)

    # ── 5. Debate adversarial: Rondas 2–4 ───────────────────────────────────
    progreso.paso("05")
    final_report = await debate.run_debate(case_with_pico, round_1_report)

    # El registro anota el resultado de cada consulta a PubMed: la de la
    # verificación (paso 6) y la re-verificación de la Ronda 5 que hace el
    # Árbitro (paso 7). Con eso el reporte dice si la verificación corrió
    # y, si no, por qué (tarjeta #91).
    progreso.paso("06")
    with registro_de_consultas() as consultas_pubmed:
        # ── 6. Verificación bibliográfica de los PMIDs citados (Agente 04) ──
        verifications = await verify_report_sources(final_report)

        # ── 7. Arbitraje: consenso, contradicciones y Ronda 5 (Agente 04) ───
        # Va después de la verificación porque el Árbitro necesita saber qué
        # citas resistieron para decidir qué hipótesis se recitan.
        arbitration = await _arbitrate_safe(final_report, verifications, case_with_pico)

    # ── 8. Navegación de ensayos (Agente 05) ────────────────────────────────
    # Ahora busca sobre el consenso y no sobre la concatenación del
    # debate: son menos hipótesis y sin duplicados, así que la búsqueda
    # trae menos ruido. `build_navigation_input()` ya estaba preparado
    # para esto y no cambia.
    progreso.paso("07")
    consensus_hypotheses = [c.hypothesis for c in arbitration.consensus]
    nav_input = build_navigation_input(
        case_with_pico,
        consensus_hypotheses or final_report.hypotheses,
    )
    navigation = await _navigate_trials_safe(nav_input)

    progreso.paso("08")
    structured = build_export(
        case=case_with_pico,
        report=final_report,
        trials=navigation.trials,
        processing_time=time.perf_counter() - start,
        verifications=verifications,
        navigation=navigation,
        arbitration=arbitration,
        mock=is_mock_active(),
        estado_verificacion=estado_verificacion(consultas_pubmed),
    )

    # ── 9. Resumen ejecutivo (Agente 06) ────────────────────────────────────
    # Va al final porque narra el reporte ya construido; no cambia datos.
    structured.executive_summary = await _synthesize_safe(structured)

    # ── 10. Quién respondió por cada agente (multi-proveedor, D7) ────────────
    # Sale de la telemetría, que ya registró cada llamada; va después del
    # Agente 06, que es la última llamada al modelo.
    structured.metadata.proveedores = _proveedores_del_analisis()
    processing_time = time.perf_counter() - start
    structured.metadata.processing_time_seconds = round(processing_time, 2)
    return structured


@router.post(
    "/analyze",
    response_model=StructuredReport,
    summary="Analizar caso clínico",
    dependencies=[Depends(validar_origen)],
)
async def analyze(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    _medico: CuentaMedico = Depends(requerir_medico_verificado),
) -> StructuredReport:
    """
    Recibe un documento clínico (PDF o texto plano) y ejecuta el pipeline completo:
    ingesta → normalización → PICO → biomarcadores → debate multi-agente →
    búsqueda de ensayos clínicos activos.

    Devuelve un Report con hipótesis priorizadas por nivel de evidencia (I, II, III).

    NEXUS no emite diagnósticos. Genera hipótesis de investigación para el médico responsable.

    `proteccion-analisis-clinico`: exige sesión de médico `verificado`
    (`requerir_medico_verificado`) y `Origin`/`Referer` permitido
    (`validar_origen`), sin importar el tipo de contenido de la solicitud.
    """
    if file is None and not text:
        raise HTTPException(
            status_code=422,
            detail="Se requiere al menos un campo: 'file' (PDF) o 'text' (texto clínico).",
        )

    start = time.perf_counter()

    # Registro de consumo del análisis (control de costos, S4 — D2). Se abre
    # acá porque el router es el único lugar que conoce el ciclo de vida
    # completo de un análisis, y se cierra en el `finally` para que un fallo a
    # mitad de pipeline no deje el contexto de telemetría activo.
    telemetry_token = usage_telemetry.open_registry()
    # Sesión de reproducción del modo mock: cuenta las llamadas de este
    # análisis para entregar a cada agente su grabación de cada ronda. Se abre
    # acá, antes de que el pipeline reparta trabajo con `asyncio.gather()`,
    # para que todas las tareas compartan el mismo conteo; y por análisis, para
    # que dos análisis del mismo texto den el mismo resultado. Fuera del modo
    # mock nadie la consulta.
    replay_token = mock_responses.open_replay_session()
    try:
        entrada = await _leer_entrada(file, text)
        return await _ejecutar_pipeline(entrada, start)
    finally:
        mock_responses.close_replay_session(replay_token)
        usage_telemetry.close_registry(telemetry_token, mock=is_mock_active())


_ERROR_INTERNO = "Ocurrió un error interno durante el análisis. Intentá de nuevo."


@router.post(
    "/analyze/stream",
    summary="Analizar caso clínico con el avance en vivo",
    dependencies=[Depends(validar_origen)],
)
async def analyze_stream(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    _medico: CuentaMedico = Depends(requerir_medico_verificado),
) -> StreamingResponse:
    """
    El mismo análisis que `POST /api/analyze`, transmitiendo el avance.

    La respuesta es NDJSON (`application/x-ndjson`): un objeto JSON por línea.

    - `{"evento": "paso", "paso": "03"}` — empezó un paso del pipeline
      (`"01"` a `"08"`).
    - `{"evento": "ronda", "ronda": 2}` — empezó una ronda del debate (2 a 4).
    - `{"evento": "reporte", "reporte": {...}}` — el `StructuredReport`
      terminado. Siempre es el último evento de un análisis que salió bien.
    - `{"evento": "error", "status": 415, "detail": "..."}` — el análisis
      falló. Siempre es el último evento de un análisis que falló.

    Una entrada inválida (sin archivo ni texto, archivo vacío o demasiado
    grande) se rechaza con su código HTTP antes de transmitir nada. Una falla
    posterior ya no puede cambiar el código de la respuesta, que es 200: viaja
    como evento `error`. Una falla inesperada lleva un mensaje fijo, nunca el
    texto de la excepción.

    Misma protección que `POST /api/analyze`: sesión de médico `verificado` y
    `Origin`/`Referer` permitido. Si el cliente corta la conexión, el análisis
    se cancela.
    """
    # Se lee antes de responder: es lo que permite rechazar una entrada
    # inválida con su código HTTP, y el pipeline corre después, mientras se
    # transmite, cuando el archivo subido ya no está garantizado.
    entrada = await _leer_entrada(file, text)

    cola: asyncio.Queue[dict | None] = asyncio.Queue()

    async def correr() -> None:
        start = time.perf_counter()
        telemetry_token = usage_telemetry.open_registry()
        replay_token = mock_responses.open_replay_session()
        progreso_token = progreso.abrir(cola.put_nowait)
        try:
            reporte = await _ejecutar_pipeline(entrada, start)
            cola.put_nowait({"evento": "reporte", "reporte": reporte.model_dump(mode="json")})
        except HTTPException as exc:
            cola.put_nowait({"evento": "error", "status": exc.status_code, "detail": exc.detail})
        except Exception as exc:
            # Solo el tipo: el mensaje de una excepción puede arrastrar texto
            # clínico, y esto va a los logs y al cliente.
            print(
                f"[NEXUS] El análisis transmitido falló ({type(exc).__name__}).",
                file=sys.stderr,
            )
            cola.put_nowait({"evento": "error", "status": 500, "detail": _ERROR_INTERNO})
        finally:
            progreso.cerrar(progreso_token)
            mock_responses.close_replay_session(replay_token)
            usage_telemetry.close_registry(telemetry_token, mock=is_mock_active())
            # Fin de la transmisión, también si la tarea fue cancelada.
            cola.put_nowait(None)

    async def cuerpo() -> AsyncIterator[str]:
        # El pipeline corre en su propia tarea: abre y cierra sus `contextvars`
        # (telemetría, modo mock, progreso) en un mismo contexto, que no
        # depende de cómo el servidor itere el cuerpo de la respuesta. Se crea
        # acá y no antes: si la respuesta nunca se llega a transmitir, el
        # pipeline no arranca.
        tarea = asyncio.create_task(correr())
        try:
            while (evento := await cola.get()) is not None:
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        finally:
            # El cliente cortó o la transmisión terminó: no dejar el pipeline
            # corriendo (y gastando cuota) sin nadie que lo lea.
            if not tarea.done():
                tarea.cancel()

    return StreamingResponse(
        cuerpo(),
        media_type="application/x-ndjson",
        # Que un proxy inverso no acumule la respuesta antes de entregarla.
        headers={"X-Accel-Buffering": "no"},
    )


def _proveedores_del_analisis() -> list[AgentProviderInfo] | None:
    """
    Quién respondió por cada agente en el análisis en curso, según el registro
    de telemetría abierto. `None` si no hay registro (no debería pasar dentro de
    `analyze()`, que lo abre al empezar).
    """
    registro = usage_telemetry.current()
    if registro is None:
        return None
    return [
        AgentProviderInfo(**entrada)
        for entrada in usage_telemetry.providers_by_agent(registro)
    ]


@router.post(
    "/report/pdf",
    summary="Exportar reporte a PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    dependencies=[Depends(validar_origen)],
)
async def export_pdf(
    report: StructuredReport,
    _medico: CuentaMedico = Depends(requerir_medico_verificado),
) -> Response:
    """
    Recibe un StructuredReport (resultado de POST /api/analyze) y devuelve el PDF.

    El frontend llama primero a /api/analyze para obtener el JSON,
    lo muestra al usuario y, si quiere descargarlo, llama a este endpoint.

    `proteccion-analisis-clinico` — Requirement: Misma exigencia sobre la
    exportación a PDF: exige la misma sesión de médico `verificado` que
    `/api/analyze` (design.md — D5).
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
