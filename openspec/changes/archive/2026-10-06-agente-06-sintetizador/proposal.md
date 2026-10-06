## Why

El pipeline ya produce un `StructuredReport` completo con hipótesis priorizadas,
veredictos del Árbitro, ensayos clínicos y bibliografía verificada, pero no existe una
síntesis en prosa legible para el médico. El Agente 06 agrega ese párrafo final sin
modificar ningún dato del reporte determinístico ya construido.

## What Changes

- Se crea `backend/agents/agent_06_synthesizer.py` con `SynthesizerAgent`, que expone
  `synthesize(structured_report: StructuredReport) -> str | None`.
- `StructuredReport` (`backend/api/schemas.py`) recibe el campo
  `executive_summary: str | None = None` con patrón nullable idéntico al de `arbitration`
  y `trial_search` (retrocompatibilidad: `None` = reporte anterior al Agente 06).
- `backend/agents/model_tasks.py` agrega la tarea
  `"agente06_sintesis": TaskBudget(GROQ_MAIN, 4096)`.
- `backend/api/router.py` llama a `synthesize()` después del Agente 05 y asigna el
  resultado a `structured_report.executive_summary`.
- `backend/mock/grabadas.json` recibe la clave `agente06_sintesis` con una respuesta
  grabada de una corrida real (producida con `scripts/medir_costos.py --grabar`).
- El PDF (`backend/pipeline/pdf_exporter.py`) y el frontend (`frontend/src/app/report/`)
  muestran el `executive_summary` cuando no es `None`.

## Capabilities

### New Capabilities

- `sintetizador`: Generación de un resumen ejecutivo en prosa por LLM al final del
  pipeline. El LLM nunca decide datos; solo narrativiza el `StructuredReport` ya
  construido por `report_builder.py`. Si el resumen cita un PMID, NCT o símbolo génico
  ausente del reporte, se descarta completo.

### Modified Capabilities

- `reporte-consenso`: `StructuredReport` suma el campo `executive_summary` opcional.
  El contrato del JSON cambia de forma aditiva (campo nullable, no breaking).

## Impact

- **Nuevo archivo**: `backend/agents/agent_06_synthesizer.py`
- **Modificados**: `backend/api/schemas.py`, `backend/agents/model_tasks.py`,
  `backend/api/router.py`, `backend/mock/grabadas.json`,
  `backend/pipeline/pdf_exporter.py`, `frontend/src/app/report/page.tsx`
- **Tests nuevos**: `tests/test_agent_06_synthesizer.py` (unitarios, sin Groq,
  fixture `client_medico_verificado`)
- **Sin breaking changes**: el campo es nullable; los reportes anteriores al Ag06
  tienen `executive_summary: null` y los renderers lo omiten
- **Cuota Groq**: +1 llamada por análisis (~4 k tokens de entrada); dentro del
  límite de 2 casos/día
