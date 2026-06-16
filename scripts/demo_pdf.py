"""
Demo de verificación — Exportación del reporte a PDF (ReportLab).

Construye un StructuredReport de ejemplo (sin LLM) y genera el PDF final del
reporte NEXUS, tal como lo descarga el usuario desde el frontend. El PDF es el
artefacto tangible: se abre y se captura directamente para Trello.

Guarda como artefacto tangible para Trello:
    output/demo_pdf/reporte_nexus.pdf

Uso:
    python scripts/demo_pdf.py
"""

import sys
from datetime import datetime
from pathlib import Path

# Permite importar el paquete backend sin instalar
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
from backend.pipeline.pdf_exporter import generate_pdf

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_pdf"


def _build_report() -> StructuredReport:
    """Arma un reporte completo de ejemplo (caso base de la tesis)."""
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime(2026, 6, 16, 10, 30),
            nexus_version="0.3.0",
            processing_time_seconds=54.2,
        ),
        case_summary=CaseSummarySection(
            narrative=(
                "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
                "progresiva de 18 meses de evolución, con compromiso autonómico "
                "(hipotensión ortostática, disfunción sudomotora). EMG con patrón axonal "
                "difuso. Panel genético CMT, LCR y anticuerpos paraneoplásicos negativos. "
                "Diabetes tipo 2 de larga data. Tres años sin diagnóstico etiológico."
            ),
            patient_profile="Paciente masculino de 42 años",
            chief_complaint="Neuropatía axonal sensitivomotora progresiva",
            disease_duration="18 meses",
            current_treatments=["Pregabalina 150 mg/día"],
            relevant_history=["Diabetes tipo 2 de 10 años (HbA1c 8.2%)",
                              "Padre con problemas de equilibrio no estudiados"],
            procedures_done=["Electromiografía (patrón axonal difuso, sural ausente bilateral)"],
        ),
        hypotheses=[
            RankedHypothesis(
                rank=1,
                text="Neuropatía diabética avanzada con compromiso autonómico",
                priority="HIGH",
                evidence_level="II",
                rationale=(
                    "Diabetes de larga data con control subóptimo (HbA1c 8.2%) y "
                    "compromiso autonómico compatible. Causa parcialmente reversible "
                    "con control glucémico estricto."
                ),
                supporting_agents=["01", "03"],
                sources=[Source(pmid="29199211", title="Diabetic neuropathy: a review",
                                journal="International Review of Neurobiology", year=2017)],
            ),
            RankedHypothesis(
                rank=2,
                text="Amiloidosis hereditaria por TTR (causa tratable a descartar)",
                priority="HIGH",
                evidence_level="III",
                rationale=(
                    "Compromiso autonómico + neuropatía axonal + antecedente familiar. "
                    "Causa tratable con terapias estabilizadoras de TTR; requiere estudio "
                    "genético específico no incluido en el panel CMT."
                ),
                supporting_agents=["03"],
                sources=[Source(title="Familial Amyloid Polyneuropathy", journal="Orphanet", year=2020)],
            ),
            RankedHypothesis(
                rank=3,
                text="Neuropatía por déficit de vitamina B12",
                priority="MEDIUM",
                evidence_level="II",
                rationale=(
                    "Causa tratable y reversible que debe descartarse siempre en "
                    "neuropatía axonal de etiología no aclarada."
                ),
                supporting_agents=["03"],
                sources=[],
            ),
        ],
        debate_summary=DebateSummary(
            rounds_completed=4,
            total_critiques=5,
            divergences=[],
            consensus_reached=True,
        ),
        clinical_trials=[
            ClinicalTrial(
                nct_id="NCT06845644",
                title="Longitudinal Quantitative Neuromuscular MRI in Neuropathic Patients",
                status="RECRUITING",
                brief_summary=("Estudio longitudinal de RMN neuromuscular cuantitativa en "
                               "pacientes con neuropatías hereditarias, incluyendo amiloidosis por TTR."),
                conditions=["Hereditary Transthyretin Amyloid Neuropathy",
                            "Charcot-Marie-Tooth Neuropathy Type 1A"],
                phase="NA",
                sponsor="Assistance Publique Hopitaux De Marseille",
                locations=["France"],
                url="https://clinicaltrials.gov/study/NCT06845644",
            ),
        ],
        bibliography=[
            Source(pmid="29199211", title="Diabetic neuropathy: a review",
                   journal="International Review of Neurobiology", year=2017),
            Source(title="Familial Amyloid Polyneuropathy", journal="Orphanet", year=2020),
        ],
    )


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Exportación del reporte a PDF (ReportLab)")
    print(_SEP)

    report = _build_report()
    print("  Reporte de ejemplo construido:")
    print(f"     • Hipótesis priorizadas : {len(report.hypotheses)}")
    print(f"     • Ensayos clínicos       : {len(report.clinical_trials)}")
    print(f"     • Referencias            : {len(report.bibliography)}")
    print(f"     • Rondas de debate       : {report.debate_summary.rounds_completed}")
    print(_SEP)
    print("  Generando PDF con ReportLab…")

    pdf_bytes = generate_pdf(report)

    salida = _OUT_DIR / "reporte_nexus.pdf"
    salida.write_bytes(pdf_bytes)

    print(_SEP)
    print(f"  ✓ PDF generado correctamente — {len(pdf_bytes):,} bytes.")
    print(f"    Cabecera del archivo: {pdf_bytes[:5]!r} (firma %PDF válida)")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Reporte PDF → {salida}")
    print(f"    Abrilo con:  xdg-open {salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
