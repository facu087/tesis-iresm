"""
Demo del Agente 06 — Sintetizador (evidencia para Trello, tarjeta #62).

Arma un StructuredReport a mano (caso base: neuropatía axonal, varón de 42 años),
llama a SynthesizerAgent().synthesize() y muestra el resumen, más la guarda
anti-invención aplicada a tres textos de ejemplo.

Uso:
    python3 scripts/demo_agente06.py           # con GROQ_API_KEY
    NEXUS_MOCK_LLM=1 python3 scripts/demo_agente06.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv()

from backend.agents.agent_06_synthesizer import SynthesizerAgent, build_context, check_invention
from tests.test_agent_06_synthesizer import NCT_OK, PMID_OK, _report

SALIDA = RAIZ / "output" / "demo_agente06"

EJEMPLOS_GUARDA = {
    "limpio": f"Sugiere amiloidosis por TTR (PMID {PMID_OK}); el ensayo {NCT_OK} es candidato.",
    "pmid_inventado": "Respaldado por PMID 99999999.",
    "nct_inventado": "Considerar el ensayo NCT09999999.",
    "gen_inventado": "Podría explicarse por una variante en MFN2.",
}


def main() -> int:
    report = _report()
    print("=== ENTRADA (contexto enviado al LLM) ===")
    print(build_context(report))

    resumen = asyncio.run(SynthesizerAgent().synthesize(report))
    print("\n=== SALIDA (executive_summary) ===")
    print(resumen if resumen else "None (LLM sin respuesta o resumen descartado por la guarda)")

    print("\n=== GUARDA ANTI-INVENCIÓN ===")
    guarda = {}
    for nombre, texto in EJEMPLOS_GUARDA.items():
        infractor = check_invention(texto, report)
        guarda[nombre] = {"texto": texto, "infractor": infractor,
                          "resultado": "aceptado" if infractor is None else "descartado"}
        print(f"- {nombre:15s} → {guarda[nombre]['resultado']}"
              + (f" (cita {infractor})" if infractor else ""))

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "resumen.json").write_text(json.dumps(
        {"executive_summary": resumen, "guarda": guarda}, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    print(f"\nGuardado en {SALIDA / 'resumen.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
