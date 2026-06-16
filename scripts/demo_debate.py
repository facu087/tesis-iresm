"""
Demo de verificación — Motor de debate adversarial (Rondas 2–4).

Tras la Ronda 1 (donde cada agente genera hipótesis), el debate las somete a
crítica cruzada y revisión:
    • Ronda 2 — cada agente CRITICA las hipótesis de los demás (paralelo).
    • Ronda 3 — cada agente REVISA sus hipótesis según las críticas recibidas.
    • Ronda 4 — revisión final, refinando la posición.
Al cierre se detectan DIVERGENCIAS: hipótesis criticadas como HIGH que se
mantuvieron sin cambios (señal de desacuerdo entre agentes).

Para enfocar el demo en el DEBATE, la Ronda 1 se arma a mano (sin LLM): así las
6 llamadas a Groq son únicamente las del debate (3 rondas × 2 agentes en paralelo).

⚠ Es el demo más pesado en cupo de Groq. Si aparece rate limit, el sistema
reintenta con back-off automáticamente (puede tardar 1–2 minutos).

Guarda como artefacto tangible para Trello:
    output/demo_debate/reporte_debate.json

Uso:
    python scripts/demo_debate.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import AgentOutput, Report
from backend.pipeline import debate

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_debate"

# ── PICO precargado (caso base de la tesis) ────────────────────────────────────
_PICO = PICOSynthesis(
    patient_profile="Paciente masculino de 42 años",
    chief_complaint="Neuropatía axonal sensitivomotora progresiva",
    relevant_history=["Diabetes tipo 2 de 10 años (HbA1c 8.2%)",
                      "Padre con problemas de equilibrio no estudiados"],
    negative_findings=["Panel genético CMT (40 genes) negativo", "LCR normal",
                       "Anticuerpos paraneoplásicos negativos"],
    disease_duration="18 meses",
    current_treatments=["Pregabalina 150 mg/día"],
    procedures_done=["Electromiografía (patrón axonal difuso)"],
    comparison="No aplica",
    primary_outcome="Determinar la etiología de la neuropatía tras 3 años sin diagnóstico",
    secondary_outcomes=["Identificar causas tratables"],
    biomarkers=["HbA1c 8.2%"],
    genetic_findings=["Panel CMT negativo"],
    clinical_narrative=(
        "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
        "progresiva de 18 meses, con compromiso autonómico. Diabetes tipo 2. "
        "Panel CMT, LCR y anticuerpos paraneoplásicos negativos. Sin diagnóstico."
    ),
)

# ── Ronda 1 precargada (hipótesis realistas de cada agente) ────────────────────
def _h(text, prio, ev, rationale):
    return Hypothesis(text=text, priority=Priority(prio),
                      evidence_level=EvidenceLevel(ev), rationale=rationale, sources=[])

_ROUND_1 = Report(
    case_summary=_PICO.clinical_narrative,
    agent_outputs=[
        AgentOutput(agent_id="01", agent_name="Analista de Literatura", hypotheses=[
            _h("Neuropatía diabética avanzada como causa de la polineuropatía axonal",
               "HIGH", "II", "Diabetes de larga data con HbA1c 8.2% y compromiso autonómico."),
            _h("Neuropatía hereditaria no detectada por el panel CMT de 40 genes",
               "MEDIUM", "III", "Antecedente paterno de problemas de equilibrio."),
            _h("Polineuropatía desmielinizante inflamatoria crónica (CIDP) atípica",
               "MEDIUM", "II", "Curso progresivo; algunas formas axonales existen."),
        ]),
        AgentOutput(agent_id="03", agent_name="Consultor Clínico", hypotheses=[
            _h("Amiloidosis hereditaria por TTR (causa tratable a descartar)",
               "HIGH", "III", "Compromiso autonómico + neuropatía axonal + antecedente familiar."),
            _h("Neuropatía por déficit de vitamina B12 (causa tratable)",
               "MEDIUM", "II", "Causa reversible que debe descartarse siempre."),
        ]),
    ],
)


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    case = ClinicalCase(raw_text="(precargado)", pico=_PICO)

    print(_SEP)
    print("  DEMO — Motor de debate adversarial (Rondas 2–4)")
    print(_SEP)
    print("  PUNTO DE PARTIDA (Ronda 1 precargada):")
    for o in _ROUND_1.agent_outputs:
        print(f"     • {o.agent_name} (ID {o.agent_id}): {len(o.hypotheses)} hipótesis")
    print(_SEP)
    print("  Ejecutando debate (6 llamadas a Groq: 3 rondas × 2 agentes)…")
    print("  Esto puede tardar si hay rate limit (reintenta con back-off).")
    print(_SEP)

    try:
        t0 = time.perf_counter()
        report = asyncio.run(debate.run_debate(case, _ROUND_1))
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        print("  ⚠ El debate no pudo completar (probablemente límite de Groq):")
        print(f"    {type(exc).__name__}: {str(exc)[:140]}")
        print("    Reintentá cuando el cupo de la API se haya reseteado.")
        print(_SEP)
        return

    print(f"  ✓ Debate completado en {elapsed:.0f} s.")
    print(_SEP)

    # ── Ronda 2: críticas ──────────────────────────────────────────
    round_2 = report.debate_rounds[0]
    print(f"  RONDA 2 — CRÍTICA CRUZADA: {len(round_2.critiques)} críticas emitidas")
    print(_SEP)
    for c in round_2.critiques:
        print(f"  [{c.severity}] {c.from_agent_name} → Agente {c.target_agent_id}")
        print(f"     Sobre: \"{c.target_hypothesis[:90]}\"")
        print(f"     Crítica: {c.critique_text[:160]}")
        if c.alternative:
            print(f"     Alternativa: {c.alternative[:120]}")
        print()
    print(_SEP)

    # ── Rondas 3 y 4: revisiones ───────────────────────────────────
    for dr in report.debate_rounds[1:]:
        total = sum(len(o.hypotheses) for o in dr.agent_outputs)
        print(f"  RONDA {dr.round_number} — REVISIÓN: {total} hipótesis tras revisar")
    print(_SEP)

    # ── Divergencias ───────────────────────────────────────────────
    print(f"  DIVERGENCIAS DETECTADAS: {len(report.divergences)}")
    if report.divergences:
        for d in report.divergences:
            print(f"     ⚠ {d}")
    else:
        print("     (ninguna — los agentes alcanzaron consenso tras el debate)")
    print(_SEP)

    print(f"  HIPÓTESIS FINALES (post-debate): {len(report.hypotheses)}")
    print(_SEP)

    # Guardar artefacto (sin respuestas crudas)
    salida = _OUT_DIR / "reporte_debate.json"
    salida.write_text(
        json.dumps(
            report.model_dump(exclude={
                "agent_outputs": {"__all__": {"raw_response"}},
                "debate_rounds": {"__all__": {"agent_outputs": {"__all__": {"raw_response"}}}},
            }),
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"  ✓ Reporte del debate generado.")
    print()
    print("  ARTEFACTO GENERADO (abrir y capturar para Trello):")
    print(f"    • Reporte del debate (JSON) → {salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
