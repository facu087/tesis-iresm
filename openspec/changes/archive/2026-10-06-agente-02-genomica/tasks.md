## 1. Perfil genómico determinista

- [x] 1.1 Crear `backend/models/genomics.py` con `GenomicSourceStatus` (`consultada`, `sin_resultados`, `no_disponible`, `no_consultada`), `GenomicSource`, `PharmacogenomicAnnotation` y `GenomicContext` (variantes, hallazgos genéticos, genes saneados, `discarded_symbols`, estudios genéticos negativos, anotaciones, fuentes), con la propiedad `has_genomic_findings` y el método `to_prompt_block()`; todo Pydantic, tipado y con docstrings en español. Verificar con los tests de 1.4.
- [x] 1.2 Agregar `genomic_context: GenomicContext | None = None` a `ClinicalCase` en `backend/models/case.py`. Verificar que `pytest tests/test_orchestrator.py tests/test_debate.py tests/test_api.py` sigue pasando sin cambios.
- [x] 1.3 Crear `backend/pipeline/genomic_context.py` con `build(case) -> GenomicContext`, sin red ni LLM: saneamiento de símbolos (formato + lista de siglas no-gen `CMT`, `FAP`, `ATTR`, `HMSN`, `CIDP`, `EMG`, `LCR`, …), estudios genéticos negativos tomados de `negative_findings` por palabras clave, reclasificación de `genetic_findings` redactados como negativos, y modo con/sin hallazgos. Verificar con los tests de 1.4.
- [x] 1.4 Crear `tests/test_genomic_context.py` con el caso base (neuropatía axonal sensitivomotora, hombre de 42 años, `genes=['CMT']` tal como lo devuelve hoy la capa regex): `CMT` descartado, 0 variantes, "Panel CMT 40 genes negativo" como estudio negativo, modo sin hallazgos; más los escenarios de TTR `p.Val30Met`, estudio negativo cargado en `genetic_findings`, `PMP22` solo mencionado, entrada no simbólica, reproducibilidad y contenido del bloque en modo sin hallazgos y con fuente `no_disponible`. Verificar con `pytest tests/test_genomic_context.py`.

## 2. PharmGKB: verificación real, errores visibles y enriquecimiento

- [x] 2.1 Hacer una solicitud real a PharmGKB por `TTR` (solo el símbolo) y comparar rutas (`/v1/gene`, `/v1/clinicalAnnotation`) y forma de la respuesta con lo que asume `backend/external/pharmgkb.py`; si no coinciden, corregir el cliente. Verificar guardando la respuesta cruda recortada en `output/demo_agente02/pharmgkb_ttr_real.json`.
- [x] 2.2 Modificar `backend/external/pharmgkb.py`: quitar los `except (httpx.HTTPError, Exception): pass`, propagar `ApiUnavailableError` / `RateLimitError` de `rate_limiter.py`, envolver cada solicitud con `pharmgkb_limiter` y `pharmgkb_breaker`, y devolver `[]` solo cuando la API respondió sin datos. Verificar con tests nuevos en `tests/test_pharmgkb.py` (HTTP 503 → `ApiUnavailableError`, respuesta vacía → `[]`, breaker abierto → error sin solicitud HTTP) y con los tests existentes pasando.
- [x] 2.3 Implementar `async enrich(ctx) -> GenomicContext` en `backend/pipeline/genomic_context.py`: máximo 3 genes, sin consulta si no hay genes, `try/except` explícito que traduce a los cuatro estados, log en stderr con nombre de fuente y tipo de error sin datos clínicos, y nunca lanza. Verificar con los tests de 2.4.
- [x] 2.4 Agregar a `tests/test_genomic_context.py` (cliente mockeado, `pharmgkb_breaker.reset()` en un fixture): sin genes → ninguna solicitud y `no_consultada`; 5 genes → 3 solicitudes; 503 → `no_disponible` y perfil entregado; respuesta vacía → `sin_resultados`; anotaciones → `consultada`; anonimización: los parámetros capturados contienen solo símbolos y ningún fragmento de la narrativa, el perfil del paciente o los estudios negativos. Verificar con `pytest tests/test_genomic_context.py`.

## 3. Agente 02 — Especialista Genómica

