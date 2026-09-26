"""
Respuestas grabadas del modo mock, por tarea (control de costos, Sprint 4 — D7).

Cada respuesta atraviesa el mismo parseo y las mismas validaciones que una
respuesta real (D7: "el modo mock ejercita el flujo real"): son JSON válido
en el formato exacto que espera cada sitio de llamada, con contenido de
ejemplo sobre el caso de prueba del proyecto (neuropatía axonal
sensitivomotora, paciente masculino de 42 años).

**Estado de estas respuestas (tasks.md, tarea 6.2 — decisión de diseño).**
Deberían salir de una corrida real contra Groq, pero esta sesión de
implementación tiene prohibido gastar cuota (restricción explícita del
control de costos que este mismo cambio instala). Son entonces fixtures
razonadas a mano que pasan el parseo vigente (ver
`tests/test_mock_pipeline.py`), no una grabación real. Quedan **parciales**:
regenerarlas desde una corrida real es trabajo pendiente para cuando haya
cuota disponible, y es la forma de que el modo mock no se desactualice
respecto de lo que el modelo devuelve de verdad (riesgo señalado en
design.md).
"""

from __future__ import annotations

import json

_PMID_B12 = "22439958"
_TITULO_B12 = "Metformin-associated vitamin B12 deficiency and hyperhomocysteinemia"

_HIPOTESIS_B12 = {
    "text": (
        "Neuropatía axonal sensitivomotora secundaria a déficit de vitamina B12 "
        "inducido por metformina."
    ),
    "priority": "HIGH",
    "evidence_level": "II",
    "rationale": (
        "La metformina interfiere con la absorción ileal de vitamina B12 "
        "dependiente de calcio; el patrón axonal difuso y el compromiso "
        "autonómico son compatibles con una neuropatía carencial de curso "
        "prolongado. [Respuesta grabada del modo mock.]"
    ),
    "sources": [{"pmid": _PMID_B12, "title": _TITULO_B12, "journal": "Diabetes Care", "year": 2012}],
}

_HIPOTESIS_ATTR = {
    "text": (
        "Amiloidosis hereditaria por transtiretina (ATTR) como causa de la "
        "neuropatía axonal sensitivomotora con compromiso autonómico."
    ),
    "priority": "MEDIUM",
    "evidence_level": "III",
    "rationale": (
        "El compromiso autonómico marcado junto con la neuropatía axonal "
        "progresiva de origen no aclarado, y el antecedente familiar de "
        "trastornos del equilibrio, son compatibles con una neuropatía "
        "amiloidótica hereditaria; el panel genético reducido no incluyó TTR. "
        "[Respuesta grabada del modo mock.]"
    ),
    "sources": [],
}


def _hypotheses_response() -> str:
    """Formato común de `run()`/`revise()`: `{"hypotheses": [...]}`."""
    return json.dumps({"hypotheses": [_HIPOTESIS_B12, _HIPOTESIS_ATTR]}, ensure_ascii=False)


def _critique_response() -> str:
    return json.dumps({
        "critiques": [{
            "target_agent_id": "01",
            "target_hypothesis": _HIPOTESIS_B12["text"],
            "critique_text": (
                "Respuesta grabada del modo mock: no evalúa evidencia real, solo "
                "ejercita el parseo de críticas."
            ),
            "severity": "LOW",
            "alternative": None,
        }],
    }, ensure_ascii=False)


def _recitation_response() -> str:
    return json.dumps({
        "recitations": [{
            "hypothesis": 1,
            "sources": [{"pmid": _PMID_B12, "title": _TITULO_B12}],
        }],
    }, ensure_ascii=False)


def _grouping_response() -> str:
    """
    Partición vacía: `consensus.normalize_partition()` la trata como que
    ninguna hipótesis fue agrupada por el modelo y le da a cada una su propio
    grupo (el mismo comportamiento que una agrupación degradada, pero con
    estado `OK`). Es la respuesta más segura independientemente de cuántas
    hipótesis haya en la corrida.
    """
    return json.dumps({"groups": []})


