"""
Módulo de síntesis PICO.

Toma el texto clínico normalizado y genera una estructura PICO completa
usando el modelo de lenguaje. Esta síntesis es el contexto estructurado
que reciben todos los agentes de análisis.
"""

import json
import os
import re
import time

from groq import Groq, RateLimitError
from pydantic import ValidationError

from ..agents.base_agent import GROQ_MAIN
from ..models.case import ClinicalCase, PICOSynthesis

SYSTEM_PROMPT = """Eres un médico especialista en metodología de investigación clínica.
Tu tarea es analizar un caso clínico y construir una síntesis estructurada en formato PICO.

PICO es una metodología estándar de medicina basada en evidencia:
- P (Población): características del paciente, perfil clínico y demográfico
- I (Intervención): tratamientos realizados, procedimientos, exposiciones
- C (Comparación): contexto comparativo relevante (o "No aplica" si no hay)
- O (Outcome): qué se quiere lograr o investigar en este caso

REGLAS:
1. Extraé SOLO la información que está explícitamente en el texto. No inferís ni inventás datos.
2. Los "negative_findings" son críticos: estudios negativos acotan el diagnóstico diferencial.
3. El "clinical_narrative" debe ser un párrafo cohesivo en tercera persona que integre
   toda la información del caso de forma estructurada. Es lo que leerán los agentes de análisis.
4. Respondé ÚNICAMENTE con JSON válido, sin texto adicional.

FORMATO DE RESPUESTA (JSON exacto):
{
  "patient_profile": "descripción demográfica y clínica principal",
  "chief_complaint": "motivo de consulta o síntoma principal",
  "relevant_history": ["antecedente 1", "antecedente 2"],
  "negative_findings": ["estudio negativo 1", "estudio negativo 2"],
  "disease_duration": "tiempo de evolución",
  "current_treatments": ["tratamiento 1", "tratamiento 2"],
  "procedures_done": ["procedimiento 1", "procedimiento 2"],
  "comparison": "contexto comparativo o No aplica",
  "primary_outcome": "objetivo principal de investigación",
  "secondary_outcomes": ["objetivo secundario 1", "objetivo secundario 2"],
  "biomarkers": ["biomarcador 1"],
  "genetic_findings": ["hallazgo genético 1"],
  "clinical_narrative": "Párrafo narrativo completo e integrado del caso clínico..."
}"""


def _parse_pico(raw: str) -> PICOSynthesis:
    """Extrae y valida la síntesis PICO del JSON devuelto por el modelo."""
    # Limpiar posibles fences de markdown
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Buscar el bloque JSON dentro del texto
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise ValueError(
                f"El modelo no devolvió JSON válido.\n"
                f"Respuesta (primeros 500 chars): {raw[:500]}"
            )
        data = json.loads(match.group())

    try:
        return PICOSynthesis(**data)
    except (ValidationError, TypeError) as e:
        raise ValueError(f"La síntesis PICO tiene campos inválidos: {e}")


def build(case: ClinicalCase) -> ClinicalCase:
    """
    Construye la síntesis PICO para un caso clínico.
    Recibe un ClinicalCase con raw_text, devuelve el mismo objeto
    con el campo pico completado.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    delays = [8, 20, 40]
    last_exc: Exception | None = None

    for attempt, delay in enumerate(delays + [None], start=1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MAIN,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Construí la síntesis PICO para el siguiente caso clínico:\n\n"
                            f"{case.raw_text}"
                        ),
                    },
                ],
                max_tokens=2048,
                temperature=0.1,
            )
            raw = response.choices[0].message.content
            case.pico = _parse_pico(raw)
            return case
        except RateLimitError as exc:
            last_exc = exc
            if delay is None:
                break
            import sys
            print(f"[NEXUS] PICO: rate limit (intento {attempt}/3). Reintentando en {delay}s…", file=sys.stderr)
            time.sleep(delay)

    raise last_exc  # type: ignore[misc]


def format_for_agents(pico: PICOSynthesis) -> str:
    """
    Formatea la síntesis PICO como contexto estructurado para pasar a los agentes.
    Este es el texto que recibe cada agente en Ronda 1.
    """
    lines = [
        "=== SÍNTESIS CLÍNICA ESTRUCTURADA (PICO) ===\n",
        f"NARRATIVA CLÍNICA:\n{pico.clinical_narrative}\n",
        f"PERFIL DEL PACIENTE: {pico.patient_profile}",
        f"MOTIVO DE CONSULTA: {pico.chief_complaint}",
        f"DURACIÓN: {pico.disease_duration}",
    ]

    if pico.relevant_history:
        lines.append("ANTECEDENTES RELEVANTES:")
        lines.extend(f"  - {h}" for h in pico.relevant_history)

    if pico.negative_findings:
        lines.append("ESTUDIOS NEGATIVOS (crítico para diagnóstico diferencial):")
        lines.extend(f"  - {f}" for f in pico.negative_findings)

    if pico.procedures_done:
        lines.append("PROCEDIMIENTOS REALIZADOS:")
        lines.extend(f"  - {p}" for p in pico.procedures_done)

    if pico.current_treatments:
        lines.append("TRATAMIENTOS:")
        lines.extend(f"  - {t}" for t in pico.current_treatments)

    if pico.biomarkers:
        lines.append("BIOMARCADORES IDENTIFICADOS:")
        lines.extend(f"  - {b}" for b in pico.biomarkers)

    if pico.genetic_findings:
        lines.append("HALLAZGOS GENÉTICOS:")
        lines.extend(f"  - {g}" for g in pico.genetic_findings)

    lines.append(f"\nOBJETIVO PRINCIPAL: {pico.primary_outcome}")

    if pico.secondary_outcomes:
        lines.append("OBJETIVOS SECUNDARIOS:")
        lines.extend(f"  - {o}" for o in pico.secondary_outcomes)

    return "\n".join(lines)