- [x] 3.1 Crear `backend/agents/agent_02_genomics.py` con `GenomicsSpecialistAgent` (`AGENT_ID="02"`, `AGENT_NAME="Especialista Genómica"`, `MODEL=GROQ_MAIN`), constructor con `genomic_context: GenomicContext | None = None` y `run()` que agrega `to_prompt_block()` al contexto y llama al LLM solo vía `_call_llm()`. El `SYSTEM_PROMPT` prohíbe diagnósticos y tratamientos, exige hipótesis de investigación, pide razonar patrón de herencia y cobertura de estudios negativos, define el modo orientación, pide 1 a 4 hipótesis con `case_genetic_findings` y PMID `null` si no hay certeza, y **no nombra enfermedades ni genes concretos**. Verificar con los tests de 3.5.
- [x] 3.2 Implementar la guarda anti-invención: leer `case_genetic_findings` del JSON crudo, chequear hallazgos no reportados (normalizando mayúsculas, espacios y prefijos `c.`/`p.`/`g.`) y notación de variante en `text` en modo orientación; degradar a `priority=LOW` con advertencia al inicio del `rationale`, sin descartar, y loggear solo la cantidad de hipótesis marcadas. Verificar con los tests de 3.5.
- [x] 3.3 Sobrescribir `critique()` y `revise()` para agregar el bloque genómico al contexto del debate y delegar en `BaseAgent`; `revise()` aplica la guarda. Verificar con los tests de 3.5.
- [x] 3.4 Exportar `GenomicsSpecialistAgent` en `backend/agents/__init__.py`. Verificar con `python3 -c "from backend.agents import GenomicsSpecialistAgent"`.
- [x] 3.5 Crear `tests/test_agent_02_genomics.py` con `_call_llm` mockeado: identidad del output; respuesta válida; 6 hipótesis → quedan las 4 primeras (en `run()` y en `revise()`); respuesta malformada → `ValueError`; en el caso base `run()` hace exactamente 1 llamada al LLM y el prompt afirma que no hay variantes ni hallazgos positivos; en el caso TTR el prompt contiene `p.Val30Met`; los cuatro escenarios de la guarda; `critique()` incluye el bloque en el prompt; `revise()` aplica la guarda; el módulo no importa `groq`. Verificar con `pytest tests/test_agent_02_genomics.py`.

## 4. Integración en Ronda 1 y debate

- [x] 4.1 Modificar `backend/pipeline/orchestrator.py`: `asyncio.gather` del enriquecimiento RAG y del perfil genómico (`build` + `enrich`), guardar el perfil en `case.genomic_context` y correr `[01, 02, 03]` en paralelo; actualizar docstrings. Verificar con los tests de 4.3.
- [x] 4.2 Modificar `backend/pipeline/debate.py`: incluir solo agentes con output de Ronda 1 (corrige el `KeyError` actual) e instanciar el Agente 02 con `case.genomic_context` o, si falta, con `genomic_context.build(case)` sin red. Verificar con los tests de 4.4.
- [x] 4.3 Actualizar `tests/test_orchestrator.py`: parchear `GenomicsSpecialistAgent` en los tests existentes y agregar: tres agentes → tres outputs `01`/`02`/`03`; el Agente 02 falla → quedan 01 y 03; `case.genomic_context` queda cargado. Verificar con `pytest tests/test_orchestrator.py`.
- [x] 4.4 Actualizar `tests/test_debate.py`: parchear `GenomicsSpecialistAgent` y agregar: Ronda 1 sin el Agente 02 → el debate completa las Rondas 2–4 sin error; con tres agentes la Ronda 2 hace tres llamadas de crítica, cada una con los otros dos outputs; durante el debate no hay solicitudes a PharmGKB. Verificar con `pytest tests/test_debate.py`.
- [x] 4.5 Agregar a `tests/test_agent_02_genomics.py` un test de atribución: un `Report` con una hipótesis del Agente 02 en la Ronda 4 pasa por `build_export()` y la hipótesis exportada lista `"Especialista Genómica"` en `supporting_agents`, sin tocar `tests/test_report_builder.py`. Verificar con `pytest tests/test_agent_02_genomics.py`.

## 5. Frontend

- [x] 5.1 Cambiar en `frontend/src/app/analyzing/page.tsx` el subtítulo del paso de Ronda 1 a "Agentes 01, 02 y 03 en simultáneo". Verificar con `npm run lint` y `npm run build` en `frontend/`, y viendo el texto en la vista de pipeline.

## 6. Evidencia para Trello y medición

