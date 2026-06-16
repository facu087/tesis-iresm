"""
Demo de verificación — Clase base de agentes (BaseAgent, interfaz común).

BaseAgent es una clase ABSTRACTA (ABC): define la interfaz y la lógica común que
todos los agentes comparten, pero no se puede instanciar directamente. Cada agente
concreto (01, 03, …) hereda de ella y solo define su prompt y su identidad.

Este demo NO usa el LLM: verifica la parte determinista de la clase base:
    1. Es abstracta: instanciarla directamente falla (obliga a implementar run()).
    2. Un agente concreto debe implementar run() para poder instanciarse.
    3. Parseo robusto de JSON: tolera fences de markdown y texto alrededor.
    4. Validación de hipótesis con Pydantic (parse_hypotheses).
    5. Los agentes 01 y 03 heredan la misma interfaz.

Uso:
    python scripts/demo_base_agent.py
"""

import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.base_agent import BaseAgent
from backend.agents.agent_01_literature import LiteratureAnalystAgent
from backend.agents.agent_03_clinical import ClinicalConsultantAgent
from backend.models.report import AgentOutput

_SEP = "═" * 70
_OK = "  ✓"


def main() -> None:
    print(_SEP)
    print("  DEMO — Clase base de agentes (BaseAgent / interfaz común)")
    print(_SEP)

    # ── 1. No se puede instanciar la clase abstracta ───────────────────────────
    print("  1) BaseAgent es abstracta (no instanciable directamente):")
    try:
        BaseAgent()  # type: ignore[abstract]
        print("     ✗ ERROR: se pudo instanciar (no debería).")
    except TypeError as e:
        print(f"{_OK} Instanciar BaseAgent() lanzó TypeError, como se espera.")
        print(f"       → {str(e)[:90]}")
    print(_SEP)

    # ── 2. Una subclase sin run() tampoco se puede instanciar ──────────────────
    print("  2) Una subclase DEBE implementar run() para instanciarse:")

    class AgenteIncompleto(BaseAgent):
        AGENT_ID = "99"
        AGENT_NAME = "Incompleto"
        # no implementa run()

    try:
        AgenteIncompleto()  # type: ignore[abstract]
        print("     ✗ ERROR: se instanció sin implementar run().")
    except TypeError:
        print(f"{_OK} Subclase sin run() → TypeError (la interfaz se respeta).")

    class AgenteValido(BaseAgent):
        AGENT_ID = "98"
        AGENT_NAME = "Válido"
        SYSTEM_PROMPT = "..."
        def run(self, clinical_context: str) -> AgentOutput:
            return self._build_output([], "")

    instancia = AgenteValido()
    print(f"{_OK} Subclase con run() implementado → se instancia OK "
          f"(Agente {instancia.AGENT_ID}: {instancia.AGENT_NAME}).")
    print(_SEP)

    # ── 3. Parseo robusto de JSON (lógica compartida) ──────────────────────────
    print("  3) extract_json() tolera respuestas 'sucias' del LLM:")
    casos = {
        "JSON puro":            '{"hypotheses": []}',
        "con fences markdown":  '```json\n{"hypotheses": []}\n```',
        "con texto alrededor":  'Claro, aquí tienes:\n{"hypotheses": []}\n¡Saludos!',
    }
    for nombre, raw in casos.items():
        data = BaseAgent.extract_json(raw)
        ok = isinstance(data, dict) and "hypotheses" in data
        print(f"{_OK if ok else '  ✗'} {nombre:<22} → parseado correctamente: {data}")
    print(_SEP)

    # ── 4. Validación de hipótesis con Pydantic ────────────────────────────────
    print("  4) parse_hypotheses() valida y tipa la salida (Pydantic):")
    raw_respuesta = """```json
    {
      "hypotheses": [
        {
          "text": "Amiloidosis hereditaria por TTR como causa tratable",
          "priority": "HIGH",
          "evidence_level": "III",
          "rationale": "Compromiso autonómico + antecedente familiar.",
          "sources": [{"pmid": "12345678", "title": "ATTR review", "journal": "Brain", "year": 2021}]
        }
      ]
    }
    ```"""
    hipotesis = BaseAgent.parse_hypotheses(raw_respuesta)
    h = hipotesis[0]
    print(f"{_OK} Parseadas {len(hipotesis)} hipótesis tipadas:")
    print(f"       texto      : {h.text}")
    print(f"       prioridad  : {h.priority.value}  (enum Priority)")
    print(f"       evidencia  : {h.evidence_level.value}  (enum EvidenceLevel)")
    print(f"       fuentes    : {len(h.sources)} (PMID {h.sources[0].pmid})")
    print(_SEP)

    # ── 5. Los agentes concretos heredan la interfaz ───────────────────────────
    print("  5) Los agentes del pipeline heredan de BaseAgent:")
    for agente in (LiteratureAnalystAgent, ClinicalConsultantAgent):
        es_subclase = issubclass(agente, BaseAgent)
        inst = agente()
        print(f"{_OK if es_subclase else '  ✗'} {inst.AGENT_NAME:<24} "
              f"(ID {inst.AGENT_ID}) — issubclass(BaseAgent) = {es_subclase}")
    print(_SEP)

    print("  ✓ Interfaz común verificada: contrato abstracto + lógica compartida.")
    print(_SEP)


if __name__ == "__main__":
    main()
