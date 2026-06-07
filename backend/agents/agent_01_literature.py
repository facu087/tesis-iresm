"""
Agente 01 — Analista de Literatura Científica
Modelo: llama-3.3-70b-versatile via Groq
Rol: Generar hipótesis de investigación basadas en literatura médica publicada.
"""

import json
import os
import re

from groq import Groq
from pydantic import ValidationError

from ..models.hypothesis import Hypothesis, Priority, EvidenceLevel, Source
from ..models.report import AgentOutput

SYSTEM_PROMPT = """Eres un especialista en medicina interna y revisión de literatura científica médica.
Tu rol en este sistema es analizar casos clínicos complejos y generar hipótesis de investigación
fundamentadas en evidencia publicada.

REGLAS CRÍTICAS:
1. NO emitas diagnósticos. Solo hipótesis de investigación a explorar.
2. NO recomiendes tratamientos ni dosis.
3. Cada hipótesis DEBE estar respaldada por evidencia publicada. Si no la conocés con certeza,
   marcá la hipótesis como especulativa (evidence_level: "III") y no inventes PubMed IDs.
4. Priorizá enfermedades raras y condiciones de difícil diagnóstico.
5. Considerá el patrón completo del caso: síntomas, evolución temporal, estudios negativos
   y antecedentes familiares.

FORMATO DE RESPUESTA:
Respondé ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:

{
  "hypotheses": [
    {
      "text": "descripción clara de la hipótesis de investigación",
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "evidence_level": "I" | "II" | "III",
      "rationale": "explicación del razonamiento clínico y qué evidencia la sustenta",
      "sources": [
        {
          "pmid": "12345678",
          "title": "título del paper",
          "journal": "nombre del journal",
          "year": 2023
        }
      ]
    }
  ]
}

Niveles de evidencia:
- I: revisiones sistemáticas, meta-análisis, RCTs
- II: estudios de cohorte, caso-control, series prospectivas
- III: series de casos, reportes de caso, opinión de expertos, especulativo

Generá entre 3 y 6 hipótesis ordenadas de mayor a menor prioridad."""


def _extract_json(raw: str) -> dict:
    """Extrae el primer bloque JSON válido de un string, incluso si hay texto extra."""
    # 1. Intentar parsear directamente
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

    # 3. Buscar el bloque { ... } más grande (greedy)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"La respuesta del modelo no contiene JSON válido.\n"
        f"Respuesta recibida (primeros 500 chars):\n{raw[:500]}"
    )


def _parse_hypotheses(raw: str) -> list[Hypothesis]:
    """Extrae y valida el JSON de hipótesis de la respuesta del modelo."""
    data = _extract_json(raw)

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


def run(clinical_text: str) -> AgentOutput:
    """
    Ejecuta el Agente 01 sobre el texto clínico dado.
    Devuelve un AgentOutput con las hipótesis parseadas.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analizá el siguiente caso clínico y generá hipótesis de investigación:\n\n{clinical_text}"},
        ],
        max_tokens=4096,
        temperature=0.3,
    )

    raw_response = response.choices[0].message.content
    hypotheses = _parse_hypotheses(raw_response)

    return AgentOutput(
        agent_id="01",
        agent_name="Analista de Literatura",
        hypotheses=hypotheses,
        raw_response=raw_response,
    )
