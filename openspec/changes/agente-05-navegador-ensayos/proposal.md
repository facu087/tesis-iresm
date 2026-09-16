## Why

Hoy la búsqueda de ensayos es un paso suelto del router (`api/router.py`, paso 6):
consulta ClinicalTrials.gov solo con `condition_en` y biomarcadores, ignora las
hipótesis que produjo el debate, no mira si el ensayo admite la edad o el sexo del
paciente y, si la API falla, devuelve `[]` sin que el reporte lo diga. El médico
recibe una lista de ensayos "relacionados con la condición", no ensayos
**compatibles con el perfil del paciente**, que es lo que pide la tarjeta #53.
Orphanet ya tiene un cliente que funciona contra la API real (`external/orphanet.py`,
arreglado en la rama `fix/s4-cliente-orphanet`, commit `41828a8`), pero **nadie lo
llama**: ninguna hipótesis se contrasta contra el catálogo de enfermedades raras. Es
el momento de cerrar las dos cosas con un agente dedicado, antes de que el Árbitro (04)
y el Sintetizador (06) se apoyen sobre este paso.

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
     una consulta por hipótesis; deduplica por NCT ID. Incluye los ensayos que todavía
     no reclutan (`NOT_YET_RECRUITING`), etiquetados como tales.
  3. **Orphanet determinista**: busca cada término y marca la hipótesis como enfermedad
     rara solo ante coincidencia **exacta** normalizada con el nombre preferido.
  4. **Filtros duros deterministas**: excluye ensayos cuyo rango de edad o sexo no
     admite al paciente, solo cuando ambos datos se conocen.
  5. **Evaluación de compatibilidad (LLM)**: etiqueta cada ensayo como `alta`,
     `media` o `baja` con fundamento y "criterios a verificar"; nunca descarta
     ensayos y solo acepta NCT IDs que se le enviaron.
  6. **Orden determinista**: compatibilidad → sede en Argentina → ya reclutando →
     orden de descubrimiento. La sede ordena, nunca filtra.
- Privacidad: a ClinicalTrials.gov y Orphanet solo viajan términos saneados en inglés
  (condición, sinónimos, genes, fármacos INN); edad y sexo se filtran localmente; los
  logs registran tipo de excepción y conteos, nunca texto clínico ni respuestas del LLM.
- `external/clinical_trials.py`: `search()` reemplaza `recruiting_only: bool` por los
  estados a consultar, para poder pedir `RECRUITING` y `NOT_YET_RECRUITING` en la misma
  llamada. El default sigue siendo solo `RECRUITING`, así que las llamadas actuales no cambian.
- `external/orphanet.py`: **sin cambios**. El cliente ya consulta el endpoint real
  `ApproximateName/{name}`, parsea `ORPHAcode` y lanza `ExternalApiError` en vez de
  devolver `[]` (commit `41828a8`, ya en `develop`). Este cambio solo lo consume y
  decide el fallback en el agente.
- `api/router.py`: el paso 6 deja de llamar a `search_by_biomarkers` y ejecuta el
  Agente 05 en paralelo con la verificación bibliográfica (paso 7).
- Contrato de exportación **aditivo** (mismo precedente que `Source.verified`):
  - `ClinicalTrial` suma campos opcionales con default: `compatibility`,
    `compatibility_rationale`, `criteria_to_verify`, `related_hypotheses`, `matched_terms`.
  - `StructuredReport` suma `rare_diseases: list[RareDiseaseMatch] = []` y
    `trial_search: TrialSearchSummary` (qué se consultó, qué falló, cuántos se excluyeron).
- Frontend (tab "Ensayos clínicos") y PDF muestran compatibilidad, criterios a
  verificar, enfermedades raras de Orphanet, el estado de reclutamiento ("aún no
  recluta"), la sede en Argentina cuando corresponde y el estado de la búsqueda, con la
  aclaración de que la compatibilidad es orientativa.

## Capabilities

### New Capabilities
- `navegador-ensayos`: Agente 05 — contrato de entrada, planificación de términos,
  búsqueda en ClinicalTrials.gov (incluidos los ensayos que aún no reclutan), filtros
  duros por edad/sexo, evaluación orientativa de compatibilidad, orden del resultado,
  fallbacks y reglas de privacidad.
- `enfermedades-raras-orphanet`: consulta a Orphanet desde el pipeline — contrato del
  cliente (endpoint real y manejo de "sin coincidencias" vs. errores, ya implementado en
  `fix/s4-cliente-orphanet`) y criterio de coincidencia exacta para marcar una hipótesis
  como enfermedad rara.
- `reporte-ensayos`: cómo llegan los ensayos, su compatibilidad, las enfermedades raras
  y el estado de la búsqueda al `StructuredReport`, al frontend y al PDF, sin romper
  el contrato vigente.

### Modified Capabilities
<!-- openspec/specs/ está vacío: no hay capacidades vigentes que modificar. -->

## Impact

- **Código nuevo**: `backend/agents/agent_05_trials.py`, `backend/pipeline/trial_matching.py`
  (adaptador de entrada y helpers deterministas), `tests/test_agent_05_trials.py`,
  `tests/test_trial_matching.py`, `scripts/demo_agente05.py`.
- **Código modificado**: `backend/models/trial.py`, `backend/external/clinical_trials.py`,
  `backend/api/router.py`, `backend/api/schemas.py`, `backend/pipeline/report_builder.py`,
  `backend/pipeline/pdf_exporter.py`, `frontend/src/lib/types.ts`,
  `frontend/src/app/report/page.tsx`, `frontend/src/app/analyzing/page.tsx`,
  `tests/test_api.py`, `tests/test_clinical_trials.py`, `tests/test_report_builder.py`,
  `tests/test_pdf_exporter.py`.
- **APIs externas**: ClinicalTrials.gov (hasta 10 consultas por análisis en vez de 1–2),
  Orphanet (nueva en el pipeline; responde sin credencial, y el cliente manda
  `ORPHANET_API_KEY` si está definida), Groq (+2 llamadas por análisis, sujetas al
  límite de 12k TPM).
- **Contrato JSON**: solo aditivo; clientes que ignoren los campos nuevos siguen andando.
- **Cambios en paralelo**: #54 (EBM) ya está mergeada en `develop`; este cambio agrega
  campos y un parámetro al final, sin tocar `_rank_hypotheses` ni `RankedHypothesis`.
  #51 (Agente 02) toca `orchestrator.py`/`debate.py`, que este cambio no modifica.
- **Documentación**: `.claude/CLAUDE.md`, `.claude/backlog.md` (tarea 10 y el hallazgo
  abierto de los genes de Orphanet, que están en Orphadata),
  `.claude/architecture.md` (flujo y APIs) y `.env.example`.
