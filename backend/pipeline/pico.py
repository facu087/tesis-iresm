"""
Módulo de síntesis PICO.

Toma el texto clínico normalizado y genera una estructura PICO completa
usando el modelo de lenguaje. Esta síntesis es el contexto estructurado
que reciben todos los agentes de análisis.
"""

import json
import re

from pydantic import ValidationError

from ..agents import model_tasks
from ..agents.base_agent import call_provider
from ..models.case import ClinicalCase, PICOSynthesis

_TASK = "pico_sintesis"

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
4. El "condition_en" es la condición principal en inglés médico estándar, con la terminología
   que usan los registros internacionales (ClinicalTrials.gov, PubMed). Es el único campo en inglés.
   Usá el término GENERAL de 2-3 palabras (el paraguas de la patología), no el diagnóstico
   detallado: los registros indexan por condición amplia y un término muy específico no matchea.
   Omití calificadores como "idiopathic", "progressive", "severe", "chronic".
   Ej: "neuropatía axonal sensitivomotora progresiva idiopática" → "axonal neuropathy".
5. Respondé ÚNICAMENTE con JSON válido, sin texto adicional.

FORMATO DE RESPUESTA (JSON exacto):
{
  "patient_profile": "descripción demográfica y clínica principal",
  "chief_complaint": "motivo de consulta o síntoma principal",
  "condition_en": "condición principal en inglés médico estándar",
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

    La llamada al proveedor pasa por `call_provider()` (control de costos,
    S4 — D1): antes este módulo instanciaba el cliente de Groq por su cuenta,
    lo que dejaba su consumo fuera de cualquier contabilidad futura y
    triplicaba el punto de swap de proveedor. El modelo y el techo de tokens
    salen de `model_tasks.TASK_BUDGETS` (D6), no de una constante local: es
    el mismo mapa que consultan los agentes.
    """
    budget = model_tasks.get_budget(_TASK)
    raw = call_provider(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            "Construí la síntesis PICO para el siguiente caso clínico:\n\n"
            f"{case.raw_text}"
        ),
        model=budget.model,
        max_tokens=budget.max_tokens,
        task=_TASK,
        temperature=0.1,
    )
    case.pico = _parse_pico(raw)
    return case


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
