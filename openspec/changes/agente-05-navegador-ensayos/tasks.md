## 1. Modelos de datos (contrato aditivo)

- [ ] 1.1 En `backend/models/trial.py`, agregar a `ClinicalTrial` los campos `compatibility` (default `"sin_evaluar"`), `compatibility_rationale`, `criteria_to_verify`, `related_hypotheses` y `matched_terms`, con docstrings en español; verificar que `pytest tests/test_clinical_trials.py tests/test_report_builder.py tests/test_pdf_exporter.py` sigue pasando sin tocar esos tests
- [ ] 1.2 En el mismo módulo, crear `RareDiseaseMatch`, `TrialSearchSummary`, `TrialCandidate`, `PatientDemographics`, `TrialNavigationInput` y `TrialNavigationResult` (design D3/D5); verificar con tests nuevos en `tests/test_trial_matching.py` que un `ClinicalTrial` construido desde un JSON previo (sin campos nuevos) valida y queda `sin_evaluar`

## 2. Cliente Orphanet contra la API real

- [ ] 2.1 Reescribir `OrphanetClient.search()` en `backend/external/orphanet.py`: endpoint `ApproximateName/{name}` con el nombre codificado, parseo de `ORPHAcode` y `Preferred term`, 404 `"Query not found"` → `[]`, otro 404/401 → `ExternalApiError` sin reintento, timeout/conexión/5xx → reintento y `ApiUnavailableError` (design D9); verificar con tests en `tests/test_orphanet.py` para: coincidencias, "Query not found", 404 genérico, 401, 503 tras reintentos y término con `/`
- [ ] 2.2 Actualizar `test_search_error_devuelve_lista_vacia` en `tests/test_orphanet.py` al nuevo contrato (el error se propaga) y verificar que `pytest tests/test_orphanet.py` pasa
- [ ] 2.3 Agregar a `scripts/demo_orphanet.py` una sección opcional que consulte la API real con `hereditary transthyretin amyloidosis` cuando `ORPHANET_API_KEY` está definida, dejando claro en la salida qué parte es simulada; verificar corriendo `python3 scripts/demo_orphanet.py` con y sin la variable

## 3. Lógica determinista (`backend/pipeline/trial_matching.py`)

- [ ] 3.1 Implementar `build_navigation_input(case, hypotheses, statuses=None)` y la selección de candidatas (excluye `descartada`, orden prioridad → evidencia, sin duplicados, máximo 3) armando `eligibility_profile` solo con campos PICO; verificar con tests en `tests/test_trial_matching.py` que cubren los escenarios de "Entrada independiente del origen de las hipótesis" y que `raw_text` y `clinical_narrative` no aparecen en la entrada
- [ ] 3.2 Implementar `sanitize_term()` (design D7); verificar con tests que descartan `42-year-old male neuropathy`, `anti-gangliósido GM1`, términos de más de 80 caracteres u 8 palabras, y aceptan `TTR`, `PMP22` y `hereditary ATTR amyloidosis`
- [ ] 3.3 Implementar `parse_patient_demographics()` y el parseo de edades de ensayos (design D6); verificar con tests que "Paciente masculino de 42 años con DM2 de 10 años de evolución" da 42/MALE, que un perfil sin sexo da `None` y que "N/A" o formatos desconocidos dan `None`
- [ ] 3.4 Implementar los filtros duros por edad y sexo con conteo de exclusiones; verificar con tests de los escenarios "Paciente fuera del rango etario", "Ensayo sin edad máxima", "Sexo incompatible" y "Perfil sin sexo identificable"
- [ ] 3.5 Implementar la normalización de nombres y la coincidencia exacta con Orphanet (design D8); verificar con tests que `Hereditary ATTR amyloidosis` coincide con `ATTR amyloidosis, hereditary` y que `Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy` no coincide con `axonal sensorimotor polyneuropathy`
- [ ] 3.6 Implementar la unificación por NCT ID (`matched_terms`, `related_hypotheses`), el tope de 10 y el orden por compatibilidad con desempate por descubrimiento; verificar con tests de "Ensayo encontrado por dos consultas" y "Más de 10 ensayos únicos"

