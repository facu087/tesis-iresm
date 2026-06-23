"""
Demo de verificación — Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial.

Muestra la construcción, validación y serialización de los modelos de datos
que estructuran toda la información del pipeline NEXUS.

Artefactos generados en output/demo_modelos_pydantic/:
    1. modelos_instanciados.txt  → ejemplo de cada modelo con sus campos
    2. reporte_json.json         → Report completo serializado a JSON

Uso:
    python scripts/demo_modelos_pydantic.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Critique, DebateRound, Report
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.biomarkers import BiomarkerProfile
from backend.models.trial import ClinicalTrial

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_modelos_pydantic"


def _construir_caso() -> ClinicalCase:
    pico = PICOSynthesis(
        patient_profile="Masculino, 42 años, diestro",
        chief_complaint="Debilidad progresiva en miembros inferiores, 18 meses de evolución",
        relevant_history=["Diabetes mellitus tipo 2 (10 años)", "HbA1c 8.2%"],
        negative_findings=["Panel genético CMT: negativo"],
        disease_duration="18 meses",
        current_treatments=["pregabalina 150 mg/día"],
        procedures_done=["EMG", "velocidad de conducción nerviosa"],
        comparison="Neuropatía diabética vs. neuropatía hereditaria",
        primary_outcome="Identificar etiología de neuropatía axonal sensitivomotora",
        secondary_outcomes=["evaluar respuesta a tratamiento", "descartar causas raras"],
        biomarkers=["HbA1c 8.2%"],
        genetic_findings=["Panel CMT negativo"],
        clinical_narrative=(
            "Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva "
            "de 18 meses de evolución, diabetes tipo 2 de larga data y panel CMT negativo."
        ),
    )
    return ClinicalCase(raw_text="[texto clínico anonimizado]", pico=pico)


def _construir_hipotesis() -> list[Hypothesis]:
    return [
        Hypothesis(
            text="Amiloidosis hereditaria por TTR como causa de neuropatía axonal progresiva",
            priority=Priority.HIGH,
            evidence_level=EvidenceLevel.II,
            rationale="Patrón axonal con afectación autonómica sin etiología clara; TTR Val30Met "
                       "es la mutación más frecuente en adultos jóvenes con neuropatía.",
            sources=[
                Source(
                    pmid="29470523",
                    title="Hereditary transthyretin amyloidosis: a review",
                    journal="N Engl J Med",
                    year=2019,
                    url="https://pubmed.ncbi.nlm.nih.gov/29470523/",
                )
            ],
        ),
        Hypothesis(
            text="Neuropatía diabética axonal severa como causa principal",
            priority=Priority.MEDIUM,
            evidence_level=EvidenceLevel.I,
            rationale="HbA1c 8.2% con 10 años de diabetes; el mal control glucémico "
                       "es el principal factor de riesgo de neuropatía axonal.",
            sources=[
                Source(
                    pmid="31504380",
                    title="Diabetic peripheral neuropathy: diagnosis and management",
                    journal="Lancet Neurology",
                    year=2019,
                    url="https://pubmed.ncbi.nlm.nih.gov/31504380/",
                )
            ],
        ),
    ]


def _construir_reporte(hipotesis: list[Hypothesis]) -> Report:
    outputs = [
        AgentOutput(
            agent_id="01",
            agent_name="Analista de Literatura",
            hypotheses=hipotesis,
        )
    ]
    critica = Critique(
        from_agent_id="03",
        from_agent_name="Consultor Clínico",
        target_agent_id="01",
        target_hypothesis=hipotesis[0].text,
        critique_text="Considerar solicitar biopsia de grasa abdominal para confirmar depósitos de amiloide.",
        severity="MEDIUM",
        alternative="Agregar estudio genético TTR como primer paso diagnóstico.",
    )
    ronda = DebateRound(round_number=2, critiques=[critica])
    return Report(
        case_summary="Paciente masculino 42 años, neuropatía axonal sensitivomotora progresiva.",
        hypotheses=hipotesis,
        agent_outputs=outputs,
        debate_rounds=[ronda],
    )


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial")
    print(_SEP)

    # 1. ClinicalCase
    print("\n  [1/5] ClinicalCase + PICOSynthesis:")
    caso = _construir_caso()
    print(f"        raw_text     : {caso.raw_text}")
    print(f"        patient      : {caso.pico.patient_profile}")
    print(f"        complaint    : {caso.pico.chief_complaint}")
    print(f"        treatments   : {caso.pico.current_treatments}")
    print(f"        pico.biomarkers : {caso.pico.biomarkers}")

    # 2. Hypothesis + Source
    print("\n  [2/5] Hypothesis + Source:")
    hipotesis = _construir_hipotesis()
    for h in hipotesis:
        print(f"        [{h.priority.value}/{h.evidence_level.value}] {h.text[:60]}...")
        print(f"          fuentes: {[s.pmid for s in h.sources]}")

    # 3. BiomarkerProfile
    print("\n  [3/5] BiomarkerProfile:")
    bio = BiomarkerProfile(
        genes=["TTR"],
        lab_biomarkers=["HbA1c 8.2%"],
        drugs=["pregabalina"],
        procedures=["EMG", "velocidad de conducción nerviosa"],
    )
    print(f"        genes        : {bio.genes}")
    print(f"        lab_biomarkers: {bio.lab_biomarkers}")
    print(f"        drugs        : {bio.drugs}")
    print(f"        is_empty()   : {bio.is_empty()}")
    print(f"        summary()    : {bio.summary()}")

    # 4. ClinicalTrial
    print("\n  [4/5] ClinicalTrial:")
    trial = ClinicalTrial(
        nct_id="NCT04104672",
        title="Patisiran para amiloidosis por transtiretina hereditaria con neuropatía",
        status="RECRUITING",
        phase="Fase III",
        brief_summary="Estudio de eficacia y seguridad de patisiran en pacientes adultos con hATTR.",
        conditions=["hATTR amyloidosis", "Polineuropatía"],
        sponsor="Alnylam Pharmaceuticals",
        start_date="2023-01",
        completion_date="2025-12",
        min_age="18 años",
        max_age="85 años",
        sex="Todos",
        locations=["Boston, MA", "Londres, UK", "Buenos Aires, AR"],
        url="https://clinicaltrials.gov/study/NCT04104672",
    )
    print(f"        nct_id  : {trial.nct_id}")
    print(f"        status  : {trial.status}")
    print(f"        phase   : {trial.phase}")
    print(f"        sponsor : {trial.sponsor}")
    print(f"        sedes   : {trial.locations}")

    # 5. Report completo → JSON
    print("\n  [5/5] Report completo → serialización JSON:")
    reporte = _construir_reporte(hipotesis)
    print(f"        agent_outputs   : {len(reporte.agent_outputs)} agente(s)")
    print(f"        debate_rounds   : {len(reporte.debate_rounds)} ronda(s)")
    print(f"        hypotheses       : {len(reporte.hypotheses)} hipótesis")
    reporte_json = reporte.model_dump()
    print(f"        JSON válido     : ✓ ({len(json.dumps(reporte_json))} caracteres)")

    # Guardar artefactos
    modelos_txt = _OUT_DIR / "modelos_instanciados.txt"
    with modelos_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Modelos Pydantic instanciados\n")
        f.write("=" * 60 + "\n\n")
        f.write("ClinicalCase:\n")
        f.write(f"  patient_profile : {caso.pico.patient_profile}\n")
        f.write(f"  chief_complaint : {caso.pico.chief_complaint}\n")
        f.write(f"  treatments      : {caso.pico.current_treatments}\n\n")
        f.write("Hypotheses:\n")
        for h in hipotesis:
            f.write(f"  [{h.priority.value}/{h.evidence_level.value}] {h.text}\n")
            f.write(f"    PMIDs: {[s.pmid for s in h.sources]}\n\n")
        f.write("BiomarkerProfile:\n")
        f.write(f"  {bio.summary()}\n\n")
        f.write("ClinicalTrial:\n")
        f.write(f"  {trial.nct_id} — {trial.title}\n")
        f.write(f"  Status: {trial.status}, Phase: {trial.phase}\n\n")
        f.write("Report:\n")
        f.write(f"  hypotheses        : {len(reporte.hypotheses)}\n")
        f.write(f"  debate_rounds     : {len(reporte.debate_rounds)}\n")

    json_out = _OUT_DIR / "reporte_json.json"
    json_out.write_text(json.dumps(reporte_json, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  ClinicalCase     : ✓ (raw_text + PICOSynthesis con 12 campos)")
    print(f"  Hypothesis       : ✓ (Priority, EvidenceLevel, Source con PMID/URL)")
    print(f"  BiomarkerProfile : ✓ (genes, lab_biomarkers, drugs, procedures)")
    print(f"  ClinicalTrial    : ✓ (NCT ID, status, phase, locations)")
    print(f"  Report           : ✓ (AgentOutput, DebateRound, Critique, consensus)")
    print(f"  Serialización    : ✓ JSON válido ({len(json.dumps(reporte_json))} chars)")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Modelos instanciados → {modelos_txt}")
    print(f"    • Report JSON          → {json_out}")
    print(_SEP)


if __name__ == "__main__":
    main()
