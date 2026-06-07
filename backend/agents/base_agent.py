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
from abc import ABC, abstractmethod

from pydantic import ValidationError

from ..models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from ..models.report import AgentOutput

# Modelos disponibles
GROQ_LLAMA = "llama-3.3-70b-versatile"   # Agentes 01, 03, 06
GROQ_LLAMA_FAST = "llama-3.1-8b-instant" # Agente rápido para tareas simples


class BaseAgent(ABC):
    """
    Interfaz común para todos los agentes de análisis clínico.

    Subclases deben definir los atributos de clase:
        AGENT_ID, AGENT_NAME, MODEL, SYSTEM_PROMPT
    """

    AGENT_ID: str = ""
    AGENT_NAME: str = ""
    MODEL: str = GROQ_LLAMA
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
    def parse_hypotheses(raw: str) -> list[Hypothesis]:
        """
        Parsea y valida la lista de hipótesis del JSON de respuesta.
        Espera un objeto con clave "hypotheses": [...].
        """
        data = BaseAgent.extract_json(raw)
        hypotheses = []

        for h in data.get("hypotheses", []):
            sources = [Source(**s) for s in h.get("sources", [])]
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
        Subclases pueden sobreescribir este método para usar otro proveedor
        (OpenAI, Gemini, etc.) sin cambiar la lógica de parseo.
        """
        from groq import Groq

        client = Groq(api_key=os.environ["GROQ_API_KEY"])
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