## 4. Agente 05 (`backend/agents/agent_05_trials.py`)

- [ ] 4.1 Crear `TrialNavigatorAgent(BaseAgent)` con `AGENT_ID="05"`, `AGENT_NAME="Navegador de Ensayos"`, `MODEL=GROQ_MAIN`, `SYSTEM_PROMPT` con las reglas de no diagnóstico y no afirmación de elegibilidad, y `run()` lanzando `NotImplementedError`; verificar con un test en `tests/test_agent_05_trials.py` que `run()` lanza y que el agente no importa ni instancia `groq` directamente
- [ ] 4.2 Implementar la planificación de términos vía `self._call_llm()` con validación de índices y saneamiento, y fallback `planificacion: "fallback"`; verificar con tests (LLM mockeado) de "Planificación exitosa", "Falla del LLM en la planificación" y "Referencia a una candidata inexistente"
- [ ] 4.3 Implementar la búsqueda en ClinicalTrials.gov (base igual a la actual + por candidata con sinónimos) usando `clinical_trials_limiter`/`clinical_trials_breaker` y `estado_clinicaltrials` ok/parcial/no_disponible/sin_consulta (design D10); verificar con tests (cliente mockeado, breakers reseteados en un fixture) de "Término principal sin resultados", "ClinicalTrials.gov caído" y "Falla parcial"
- [ ] 4.4 Implementar la consulta a Orphanet con `orphanet_limiter`/`orphanet_breaker`, `sin_configurar` cuando falta `ORPHANET_API_KEY` y construcción de `RareDiseaseMatch`; verificar con tests de "Entorno sin credencial", "Coincidencia exacta con un sinónimo" y "Orphanet caído con ClinicalTrials.gov disponible"
- [ ] 4.5 Implementar la evaluación de compatibilidad en una llamada (entrada truncada según design D11), validación de NCT IDs y etiquetas, y fallback `sin_evaluar`; verificar con tests de "Evaluación válida", "NCT ID inventado por el LLM", "Falla del LLM en la evaluación" y "Ensayo omitido por el LLM"
- [ ] 4.6 Integrar los pasos en `async navigate()` y el helper de logs sin texto clínico (design D12); verificar con tests que usan `capsys` para comprobar que, ante un `ValueError` de parseo con eco del perfil, stderr no contiene el perfil, y que ningún parámetro enviado a los clientes externos contiene "42", "masculino" ni fragmentos de la narrativa del caso base

## 5. Integración en el pipeline y el reporte

- [ ] 5.1 En `backend/api/schemas.py`, agregar al final de `StructuredReport` `rare_diseases: list[RareDiseaseMatch] = []` y `trial_search: TrialSearchSummary | None = None`; verificar con un test en `tests/test_report_builder.py` que un `StructuredReport` sin esos campos valida
- [ ] 5.2 En `backend/pipeline/report_builder.py`, agregar al final de `build_export` el parámetro `navigation: TrialNavigationResult | None = None` que completa `rare_diseases` y `trial_search`, sin tocar `_rank_hypotheses`; verificar con tests de "Hipótesis marcada como enfermedad rara", "Sin coincidencias" y "Reporte con búsqueda completa"
- [ ] 5.3 En `backend/api/router.py`, reemplazar el paso 6 por `build_navigation_input` + `asyncio.gather(_navigate_trials_safe(...), verify_report_sources(...))`, quitar el reemplazo por `chief_complaint` y el log con `{exc}` (design D4); verificar actualizando `tests/test_api.py` (el patch de `search_by_biomarkers` pasa a ser del agente) con los tests existentes de ensayos más "Error inesperado dentro del agente" devolviendo HTTP 200
- [ ] 5.4 Verificar con un test en `tests/test_api.py` que `POST /api/report/pdf` acepta un reporte previo sin `trial_search`, `rare_diseases` ni `compatibility` y responde HTTP 200

