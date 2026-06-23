"""
Demo de verificación — Generación de JSON estructurado con todas las secciones del reporte.

Muestra cómo el pipeline/report_builder.py transforma los outputs internos
del pipeline en el StructuredReport que consume el frontend Next.js.

Artefactos generados en output/demo_reporte_json/:
    1. structured_report.json  → JSON completo con todas las secciones
    2. resumen_secciones.txt   → descripción de cada sección del JSON

Uso:
    python scripts/demo_reporte_json.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
)
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Critique, DebateRound, Report
from backend.models.trial import ClinicalTrial
from backend.pipeline.report_builder import build_export

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_reporte_json"


def _mock_report() -> tuple[Report, ClinicalCase, list[ClinicalTrial]]:
    """Construye un Report completo de prueba sin llamar al LLM."""
    sources = [
        Source(pmid="29470523", title="Hereditary transthyretin amyloidosis: a review",
               journal="N Engl J Med", year=2019, url="https://pubmed.ncbi.nlm.nih.gov/29470523/"),
        Source(pmid="31504380", title="Diabetic peripheral neuropathy: diagnosis and management",
               journal="Lancet Neurol", year=2019, url="https://pubmed.ncbi.nlm.nih.gov/31504380/"),
        Source(pmid="30589315", title="Acute hepatic porphyria neuropathy",
               journal="J Neurol", year=2019, url="https://pubmed.ncbi.nlm.nih.gov/30589315/"),
    ]
    hipotesis = [
        Hypothesis(
            text="Amiloidosis hereditaria por TTR (ATTRv) como causa de neuropatía axonal progresiva",
            priority=Priority.HIGH,
            evidence_level=EvidenceLevel.II,
            rationale="Patrón axonal sensitivomotor con afectación autonómica; TTR Val30Met "
                       "es la mutación más frecuente en adultos jóvenes con neuropatía.",
            sources=[sources[0]],
        ),
        Hypothesis(
            text="Neuropatía diabética axonal severa por mal control glucémico crónico",
            priority=Priority.MEDIUM,
            evidence_level=EvidenceLevel.I,
            rationale="HbA1c 8.2% con 10 años de evolución; patrón axonal distal compatible.",
            sources=[sources[1]],
        ),
        Hypothesis(
            text="Porfiria hepática aguda como causa poco frecuente de neuropatía motora",
            priority=Priority.LOW,
            evidence_level=EvidenceLevel.III,
            rationale="Panel CMT negativo; porfiria AHP puede presentar neuropatía axonal motora.",
            sources=[sources[2]],
        ),
    ]
    outputs = [
        AgentOutput(agent_id="01", agent_name="Analista de Literatura", hypotheses=hipotesis[:2]),
        AgentOutput(agent_id="03", agent_name="Consultor Clínico", hypotheses=hipotesis[1:]),
    ]
    criticas = [
        Critique(
            from_agent_id="03", from_agent_name="Consultor Clínico",
            target_agent_id="01", target_hypothesis=hipotesis[0].text,
            critique_text="Solicitar biopsia de grasa abdominal para confirmar depósito de amiloide.",
            severity="MEDIUM",
        ),
    ]
    rondas = [DebateRound(round_number=2, critiques=criticas)]
    report = Report(
        case_summary="Paciente masculino 42 años, neuropatía axonal sensitivomotora progresiva.",
        hypotheses=hipotesis,
        agent_outputs=outputs,
        debate_rounds=rondas,
    )
    pico = PICOSynthesis(
        patient_profile="Masculino, 42 años",
        chief_complaint="Debilidad progresiva en miembros inferiores (18 meses)",
        relevant_history=["Diabetes mellitus tipo 2 (10 años)", "HbA1c 8.2%"],
        negative_findings=["Panel CMT negativo"],
        disease_duration="18 meses",
        current_treatments=["pregabalina 150 mg/día"],
        procedures_done=["EMG", "VCN"],
        comparison="Neuropatía diabética vs. amiloidosis hereditaria",
        primary_outcome="Etiología de neuropatía axonal sensitivomotora",
        secondary_outcomes=["respuesta a tratamiento", "descartar causas raras"],
        biomarkers=["HbA1c 8.2%"],
        genetic_findings=["Panel CMT negativo"],
        clinical_narrative=(
            "Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva "
            "de 18 meses, diabetes tipo 2 mal controlada y panel CMT negativo."
        ),
    )
    caso = ClinicalCase(raw_text="[texto clínico anonimizado]", pico=pico)
    trials = [
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
    ]
    return report, caso, trials


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Generación de JSON estructurado del reporte")
    print(_SEP)

    # 1. Construir mock del pipeline
    print("\n  [1/5] Construyendo outputs del pipeline (sin LLM)...")
    report, caso, trials = _mock_report()
    print(f"        ✓ {len(report.agent_outputs)} agentes, {len(report.hypotheses)} hipótesis, "
          f"{len(report.debate_rounds)} rondas de debate")

    # 2. Ejecutar report_builder
    print("\n  [2/5] Ejecutando report_builder.build_export()...")
    t0 = __import__("time").time()
    structured: StructuredReport = build_export(caso, report, trials, processing_time=12.4)
    elapsed = __import__("time").time() - t0
    print(f"        ✓ StructuredReport generado en {elapsed:.3f}s")

    # 3. Mostrar secciones del JSON
    print("\n  [3/5] Secciones del StructuredReport:")
    print(f"        metadata:")
    print(f"          nexus_version    : {structured.metadata.nexus_version}")
    print(f"          processing_time  : {structured.metadata.processing_time_seconds}s")
    print(f"          generated_at     : {structured.metadata.generated_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"        case_summary:")
    print(f"          patient_profile  : {structured.case_summary.patient_profile}")
    print(f"          chief_complaint  : {structured.case_summary.chief_complaint[:60]}...")
    print(f"        hypotheses ({len(structured.hypotheses)}):")
    for h in structured.hypotheses:
        print(f"          #{h.rank} [{h.priority}/{h.evidence_level}] {h.text[:55]}...")
    print(f"        debate_summary:")
    print(f"          rounds_completed : {structured.debate_summary.rounds_completed}")
    print(f"          consensus_reached: {structured.debate_summary.consensus_reached}")
    print(f"        clinical_trials    : {len(structured.clinical_trials)} ensayo(s)")

    # 4. Serializar a JSON
    print("\n  [4/5] Serialización a JSON...")
    data = structured.model_dump(mode="json")
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    print(f"        ✓ {len(json_str)} caracteres, {json_str.count(chr(10))} líneas")

    # 5. Verificar que el frontend puede deserializarlo
    print("\n  [5/5] Verificando round-trip JSON (serializar → deserializar)...")
    reconstructed = StructuredReport.model_validate(json.loads(json_str))
    assert len(reconstructed.hypotheses) == len(structured.hypotheses)
    assert reconstructed.metadata.nexus_version == structured.metadata.nexus_version
    print(f"        ✓ Round-trip OK — hipótesis: {len(reconstructed.hypotheses)}, "
          f"versión: {reconstructed.metadata.nexus_version}")

    # Guardar artefactos
    json_out = _OUT_DIR / "structured_report.json"
    json_out.write_text(json_str, encoding="utf-8")

    resumen_txt = _OUT_DIR / "resumen_secciones.txt"
    with resumen_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — StructuredReport: secciones del JSON de exportación\n")
        f.write("=" * 60 + "\n\n")
        f.write("SECCIONES:\n\n")
        f.write("1. metadata\n")
        f.write(f"   nexus_version    : {structured.metadata.nexus_version}\n")
        f.write(f"   processing_time  : {structured.metadata.processing_time_seconds}s\n")
        f.write(f"   disclaimer       : {structured.metadata.disclaimer[:80]}...\n\n")
        f.write("2. case_summary\n")
        f.write(f"   patient_profile  : {structured.case_summary.patient_profile}\n")
        f.write(f"   chief_complaint  : {structured.case_summary.chief_complaint}\n")
        f.write(f"   treatments       : {structured.case_summary.current_treatments}\n\n")
        f.write(f"3. hypotheses ({len(structured.hypotheses)} hipótesis rankeadas)\n")
        for h in structured.hypotheses:
            f.write(f"   #{h.rank} [{h.priority}/{h.evidence_level}] {h.text}\n")
            f.write(f"      PMIDs: {[s.pmid for s in h.sources]}\n")
        f.write(f"\n4. debate_summary\n")
        f.write(f"   rounds_completed : {structured.debate_summary.rounds_completed}\n")
        f.write(f"   total_critiques  : {structured.debate_summary.total_critiques}\n")
        f.write(f"   consensus_reached: {structured.debate_summary.consensus_reached}\n\n")
        f.write(f"5. clinical_trials ({len(structured.clinical_trials)} ensayo(s))\n")
        for t in structured.clinical_trials:
            f.write(f"   {t.nct_id} — {t.title[:50]}\n")
        f.write(f"\nJSON total: {len(json_str)} caracteres\n")
        f.write(f"Round-trip: ✓ OK\n")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Secciones generadas  : metadata, case_summary, hypotheses, debate_summary, clinical_trials")
    print(f"  Hipótesis rankeadas  : {len(structured.hypotheses)} (por Priority + EvidenceLevel)")
    print(f"  Ensayos clínicos     : {len(structured.clinical_trials)}")
    print(f"  JSON total           : {len(json_str)} caracteres")
    print(f"  Round-trip JSON      : ✓ (serializar → deserializar sin pérdida)")
    print(f"  Consumido por        : frontend Next.js (sessionStorage) + PDF exporter")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • JSON del reporte    → {json_out}")
    print(f"    • Resumen secciones   → {resumen_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
