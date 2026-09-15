"""
Demo — El debate sobrevive a un agente caído en la Ronda 1.

Muestra el problema y el arreglo. `run_round_1()` excluye de `agent_outputs` a
los agentes que fallaron (timeout de Groq, rate limit, JSON inválido), así que
el debate recibe menos outputs que agentes instanciados. `run_debate()` indexaba
`outputs_by_id[agent.AGENT_ID]` sin filtrar y saltaba `KeyError`, que se
propagaba hasta tumbar `POST /api/analyze` entero: un agente caído hacía perder
también el trabajo del que sí había respondido.

No consulta APIs externas ni necesita GROQ_API_KEY: los agentes están mockeados
para que la demo sea reproducible.

    python scripts/demo_debate_agente_caido.py

Artefactos generados en output/demo_debate_agente_caido/:
    1. salida.txt   → la corrida completa, antes y después
    2. resumen.json → el Report resultante, con la constancia del ausente
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# La consola de Windows usa cp1252 y no puede imprimir los caracteres de caja.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.report import AgentOutput, Report
from backend.pipeline.debate import run_debate

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_debate_agente_caido"


def _pico() -> PICOSynthesis:
    return PICOSynthesis(
        patient_profile="Paciente masculino de 42 años",
        chief_complaint="Neuropatía axonal sensitivomotora progresiva",
        condition_en="axonal sensorimotor polyneuropathy",
        relevant_history=["Padre con trastorno de la marcha no estudiado"],
        negative_findings=["Panel genético CMT de 40 genes negativo"],
        disease_duration="18 meses",
        current_treatments=[],
        procedures_done=["Electromiograma", "Punción lumbar"],
        comparison="No aplica",
        primary_outcome="Identificar la etiología de la neuropatía",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative="Varón de 42 años con neuropatía axonal de 18 meses.",
    )


def _ronda_1_con_agente_caido() -> Report:
    """Ronda 1 real del caso de la tesis en la que el Agente 03 no respondió."""
    hipotesis = Hypothesis(
        text="Evaluar amiloidosis hereditaria por transtiretina (ATTRv)",
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        rationale="Neuropatía axonal con compromiso autonómico y antecedente familiar.",
    )
    return Report(
        case_summary="Varón de 42 años con neuropatía axonal de 18 meses.",
        hypotheses=[hipotesis],
        agent_outputs=[
            AgentOutput(
                agent_id="01",
                agent_name="Analista de Literatura",
                hypotheses=[hipotesis],
                raw_response="{}",
            )
        ],
        sources_summary={"I": 0, "II": 0, "III": 0},
    )


def _mockear_agentes(M01, M03):
    a01 = MagicMock()
    a01.AGENT_ID, a01.AGENT_NAME = "01", "Analista de Literatura"
    a01.critique.return_value = []
    a01.revise.return_value = AgentOutput(
        agent_id="01", agent_name="Analista de Literatura", hypotheses=[], raw_response="{}"
    )
    M01.return_value = a01

    a03 = MagicMock()
    a03.AGENT_ID, a03.AGENT_NAME = "03", "Consultor Clínico"
    M03.return_value = a03
    return a01, a03


def main() -> None:
    print(_SEP)
    print("DEMO — El debate cuando un agente se cae en la Ronda 1")
    print(_SEP)

    ronda_1 = _ronda_1_con_agente_caido()
    ids_con_output = sorted(o.agent_id for o in ronda_1.agent_outputs)

    print("\nENTRADA — Report de la Ronda 1")
    print(f"  Agentes instanciados por run_debate(): ['01', '03']")
    print(f"  Agentes con output en la Ronda 1:      {ids_con_output}")
    print(f"  El Agente 03 falló y quedó fuera de agent_outputs.")

    # ── ANTES ────────────────────────────────────────────────────────────────
    print(f"\n{'─' * 78}\nANTES — indexar sin filtrar (debate.py:101, :130, :145)\n{'─' * 78}")
    outputs_by_id = {o.agent_id: o for o in ronda_1.agent_outputs}
    try:
        for agent_id in ["01", "03"]:
            _ = outputs_by_id[agent_id]
        print("  (no debería llegar acá)")
    except KeyError as exc:
        print(f"  KeyError: {exc}")
        print("  → la excepción sube por run_debate() y tumba POST /api/analyze.")
        print("  → se pierde también la hipótesis que el Agente 01 sí había producido.")

    # ── DESPUÉS ──────────────────────────────────────────────────────────────
    print(f"\n{'─' * 78}\nDESPUÉS — el debate corre solo con los que respondieron\n{'─' * 78}")
    caso = ClinicalCase(raw_text="texto clínico normalizado", pico=_pico())
    with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
         patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
        a01, a03 = _mockear_agentes(M01, M03)
        reporte = asyncio.run(run_debate(caso, ronda_1))

    print(f"  Report devuelto        : OK, sin excepción")
    print(f"  Agentes ausentes       : {reporte.absent_agents}")
    print(f"  Rondas de debate        : {len(reporte.debate_rounds)}")
    print(f"  Hipótesis conservadas   : {len(reporte.hypotheses)}")
    for h in reporte.hypotheses:
        print(f"      • {h.text}")
    print(f"  Llamadas al LLM gastadas: {a01.critique.call_count + a01.revise.call_count}")
    print("\n  Con un solo agente no hay debate adversarial posible: nadie a quien")
    print("  criticar ni críticas que responder. Se devuelven las hipótesis de la")
    print("  Ronda 1 con la constancia, en vez de simular tres rondas vacías y")
    print("  reportar un consenso que nunca se debatió.")

    # ── Artefactos ───────────────────────────────────────────────────────────
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    resumen = _OUT_DIR / "resumen.json"
    resumen.write_text(
        json.dumps(reporte.model_dump(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n{_SEP}\nArtefacto: {resumen}\n{_SEP}")


if __name__ == "__main__":
    main()