## 6. PDF exportado

- [ ] 6.1 Extender `_clinical_trials` en `backend/pipeline/pdf_exporter.py` con compatibilidad, criterios a verificar, apartado de Orphanet, aclaración orientativa y aviso de API no disponible, renderizando como hoy cuando `trial_search` es nulo (design D13); verificar con tests en `tests/test_pdf_exporter.py` de "PDF con ensayos evaluados", "PDF con la API caída" y reporte previo, extrayendo el texto del PDF generado

## 7. Frontend

- [ ] 7.1 Actualizar `frontend/src/lib/types.ts` con los campos opcionales de `ClinicalTrial`, `RareDiseaseMatch`, `TrialSearchSummary`, `rare_diseases?` y `trial_search?`; verificar que `npm run lint` y `npm run build` en `frontend/` terminan sin errores
- [ ] 7.2 Actualizar `EnsayosTab` en `frontend/src/app/report/page.tsx` (badge de compatibilidad, fundamento, criterios a verificar, hipótesis relacionadas, bloque Orphanet, aclaración, aviso de estado y `EmptyState` que distingue "sin resultados" de "no se pudo consultar"; render actual si `trial_search` es nulo); verificar con `npm run build` y abriendo la vista con un reporte nuevo y con uno previo guardado en `output/` (captura para Trello)
- [ ] 7.3 Actualizar el texto del paso de reporte en `frontend/src/app/analyzing/page.tsx` para nombrar al Agente 05; verificar visualmente en `npm run dev`

## 8. Evidencia para Trello

- [ ] 8.1 Crear `scripts/demo_agente05.py` sobre el caso base (neuropatía axonal sensitivomotora, paciente masculino de 42 años) que muestre entrada (candidatas, términos saneados, demografía detectada) → salida (ensayos con compatibilidad, excluidos por edad/sexo, enfermedades raras, estado de la búsqueda, latencia) y guarde `output/demo_agente05/navegacion.json` y `output/demo_agente05/resumen.txt`; verificar corriéndolo con `GROQ_API_KEY` y con/sin `ORPHANET_API_KEY`
- [ ] 8.2 Agregar al demo un modo `--sin-red` que use respuestas grabadas y simule la caída de ClinicalTrials.gov, Orphanet y el LLM para mostrar cada fallback; verificar con `python3 scripts/demo_agente05.py --sin-red` sin conexión

## 9. Verificación integral

- [ ] 9.1 Correr `pytest tests/` completo y verificar que no hay regresiones; correr `openspec validate agente-05-navegador-ensayos` y verificar que pasa
- [ ] 9.2 Correr `POST /api/analyze` con el caso base contra el backend real y verificar en el JSON que `clinical_trials` trae `compatibility`, que `trial_search` refleja las APIs consultadas y que el PDF exportado muestra la sección nueva

## 10. Documentación

- [ ] 10.1 Actualizar `.claude/CLAUDE.md`: marcar el Agente 05 como implementado en Sprint 4 y en la tabla de numeración, sumar `agent_05_trials.py`, `pipeline/trial_matching.py` y `demo_agente05.py` a la estructura y a la lista de demos; verificar releyendo que no queden referencias a "Agente 05 pendiente"
- [ ] 10.2 Actualizar `.claude/backlog.md`: tarea 10 del Sprint 4 como hecha con su evidencia, y hallazgos abiertos nuevos: `OrphanetClient.get_by_code()`/`_get_genes()` usan endpoints que devuelven 404 y `demo_orphanet.py` usaba solo datos simulados; verificar que la tabla de hallazgos quedó con archivo y línea
- [ ] 10.3 Actualizar `.claude/architecture.md` (Agente 05 en paralelo con la verificación hasta que exista el Árbitro, endpoints reales de Orphanet, campos nuevos de `ClinicalTrial` y `StructuredReport`) y el comentario de `ORPHANET_API_KEY` en `.env.example`; verificar que el diagrama y la sección "APIs externas" coinciden con el código