def _verdicts_response() -> str:
    """Lista vacía: ninguna hipótesis recibe veredicto, pero el parseo corre."""
    return json.dumps({"verdicts": []})


def _term_planning_response() -> str:
    return json.dumps({
        "terms": [{
            "candidate": 1,
            "condition_en": "axonal neuropathy",
            "synonyms_en": ["hereditary sensorimotor neuropathy"],
        }],
    })


def _compatibility_response() -> str:
    return json.dumps({
        "evaluations": [{
            "nct_id": "NCT00000000",
            "compatibility": "media",
            "rationale": "Respuesta grabada del modo mock.",
            "criteria_to_verify": ["Verificar criterios de inclusión reales del ensayo"],
        }],
    })


def _pico_response() -> str:
    return json.dumps({
        "patient_profile": "Masculino de 42 años",
        "chief_complaint": "Neuropatía axonal sensitivomotora progresiva",
        "condition_en": "axonal neuropathy",
        "relevant_history": ["Diabetes tipo 2 en tratamiento con metformina"],
        "negative_findings": [
            "Panel genético CMT de 40 genes negativo",
            "Anticuerpos paraneoplásicos (anti-Hu, anti-Yo, anti-Ri) negativos",
        ],
        "disease_duration": "18 meses",
        "current_treatments": ["Metformina", "Pregabalina"],
        "procedures_done": ["Electromiograma", "Punción lumbar"],
        "comparison": "No aplica",
        "primary_outcome": "Identificar la etiología tratable de la neuropatía",
        "secondary_outcomes": [],
        "biomarkers": ["Vitamina B12 baja"],
        "genetic_findings": [],
        "clinical_narrative": (
            "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
            "progresiva de 18 meses de evolución, con compromiso autonómico "
            "asociado. Respuesta grabada del modo mock: no proviene de un "
            "análisis real."
        ),
    }, ensure_ascii=False)


def _biomarkers_response() -> str:
    return json.dumps({
        "genes": [],
        "antibodies": [],
        "lab_biomarkers": ["vitamina B12 baja"],
        "genetic_variants": [],
        "pathways": ["neuropatía axonal sensitivomotora"],
        "therapeutic_history": {
            "drugs": ["metformina", "pregabalina"],
            "procedures": ["electromiograma", "punción lumbar"],
            "surgeries": [],
        },
    }, ensure_ascii=False)


# Una entrada por cada tarea de `agents.model_tasks.TASK_BUDGETS`: es lo que
# hace que ninguna llamada del pipeline se quede sin respuesta grabada.
MOCK_RESPONSES: dict[str, str] = {
    "agente01_hipotesis": _hypotheses_response(),
    "agente02_hipotesis": _hypotheses_response(),
    "agente03_hipotesis": _hypotheses_response(),
    "debate_critica": _critique_response(),
    "debate_revision": _hypotheses_response(),
    "debate_recitacion": _recitation_response(),
    "arbitro_agrupacion": _grouping_response(),
    "arbitro_veredictos": _verdicts_response(),
    "agente05_planificacion_terminos": _term_planning_response(),
    "agente05_evaluacion_compatibilidad": _compatibility_response(),
    "pico_sintesis": _pico_response(),
    "biomarcadores_extraccion": _biomarkers_response(),
}

# JSON válido y vacío: una tarea sin fixture falla en el parseo de quien
# llama (p. ej. "no devolvió ninguna hipótesis"), de forma controlada, en vez
# de que `call_provider()` reviente por una tarea nueva sin registrar acá.
_SIN_FIXTURE = "{}"


def get_mock_response(task: str) -> str:
    """Respuesta grabada para `task`, o un JSON vacío si no hay fixture."""
    return MOCK_RESPONSES.get(task, _SIN_FIXTURE)
