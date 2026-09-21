"""
Clase base para todos los agentes de análisis de NEXUS.

Cada agente especializado hereda de BaseAgent y solo necesita definir:
  - AGENT_ID      → identificador único (ej: "01")
  - AGENT_NAME    → nombre legible (ej: "Analista de Literatura")
  - MODEL         → modelo de LLM a usar
  - SYSTEM_PROMPT → prompt de sistema especializado

La lógica común (llamada al LLM, parseo de JSON, validación de hipótesis)
está implementada aquí y es heredada por todos los agentes.
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod

from pydantic import ValidationError

from ..models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from ..models.report import AgentOutput, Critique

# Modelos disponibles
# Groq dio de baja los LLaMA 3.x (llama-3.3-70b-versatile / llama-3.1-8b-instant):
# la API devuelve 404 model_not_found. Reemplazados por los gpt-oss disponibles.
GROQ_MAIN = "openai/gpt-oss-120b"  # Agentes 01, 03, 06
GROQ_FAST = "openai/gpt-oss-20b"   # Agente rápido para tareas simples


class BaseAgent(ABC):
    """
    Interfaz común para todos los agentes de análisis clínico.

    Subclases deben definir los atributos de clase:
        AGENT_ID, AGENT_NAME, MODEL, SYSTEM_PROMPT
    """

    AGENT_ID: str = ""
    AGENT_NAME: str = ""
    MODEL: str = GROQ_MAIN
    SYSTEM_PROMPT: str = ""

    # ── Utilidades de parseo ──────────────────────────────────────

    @staticmethod
    def extract_json(raw: str) -> dict:
        """
        Extrae el primer bloque JSON válido de un string.
        Maneja respuestas con texto libre, markdown fences y JSON puro.
        """
        # 1. Parsear directamente
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Remover fences de markdown (```json ... ``` o ``` ... ```)
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
            stripped = re.sub(r'\s*```\s*$', '', stripped.strip())
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # 3. Buscar el bloque { ... } más grande
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"La respuesta del modelo no contiene JSON válido.\n"
            f"Primeros 500 chars: {raw[:500]}"
        )

    @staticmethod
    def _build_source(declared: dict) -> Source:
        """
        Construye una Source con los campos que al agente le corresponde declarar.

        El estado de verificación, el título real y los tipos de publicación son
        **salida** de la verificación bibliográfica contra PubMed
        (`pipeline/verification.py`), nunca entrada del modelo: un LLM que escribe
        `verified: true` en su JSON no verificó nada. Antes se hacía `Source(**s)`
        y esos campos autodeclarados viajaban en el Report interno hasta que
        `evidence.py` y `report_builder._annotate_source()` los ignoraban aguas
        abajo. Acá se descartan en el origen.

        No falla ante campos de más: emitirlos no invalida la hipótesis, y la regla
        del proyecto es no descartar hipótesis. Una fuente sin `title` sí sigue
        siendo un error de validación, como antes.
        """
        return Source(
            pmid=declared.get("pmid"),
            title=declared.get("title"),  # type: ignore[arg-type]
            journal=declared.get("journal"),
            year=declared.get("year"),
            url=declared.get("url"),
        )

    @staticmethod
    def parse_hypotheses(raw: str) -> list[Hypothesis]:
        """
        Parsea y valida la lista de hipótesis del JSON de respuesta.
        Espera un objeto con clave "hypotheses": [...].
        """
        data = BaseAgent.extract_json(raw)
        hypotheses = []

        for h in data.get("hypotheses", []):
            sources = [BaseAgent._build_source(s) for s in h.get("sources", [])]
            try:
                hypothesis = Hypothesis(
                    text=h["text"],
                    priority=Priority(h["priority"]),
                    evidence_level=EvidenceLevel(h["evidence_level"]),
                    rationale=h["rationale"],
                    sources=sources,
                )
                hypotheses.append(hypothesis)
            except (KeyError, ValidationError) as e:
                raise ValueError(f"Hipótesis malformada: {e}\nDatos: {h}")

        if not hypotheses:
            raise ValueError("El modelo no devolvió ninguna hipótesis.")

        return hypotheses

    # ── Llamada al LLM ────────────────────────────────────────────

    def _call_llm(self, user_message: str) -> str:
        """
        Llama al modelo configurado en self.MODEL vía Groq.
        Devuelve el texto crudo de la respuesta.
        Reintenta hasta 3 veces con backoff incremental ante errores 429
        (rate limit del tier gratuito de Groq: 12k TPM).
        """
        from groq import Groq, RateLimitError

        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        delays = [8, 20, 40]  # segundos de espera entre reintentos
        last_exc: Exception | None = None

        for attempt, delay in enumerate(delays + [None], start=1):
            try:
                response = client.chat.completions.create(
                    model=self.MODEL,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=4096,
                    temperature=0.3,
                )
                return response.choices[0].message.content
            except RateLimitError as exc:
                last_exc = exc
                if delay is None:
                    break
                print(
                    f"[NEXUS] Agente {self.AGENT_NAME}: rate limit (intento {attempt}/3). "
                    f"Reintentando en {delay}s…",
                    file=__import__("sys").stderr,
                )
                time.sleep(delay)

        raise last_exc  # type: ignore[misc]

    # ── Interfaz pública ──────────────────────────────────────────

    @abstractmethod
    def run(self, clinical_context: str) -> AgentOutput:
        """
        Ejecuta el agente sobre el contexto clínico dado.

        Args:
            clinical_context: texto clínico estructurado (salida de format_for_agents)

        Returns:
            AgentOutput con las hipótesis generadas por este agente
        """

    def _build_output(self, hypotheses: list[Hypothesis], raw: str) -> AgentOutput:
        """Construye el AgentOutput estándar."""
        return AgentOutput(
            agent_id=self.AGENT_ID,
            agent_name=self.AGENT_NAME,
            hypotheses=hypotheses,
            raw_response=raw,
        )

    # ── Debate adversarial ────────────────────────────────────────

    def critique(
        self,
        context: str,
        own_output: AgentOutput,
        other_outputs: list[AgentOutput],
    ) -> list[Critique]:
        """
        Ronda 2: genera críticas sobre las hipótesis de los otros agentes.
        Devuelve una lista de Critique con severidad y alternativa opcional.
        """
        own_text = _format_output(own_output, label="TUS HIPÓTESIS (Ronda 1)")
        others_text = _format_outputs(other_outputs, label="HIPÓTESIS DE OTROS AGENTES")

        prompt = (
            f"Sos {self.AGENT_NAME}. Participás en un debate adversarial de análisis clínico.\n\n"
            f"CONTEXTO CLÍNICO:\n{context}\n\n"
            f"{own_text}\n\n"
            f"{others_text}\n\n"
            "Analizá críticamente las hipótesis de los otros agentes desde tu perspectiva.\n"
            "Identificá inconsistencias, sobre-estimaciones o falta de evidencia.\n\n"
            "Respondé ÚNICAMENTE con JSON válido:\n"
            '{\n  "critiques": [\n    {\n'
            '      "target_agent_id": "ID del agente",\n'
            '      "target_hypothesis": "texto exacto de la hipótesis criticada",\n'
            '      "critique_text": "crítica específica y fundamentada",\n'
            '      "severity": "HIGH" | "MEDIUM" | "LOW",\n'
            '      "alternative": "alternativa sugerida o null"\n'
            "    }\n  ]\n}"
        )
        raw = self._call_llm(prompt)
        return self._parse_critiques(raw)

    def revise(
        self,
        context: str,
        own_output: AgentOutput,
        critiques_received: list[Critique],
    ) -> AgentOutput:
        """
        Rondas 3-4: revisa o defiende hipótesis propias en respuesta a críticas.
        Devuelve un AgentOutput con hipótesis ajustadas o defendidas.
        """
        own_text = _format_output(own_output, label="TUS HIPÓTESIS PREVIAS")
        critiques_text = _format_critiques(critiques_received)

        prompt = (
            f"Sos {self.AGENT_NAME}. Participás en un debate adversarial de análisis clínico.\n\n"
            f"CONTEXTO CLÍNICO:\n{context}\n\n"
            f"{own_text}\n\n"
            f"{critiques_text}\n\n"
            "Respondé a cada crítica recibida: ajustá tu hipótesis si la crítica es válida,\n"
            "o defendela con argumentación adicional. Podés agregar hipótesis nuevas si\n"
            "el debate reveló perspectivas no consideradas.\n\n"
            "Respondé ÚNICAMENTE con JSON en el formato estándar de hipótesis:\n"
            '{\n  "hypotheses": [...]\n}'
        )
        raw = self._call_llm(prompt)
        hypotheses = self.parse_hypotheses(raw)
        return self._build_output(hypotheses, raw)

    def _parse_critiques(self, raw: str) -> list[Critique]:
        """Parsea el JSON de críticas devuelto por el modelo."""
        data = self.extract_json(raw)
        critiques = []
        for c in data.get("critiques", []):
            severity = c.get("severity", "MEDIUM").upper()
            if severity not in ("HIGH", "MEDIUM", "LOW"):
                severity = "MEDIUM"
            critiques.append(Critique(
                from_agent_id=self.AGENT_ID,
                from_agent_name=self.AGENT_NAME,
                target_agent_id=str(c.get("target_agent_id", "")),
                target_hypothesis=c.get("target_hypothesis", ""),
                critique_text=c.get("critique_text", ""),
                severity=severity,
                alternative=c.get("alternative") or None,
            ))
        return critiques


# ── Helpers de formateo para el debate ────────────────────────────────────────

def _format_output(output: AgentOutput, label: str) -> str:
    lines = [f"=== {label} ({output.agent_name}) ==="]
    for i, h in enumerate(output.hypotheses, 1):
        lines.append(f"#{i} [{h.priority.value}] Evidencia {h.evidence_level.value}: {h.text}")
        lines.append(f"   Fundamento: {h.rationale[:300]}")
    return "\n".join(lines)


def _format_outputs(outputs: list[AgentOutput], label: str) -> str:
    lines = [f"=== {label} ==="]
    for output in outputs:
        lines.append(f"\n--- {output.agent_name} (Agente {output.agent_id}) ---")
        for i, h in enumerate(output.hypotheses, 1):
            lines.append(f"#{i} [{h.priority.value}] Evidencia {h.evidence_level.value}: {h.text}")
            lines.append(f"   Fundamento: {h.rationale[:300]}")
    return "\n".join(lines)


def _format_critiques(critiques: list[Critique]) -> str:
    if not critiques:
        return "=== CRÍTICAS RECIBIDAS ===\nNinguna crítica recibida."
    lines = ["=== CRÍTICAS RECIBIDAS ==="]
    for c in critiques:
        lines.append(f"\n- De: {c.from_agent_name} [{c.severity}]")
        lines.append(f"  Hipótesis criticada: {c.target_hypothesis[:150]}")
        lines.append(f"  Crítica: {c.critique_text}")
        if c.alternative:
            lines.append(f"  Alternativa sugerida: {c.alternative}")
    return "\n".join(lines)
