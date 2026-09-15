## Why

Hoy la búsqueda de ensayos es un paso suelto del router (`api/router.py`, paso 6):
consulta ClinicalTrials.gov solo con `condition_en` y biomarcadores, ignora las
hipótesis que produjo el debate, no mira si el ensayo admite la edad o el sexo del
paciente y, si la API falla, devuelve `[]` sin que el reporte lo diga. El médico
recibe una lista de ensayos "relacionados con la condición", no ensayos
**compatibles con el perfil del paciente**, que es lo que pide la tarjeta #53.
Orphanet tiene cliente (`external/orphanet.py`) pero **no está conectado al pipeline**.
Su búsqueda nunca devolvía resultados —usaba el endpoint inexistente
`/approximatelymatching`— pero eso ya quedó arreglado en F1 (PR #11), que es
prerrequisito de este cambio: acá solo hay que conectarlo. Es el momento de cerrar las
dos cosas con un agente dedicado, antes de que el Árbitro (04) y el Sintetizador (06) se
apoyen sobre este paso.

## What Changes

- Nuevo **Agente 05 — Navegador de Ensayos** (`backend/agents/agent_05_trials.py`),
  hereda de `BaseAgent` y usa el LLM **solo** vía `BaseAgent._call_llm()`. No
  participa del debate: expone `navigate(TrialNavigationInput) -> TrialNavigationResult`.
- Contrato de entrada neutral (`TrialNavigationInput`) armado por un adaptador desde
  `ClinicalCase` + `list[Hypothesis]`: hoy recibe las hipótesis del reporte final del
  debate; cuando exista el Árbitro recibe su consenso (con estado por hipótesis) sin
  cambiar el agente.
- Flujo híbrido del agente, cada paso con fallback explícito:
  1. **Planificación (LLM)**: traduce las hipótesis principales (en español) a
     términos de condición en inglés médico, con sinónimos.
  2. **Búsqueda determinista**: consulta base igual a la de hoy (no hay regresión) más
     una consulta por hipótesis; deduplica por NCT ID.
  3. **Orphanet determinista**: busca cada término y marca la hipótesis como enfermedad
     rara solo ante coincidencia **exacta** normalizada con el nombre preferido.
  4. **Filtros duros deterministas**: excluye ensayos cuyo rango de edad o sexo no
     admite al paciente, solo cuando ambos datos se conocen.
  5. **Evaluación de compatibilidad (LLM)**: etiqueta cada ensayo como `alta`,
     `media` o `baja` con fundamento y "criterios a verificar"; nunca descarta
     ensayos y solo acepta NCT IDs que se le enviaron.
- Privacidad: a ClinicalTrials.gov y Orphanet solo viajan términos saneados en inglés
  (condición, sinónimos, genes, fármacos INN); edad y sexo se filtran localmente; los
  logs registran tipo de excepción y conteos, nunca texto clínico ni respuestas del LLM.
- `external/orphanet.py`: **sin cambios en este PR**. F1 ya lo dejó funcionando contra el
  endpoint real, parseando `ORPHAcode` y levantando `ExternalApiError` ante un fallo real
  en lugar de devolver `[]`. Este cambio consume ese contrato y decide el fallback en el
  agente. `ORPHANET_API_KEY` es opcional: medido, la API responde sin clave.
- `api/router.py`: el paso 6 deja de llamar a `search_by_biomarkers` y ejecuta el
  Agente 05 en paralelo con la verificación bibliográfica (paso 7).
- Contrato de exportación **aditivo** (mismo precedente que `Source.verified`):
  - `ClinicalTrial` suma campos opcionales con default: `compatibility`,
    `compatibility_rationale`, `criteria_to_verify`, `related_hypotheses`, `matched_terms`.
  - `StructuredReport` suma `rare_diseases: list[RareDiseaseMatch] = []` y
    `trial_search: TrialSearchSummary` (qué se consultó, qué falló, cuántos se excluyeron).
- **Ensayos `NOT_YET_RECRUITING` incluidos y etiquetados**: la búsqueda deja de limitarse a
  `RECRUITING`. Para un paciente con enfermedad rara sin tratamiento aprobado, un ensayo que
  abre en meses es accionable; el reporte lo distingue de los que reclutan hoy y nunca
  afirma disponibilidad inmediata.
- **Ensayos con sede en Argentina primero**: el reporte los ordena hacia arriba dentro de
  cada nivel de compatibilidad, **sin filtrar** por ubicación. Se resuelve sobre las sedes
  que el cliente ya devuelve; no viaja nada a la API ni deriva de un dato del paciente.
  `ClinicalTrial` suma `has_local_site`.
- Frontend (tab "Ensayos clínicos") y PDF muestran compatibilidad, criterios a
  verificar, enfermedades raras de Orphanet, estado de reclutamiento, sede local y el
  estado de la búsqueda, con la aclaración de que la compatibilidad es orientativa.

## Capabilities

### New Capabilities
- `navegador-ensayos`: Agente 05 — contrato de entrada, planificación de términos,
  búsqueda en ClinicalTrials.gov, filtros duros por edad/sexo, evaluación orientativa
  de compatibilidad, fallbacks y reglas de privacidad.
- `enfermedades-raras-orphanet`: consulta a Orphanet desde el pipeline — endpoint real,
  manejo de "sin coincidencias" vs. errores, y criterio de coincidencia exacta para
  marcar una hipótesis como enfermedad rara.
- `reporte-ensayos`: cómo llegan los ensayos, su compatibilidad, las enfermedades raras
  y el estado de la búsqueda al `StructuredReport`, al frontend y al PDF, sin romper
  el contrato vigente.

### Modified Capabilities
<!-- openspec/specs/ está vacío: no hay capacidades vigentes que modificar. -->

## Impact

- **Código nuevo**: `backend/agents/agent_05_trials.py`, `backend/pipeline/trial_matching.py`
  (adaptador de entrada y helpers deterministas), `tests/test_agent_05_trials.py`,
  `tests/test_trial_matching.py`, `scripts/demo_agente05.py`.
- **Código modificado**: `backend/models/trial.py`, `backend/external/clinical_trials.py`
  (estados de reclutamiento), `backend/api/router.py`, `backend/api/schemas.py`,
  `backend/pipeline/report_builder.py`, `backend/pipeline/pdf_exporter.py`,
  `frontend/src/lib/types.ts`, `frontend/src/app/report/page.tsx`,
  `frontend/src/app/analyzing/page.tsx`, `tests/test_api.py`,
  `tests/test_clinical_trials.py`, `tests/test_report_builder.py`,
  `tests/test_pdf_exporter.py`.
  **Ya no se toca** `backend/external/orphanet.py`, `tests/test_orphanet.py` ni
  `scripts/demo_orphanet.py`: los cerró F1.
- **APIs externas**: ClinicalTrials.gov (hasta 10 consultas por análisis en vez de 1–2, y
  ahora también estados `NOT_YET_RECRUITING`), Orphanet (nueva en el pipeline, sin
  credencial obligatoria), Groq (+2 llamadas por análisis, sujetas al límite de 12k TPM).
- **Contrato JSON**: solo aditivo; clientes que ignoren los campos nuevos siguen andando.
- **Cambios ya mergeados que este toma como base**: #54 (EBM) dejó
  `backend/pipeline/evidence.py`, el parámetro `verifications` en `build_export()` y los
  estados `respaldada` / `pendiente` / `especulativa` — **no existe `descartada`**, así que
  el agente no descarta candidatas por estado. F1 dejó el cliente Orphanet funcionando.
  Este cambio agrega campos y un parámetro al final, sin tocar `_rank_hypotheses` ni
  `RankedHypothesis`. #51 (Agente 02) toca `orchestrator.py`/`debate.py`, que no se modifican.
- **Documentación**: `.claude/CLAUDE.md`, `.claude/backlog.md` (tarea 10),
  `.claude/architecture.md` (flujo, APIs y estados de reclutamiento).
