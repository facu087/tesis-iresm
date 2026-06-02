"""
Script de prueba — Sprint 1 PoC
Caso clínico: neuropatía axonal sensitivomotora progresiva (paciente 42 años)

Uso:
    cd /path/to/Tesis
    ANTHROPIC_API_KEY=tu_clave python scripts/poc_test.py

    O con .env:
    cp .env.example .env  # completar con tu API key
    python scripts/poc_test.py
"""

import json
import os
import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.agents import agent_01_literature

CASO_CLINICO = """
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Compromiso autonómico asociado (hipotensión ortostática,
disfunción sudomotora). Panel genético reducido (CMT panel de 40 genes) negativo.
Electromiograma: axonal difuso sin desmielinización. LCR normal. Anticuerpos
paraneoplásicos estándar (anti-Hu, anti-Yo, anti-Ri) negativos. 3 años de
seguimiento sin diagnóstico. Edad de inicio: 40 años. Antecedentes familiares:
padre con "problemas de equilibrio" no estudiados.
""".strip()


def validar_output(output) -> list[str]:
    """Verifica que el output cumple los criterios mínimos del PoC."""
    errores = []
    if len(output.hypotheses) < 3:
        errores.append(f"Se esperaban al menos 3 hipótesis, se obtuvieron {len(output.hypotheses)}")
    prioridades = {h.priority for h in output.hypotheses}
    if len(prioridades) < 2:
        errores.append("Las hipótesis deben tener al menos 2 niveles de prioridad distintos")
    hipotesis_con_fuentes = [h for h in output.hypotheses if h.sources]
    if len(hipotesis_con_fuentes) < 1:
        errores.append("Al menos 1 hipótesis debe tener fuentes bibliográficas")
    return errores


def main():
    print("=" * 60)
    print("NEXUS — Sprint 1 PoC")
    print("Caso: Neuropatía axonal sensitivomotora, 42 años")
    print("=" * 60)

    if not os.environ.get("GROQ_API_KEY"):
        print("\n⚠  GROQ_API_KEY no encontrada.")
        print("   Copiá .env.example a .env y completá la API key.")
        sys.exit(1)

    print("\nEjecutando Agente 01 — Analista de Literatura...")
    print("(Primera llamada puede tardar unos segundos)\n")

    try:
        output = agent_01_literature.run(CASO_CLINICO)
    except Exception as e:
        print(f"✗ Error al ejecutar el agente: {e}")
        sys.exit(1)

    # ── Mostrar resultado ──────────────────────────────────────────
    print(f"Agente: {output.agent_name} (ID: {output.agent_id})")
    print(f"Hipótesis generadas: {len(output.hypotheses)}\n")

    for i, h in enumerate(output.hypotheses, 1):
        print(f"{'─' * 50}")
        print(f"Hipótesis #{i} [{h.priority.value}] — Evidencia nivel {h.evidence_level.value}")
        print(f"  {h.text}")
        print(f"  Fundamento: {h.rationale[:200]}...")
        if h.sources:
            print(f"  Fuentes ({len(h.sources)}):")
            for s in h.sources:
                pmid_str = f"PMID:{s.pmid} — " if s.pmid else ""
                print(f"    • {pmid_str}{s.title[:80]} ({s.year})")
        else:
            print("  Fuentes: ninguna (hipótesis especulativa)")

    # ── Validación ─────────────────────────────────────────────────
    print(f"\n{'═' * 50}")
    errores = validar_output(output)
    if errores:
        print("⚠  VALIDACIÓN FALLIDA:")
        for e in errores:
            print(f"   • {e}")
    else:
        print("✅ Validación OK — Output cumple criterios mínimos del PoC")

    # ── Exportar JSON ──────────────────────────────────────────────
    output_path = Path(__file__).parent.parent / "output" / "poc_result.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON exportado: {output_path}")


if __name__ == "__main__":
    main()
