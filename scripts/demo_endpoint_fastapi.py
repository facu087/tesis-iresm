"""
Demo de verificación — Endpoint FastAPI: POST /api/analyze.

Muestra la estructura del endpoint, su contrato de request/response
y simula el flujo de datos que recibe y retorna, sin ejecutar el pipeline
completo (que requiere Groq API key y puede tardar varios minutos).

Para una prueba real contra el servidor levantado:
    uvicorn backend.main:app --reload
    curl -X POST http://localhost:8000/api/analyze -F "text=<texto clínico>"

Artefactos generados en output/demo_endpoint_fastapi/:
    1. contrato_api.txt     → documentación del endpoint (request/response schema)
    2. ejemplo_request.txt  → ejemplo de cómo llamar al endpoint (curl + Python)
    3. ejemplo_response.json → estructura del JSON que devuelve el endpoint

Uso:
    python scripts/demo_endpoint_fastapi.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
)
from backend.models.hypothesis import Source
from backend.models.trial import ClinicalTrial
from datetime import datetime, timezone

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_endpoint_fastapi"

_PIPELINE_STEPS = [
    ("Extracción de texto",       "PDF nativo (pdfplumber) o texto plano"),
    ("Normalización",             "Nombres INN, unidades de medida (normalizer.py)"),
    ("Síntesis PICO",             "Narrativa clínica estructurada (pico.py)"),
    ("Extracción biomarcadores",  "Genes, anticuerpos, fármacos (biomarker_extractor.py)"),
    ("Ronda 1 — Agentes",         "Análisis paralelo: Agente 01 + Agente 03 (asyncio)"),
    ("Rondas 2-4 — Debate",       "Crítica cruzada adversarial (debate.py)"),
    ("Ensayos clínicos",          "Búsqueda en ClinicalTrials.gov API v2"),
    ("Generación del reporte",    "JSON estructurado (report_builder.py)"),
]


def _mock_structured_report() -> StructuredReport:
    """Construye el StructuredReport que retornaría el endpoint."""
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime(2026, 6, 23, 10, 30, 0, tzinfo=timezone.utc),
            nexus_version="0.3.0",
            processing_time_seconds=12.4,
        ),
        case_summary=CaseSummarySection(
            narrative=(
                "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
                "progresiva de 18 meses, diabetes tipo 2 mal controlada (HbA1c 8.2%) "
                "y panel CMT negativo."
            ),
            patient_profile="Masculino, 42 años",
            chief_complaint="Debilidad progresiva en miembros inferiores (18 meses)",
            disease_duration="18 meses",
            current_treatments=["pregabalina 150 mg/día"],
            relevant_history=["Diabetes mellitus tipo 2 (10 años)", "HbA1c 8.2%"],
            procedures_done=["EMG", "VCN"],
        ),
        hypotheses=[
            RankedHypothesis(
                rank=1,
                text="Amiloidosis hereditaria por TTR como causa de neuropatía axonal progresiva",
                priority="HIGH",
                evidence_level="II",
                rationale="Patrón axonal con afectación autonómica; TTR Val30Met es la más frecuente.",
                supporting_agents=["Agente 01", "Agente 03"],
                sources=[Source(pmid="29470523", title="Hereditary transthyretin amyloidosis: a review",
                                journal="N Engl J Med", year=2019,
                                url="https://pubmed.ncbi.nlm.nih.gov/29470523/")],
            ),
            RankedHypothesis(
                rank=2,
                text="Neuropatía diabética axonal severa por mal control glucémico crónico",
                priority="MEDIUM",
                evidence_level="I",
                rationale="HbA1c 8.2% con 10 años de diabetes; patrón axonal distal compatible.",
                supporting_agents=["Agente 03"],
                sources=[Source(pmid="31504380", title="Diabetic peripheral neuropathy",
                                journal="Lancet Neurol", year=2019,
                                url="https://pubmed.ncbi.nlm.nih.gov/31504380/")],
            ),
        ],
        debate_summary=DebateSummary(
            rounds_completed=3,
            total_critiques=6,
            divergences=["Agente 01 prioriza TTR; Agente 03 prioriza causa diabética"],
            consensus_reached=True,
        ),
        clinical_trials=[
            ClinicalTrial(
                nct_id="NCT04104672",
                title="Patisiran para amiloidosis por transtiretina hereditaria con neuropatía",
                status="RECRUITING",
                brief_summary="Estudio de eficacia de patisiran en hATTR amyloidosis.",
                conditions=["hATTR amyloidosis"],
                phase="Fase III",
                sponsor="Alnylam Pharmaceuticals",
                start_date="2023-01", completion_date="2025-12",
                min_age="18 años", max_age="85 años", sex="Todos",
                locations=["Boston, MA", "Buenos Aires, AR"],
                url="https://clinicaltrials.gov/study/NCT04104672",
            )
        ],
        bibliography=[
            Source(pmid="29470523", title="Hereditary transthyretin amyloidosis: a review",
                   journal="N Engl J Med", year=2019,
                   url="https://pubmed.ncbi.nlm.nih.gov/29470523/"),
            Source(pmid="31504380", title="Diabetic peripheral neuropathy",
                   journal="Lancet Neurol", year=2019,
                   url="https://pubmed.ncbi.nlm.nih.gov/31504380/"),
        ],
    )


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Endpoint FastAPI: POST /api/analyze")
    print(_SEP)

    # 1. Contrato del endpoint
    print("\n  [1/5] Contrato del endpoint:")
    print(f"        Método  : POST")
    print(f"        Ruta    : /api/analyze")
    print(f"        Auth    : ninguna (acceso local)")
    print(f"        Request : multipart/form-data")
    print(f"                  - file (PDF, opcional)")
    print(f"                  - text (texto plano, opcional)")
    print(f"                  ← al menos uno requerido")
    print(f"        Response: StructuredReport (JSON, HTTP 200)")
    print(f"        Errores : 422 si faltan ambos campos")
    print(f"                  415 si el PDF no tiene texto extraíble")

    # 2. Pipeline que ejecuta
    print(f"\n  [2/5] Pipeline que ejecuta el endpoint ({len(_PIPELINE_STEPS)} pasos):")
    for i, (paso, desc) in enumerate(_PIPELINE_STEPS, 1):
        print(f"        {i}. {paso:<35} → {desc}")

    # 3. Construir respuesta de ejemplo
    print(f"\n  [3/5] Construyendo StructuredReport de ejemplo...")
    report = _mock_structured_report()
    print(f"        ✓ metadata.nexus_version     : {report.metadata.nexus_version}")
    print(f"        ✓ metadata.processing_time   : {report.metadata.processing_time_seconds}s")
    print(f"        ✓ hypotheses count           : {len(report.hypotheses)}")
    print(f"        ✓ debate_summary.consensus   : {report.debate_summary.consensus_reached}")
    print(f"        ✓ clinical_trials count      : {len(report.clinical_trials)}")

    # 4. Serialización
    print(f"\n  [4/5] Serialización a JSON (lo que devuelve el endpoint)...")
    data = report.model_dump(mode="json")
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    print(f"        ✓ {len(json_str)} caracteres, {json_str.count(chr(10))} líneas")

    # 5. Ejemplo de llamada curl
    print(f"\n  [5/5] Cómo llamar al endpoint:")
    print(f"        # Con texto:")
    print(f'        curl -X POST http://localhost:8000/api/analyze \\')
    print(f'             -F "text=Paciente masculino 42 años, neuropatía axonal..."')
    print(f"")
    print(f"        # Con PDF:")
    print(f'        curl -X POST http://localhost:8000/api/analyze \\')
    print(f'             -F "file=@informe_clinico.pdf"')
    print(f"")
    print(f"        # Desde Python (frontend usa fetch()):")
    print(f'        import httpx')
    print(f'        r = httpx.post("http://localhost:8000/api/analyze",')
    print(f'                        data={{"text": texto_clinico}})')
    print(f'        report = r.json()')

    # Guardar artefactos
    contrato_txt = _OUT_DIR / "contrato_api.txt"
    with contrato_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Contrato del endpoint POST /api/analyze\n")
        f.write("=" * 60 + "\n\n")
        f.write("MÉTODO : POST\n")
        f.write("RUTA   : /api/analyze\n")
        f.write("DOCS   : http://localhost:8000/docs\n\n")
        f.write("REQUEST (multipart/form-data):\n")
        f.write("  - file : UploadFile (PDF, opcional)\n")
        f.write("  - text : str (texto clínico, opcional)\n")
        f.write("  → al menos uno es requerido\n\n")
        f.write("RESPONSE (HTTP 200 — StructuredReport JSON):\n")
        f.write("  - metadata        : versión, tiempo, disclaimer\n")
        f.write("  - case_summary    : narrativa PICO del caso\n")
        f.write("  - hypotheses      : lista rankeada por Priority + EvidenceLevel\n")
        f.write("  - debate_summary  : rondas, críticas, divergencias, consenso\n")
        f.write("  - clinical_trials : ensayos activos de ClinicalTrials.gov\n\n")
        f.write("ERRORES:\n")
        f.write("  422 : faltan file y text\n")
        f.write("  415 : PDF sin texto extraíble\n\n")
        f.write("PIPELINE (8 pasos):\n")
        for i, (paso, desc) in enumerate(_PIPELINE_STEPS, 1):
            f.write(f"  {i}. {paso}: {desc}\n")

    request_txt = _OUT_DIR / "ejemplo_request.txt"
    with request_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Ejemplos de llamada al endpoint\n")
        f.write("=" * 60 + "\n\n")
        f.write("# Con texto clínico:\n")
        f.write('curl -X POST http://localhost:8000/api/analyze \\\n')
        f.write('     -F "text=Paciente masculino 42 años con neuropatía axonal..."\n\n')
        f.write("# Con archivo PDF:\n")
        f.write('curl -X POST http://localhost:8000/api/analyze \\\n')
        f.write('     -F "file=@informe_clinico.pdf"\n\n')
        f.write("# Desde Python:\n")
        f.write("import httpx\n")
        f.write('r = httpx.post("http://localhost:8000/api/analyze",\n')
        f.write('               data={"text": texto_clinico})\n')
        f.write("report = StructuredReport(**r.json())\n\n")
        f.write("# Documentación interactiva (Swagger UI):\n")
        f.write("http://localhost:8000/docs\n")

    json_out = _OUT_DIR / "ejemplo_response.json"
    json_out.write_text(json_str, encoding="utf-8")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Endpoint       : POST /api/analyze")
    print(f"  Pipeline       : {len(_PIPELINE_STEPS)} pasos (extracción → debate → reporte)")
    print(f"  Response       : StructuredReport JSON ({len(json_str)} chars)")
    print(f"  Hipótesis      : {len(report.hypotheses)} rankeadas por Priority + EvidenceLevel")
    print(f"  Docs Swagger   : http://localhost:8000/docs")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Contrato API     → {contrato_txt}")
    print(f"    • Ejemplo request  → {request_txt}")
    print(f"    • Ejemplo response → {json_out}")
    print(_SEP)


if __name__ == "__main__":
    main()