- [x] 6.1 Crear `scripts/demo_agente02.py` con dos escenarios y salida entrada → salida: (A) caso base con PICO armada a mano y `genes=['CMT']`: perfil genómico (`CMT` descartado, 0 variantes, modo orientación, PharmGKB `no_consultada`), bloque enviado al agente, hipótesis y marcas de la guarda; (B) caso sintético con `TTR` y `p.Val30Met`: estado real de PharmGKB, anotaciones, bloque e hipótesis. Si Groq no tiene cupo, mostrar igual el perfil y el bloque y avisar, como `demo_agente03.py`. Verificar corriendo `python3 scripts/demo_agente02.py` y confirmando `output/demo_agente02/contexto_caso_base.json`, `hipotesis_caso_base.json`, `contexto_ttr.json` e `hipotesis_ttr.json`.
- [x] 6.2 Actualizar los textos de `scripts/demo_orquestador.py` a tres agentes ("Agentes 01, 02 y 03", "3 llamadas concurrentes", "de 3"). Verificar corriendo `python3 scripts/demo_orquestador.py`.
- [x] 6.3 Medir el pipeline completo sobre el caso base (Ronda 1 + debate): llamadas al LLM, tiempo total, tiempo del debate y cantidad de reintentos por 429, contra la línea de base de 25 s del debate con dos agentes. Verificar guardando la medición en `output/demo_agente02/medicion_pipeline.txt`.
- [x] 6.4 Correr `pytest tests/` y verificar que no hay fallas nuevas respecto de `develop` (los tests de integración RAG que usan red quedan fuera de la comparación, ver hallazgo B del backlog).

## 7. Documentación

- [x] 7.1 Actualizar `.claude/CLAUDE.md`: Agente 02 marcado como hecho en Sprint 4 y en la tabla de numeración, `agent_02_genomics.py`, `models/genomics.py` y `pipeline/genomic_context.py` en el árbol de carpetas, `demo_agente02.py` en la lista de scripts y la constante `GROQ_MAIN` descripta para los agentes 01, 02, 03 y 06. Verificar leyendo las secciones actualizadas.
- [x] 7.2 Actualizar `.claude/backlog.md`: tarea 8 con su estado y evidencia, resultado de la medición de 6.3 y hallazgos abiertos nuevos: `CMT`/`FAP`/`ATTR` en `_KNOWN_GENES` del extractor (fix pendiente), ClinVar como tarjeta nueva y el demo de PharmGKB con datos simulados. Verificar leyendo la tabla del Sprint 4 y la de hallazgos.
- [x] 7.3 Actualizar `.claude/architecture.md`: herramientas del Agente 02 ("PharmGKB; ClinVar pendiente"), `GenomicContext` en los modelos de datos y el campo `genomic_context` de `ClinicalCase`. Verificar con `openspec validate agente-02-genomica`.

## Revisión del 2026-10-06

Las tareas se implementaron en el PR #12 pero nunca se tildaron. Al revisarlas contra el código
de `develop` aparecieron faltantes, que se completaron en la rama `fix/s4-agente02-guarda`:

- **3.2 (bug):** la guarda buscaba `case_genetic_findings` en la `Hypothesis` parseada, que no
  tiene ese campo; en un caso con hallazgos genéticos nunca degradaba nada. Ahora lo lee del JSON
  crudo (`_declared_findings`). Tests nuevos en `TestGuardaConHallazgos`, que fallan con el
  código anterior.
- **2.1:** respuesta real de ClinPGx para `TTR` guardada en
  `output/demo_agente02/pharmgkb_ttr_real.json` (404 "No results matching criteria." = sin
  resultados; `CYP2D6` responde 200).
- **2.2:** faltaba el circuit breaker (`pharmgkb_breaker`); tests en `TestCircuitBreaker`.
- **4.3 / 4.4 / 4.5:** tests de Ronda 1 y debate con tres agentes, y de atribución en
  `build_export()`.
- **6.1 / 6.2:** `demo_agente02.py` estaba solo en la rama sin mergear; `demo_orquestador.py`
  seguía hablando de dos agentes.
- **6.3:** `medicion_pipeline.txt` tenía estimaciones; ahora tiene la corrida real del
  2026-10-06 (`scripts/medir_costos.py --grabar`): Ronda 1 43 s, debate 352 s de 495 s,
  26 llamadas (4 reintentadas por 429), 82.968 tokens.
- **7.1–7.3:** documentación completada (árbol de carpetas, scripts, `GenomicContext` en
  `architecture.md`, hallazgo F resuelto y nota (21) en `backlog.md`).
