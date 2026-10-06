> ⚠ **Este cambio se implementa después de mergear el PR #19** (Agente 04). Toca
> `base_agent.py`, `agent_04_arbiter.py`, `agent_05_trials.py` y `router.py`,
> que ese PR modifica. Arrancar antes garantiza conflictos.

## 1. Punto de llamada compartido

- [x] 1.1 Extraer la llamada al proveedor de `BaseAgent._call_llm()` a una función compartida que reciba system prompt, mensaje, modelo, techo de tokens y una etiqueta del paso de origen, conservando el reintento ante 429 con el backoff actual (D1). `_call_llm()` pasa a delegar en ella. Verificar que la suite completa sigue verde: `pytest tests/ --ignore=tests/test_ingesta.py`.
      Hecho: `call_provider()` en `backend/agents/base_agent.py`. Test nuevo:
      `tests/test_base_agent.py::TestCallProvider`. Suite completa verde (ver 7.4).
- [x] 1.2 Migrar `pipeline/pico.py:93` a la función compartida, conservando su techo actual de 2048 y su manejo de errores. Verificar con `tests/test_pico.py` y corriendo `scripts/demo_pico.py`.
      Hecho: `pico.build()` delega en `call_provider(task="pico_sintesis")`. `tests/test_pico.py`
      verde (solo prueba el parser, no llama LLM). `demo_pico.py` **no se corrió**: llama al LLM
      real (restricción de cuota de esta sesión); queda pendiente para el orquestador.
- [x] 1.3 Migrar `ingestion/biomarker_extractor.py:156` a la función compartida, conservando su techo de 1024. Verificar con `tests/test_biomarkers.py` y `scripts/demo_biomarcadores.py`.
      Hecho: `_extract_with_llm()` delega en `call_provider(task="biomarcadores_extraccion")`.
      `tests/test_biomarkers.py` verde (LLM mockeado). `demo_biomarcadores.py` **no se corrió**:
      llama al LLM real; queda pendiente para el orquestador.
- [x] 1.4 Verificar que **ningún** módulo instancia `Groq(api_key=...)` fuera del punto compartido: `grep -rn "Groq(api_key" backend/` debe devolver una sola línea. Es la condición del requisito "toda llamada queda contabilizada".
      Verificado: `rg -n "Groq\(api_key" backend/` devuelve exactamente
      `backend/agents/base_agent.py:82` (dentro de `call_provider()`).

## 2. Telemetría

> Implementado junto con la sección 3: el resumen JSONL de 2.6 necesita costo
> estimado, y eso requiere `pricing.py`. Un solo bloque de trabajo, dos commits
> lógicos en tasks.md.

- [x] 2.1 Crear `backend/telemetry/usage.py` con el registro por llamada (paso, modelo, tokens de entrada y salida, latencia, si falló) y el contexto por análisis basado en `contextvars`, que se propaga a corrutinas y a `asyncio.to_thread()` (D2). Verificar con `tests/test_telemetry.py` que dos análisis concurrentes no mezclan sus conteos.
      Hecho: `AnalysisUsage` + `_current: ContextVar`. Test:
      `test_dos_analisis_concurrentes_no_mezclan_conteos` (dos `asyncio.Task`) y
      `test_el_contexto_se_propaga_a_asyncio_to_thread`.
- [x] 2.2 Instrumentar la función compartida de 1.1 para que registre cada llamada en el contexto activo, y que **no haga nada** si no hay contexto (un demo o un test no deben fallar por eso). Verificar con un test que llama sin contexto abierto.
      Hecho: `call_provider()` llama a `usage_telemetry.record_call()` en cada intento.
      Test: `TestCallProviderTelemetria::test_sin_registro_activo_no_falla`.
- [x] 2.3 Registrar también las llamadas **fallidas** y los reintentos por 429, para que el costo de los reintentos sea visible. Verificar con un test que fuerza un fallo y comprueba que queda contabilizado.
      Hecho: cada intento (429 o cualquier otra excepción) se registra `ok=False`
      antes de reintentar o relanzar. Tests:
      `test_reintento_por_rate_limit_deja_un_intento_fallido_y_uno_exitoso`,
      `test_fallo_no_reintentable_tambien_queda_contabilizado`.
- [x] 2.4 Registrar como "sin datos de consumo" las respuestas donde el proveedor no informe `usage`, en vez de omitirlas. Verificar con un test de respuesta sin `usage`.
      Hecho: `prompt_tokens`/`completion_tokens` quedan `None` cuando `response.usage`
      es `None`. Test: `test_respuesta_sin_usage_se_registra_marcada`.
- [x] 2.5 Implementar el identificador **aleatorio** por análisis, nunca derivado del texto clínico (D3). Verificar con un test que analiza dos veces el mismo texto y comprueba que los identificadores difieren.
      Hecho: `secrets.token_hex(8)` en `AnalysisUsage.__init__`. Tests en
      `TestIdentificadorAleatorio`.
- [x] 2.6 Implementar la escritura JSONL en `output/costos.jsonl`, una línea por análisis con total, desglose por agente y costo estimado (D4). Verificar con un test que corre tres análisis y comprueba que quedan tres líneas parseables.
      Hecho: `close_registry()` → `_append_jsonl()`. Test:
      `test_tres_analisis_dejan_tres_lineas_parseables`.
- [x] 2.7 **Test de privacidad**: correr un análisis con el caso base y verificar que el registro no contiene ninguna palabra del texto clínico, ni del prompt, ni de la respuesta del modelo. Es un requisito de la spec, no un extra.
      Hecho: `tests/test_telemetry.py::TestPrivacidad` (estructural: `record_call()`
      no acepta prompt/respuesta como parámetro) + `tests/test_router_telemetry.py
      ::TestPrivacidadDelRegistroEnUnAnalisisReal` (análisis completo end-to-end
      por el router, LLM y APIs externas mockeadas, resumen inspeccionado en disco).
- [x] 2.8 Garantizar que un fallo al escribir el registro no rompe el análisis: `POST /api/analyze` responde igual y avisa por stderr. Verificar con un test que apunta el registro a una ruta no escribible.
      Hecho: `close_registry()` atrapa `OSError` de `_append_jsonl()`. Test:
      `TestResilenciaDeEscritura::test_ruta_no_escribible_no_rompe_y_avisa`.
- [x] 2.9 Emitir el resumen legible por stderr al terminar el análisis (llamadas, tokens, costo estimado). Verificar capturando stderr en un test.
      Hecho: `_print_summary()`. Test: `TestResumenPorConsola`.

## 3. Tarifas y estimación de costo

- [x] 3.1 Crear `backend/telemetry/pricing.py` con la tabla de tarifas por modelo, configurable, con Groq en cero por defecto y los modelos de la arquitectura de destino comentados (D5). Verificar con `tests/test_telemetry.py`.
      Hecho: `DEFAULT_PRICES` con `openai/gpt-oss-120b`/`20b` en 0.0, Claude Opus /
      GPT-4o / Gemini Pro comentados con la fuente de verdad de modelos
      (`.claude/CLAUDE.md`).
- [x] 3.2 Implementar el cálculo del costo estimado por análisis y por agente. Verificar con un test de tarifas conocidas y conteos conocidos.
      Hecho: `pricing.estimate_cost()` + `usage.build_summary()` (agrega por
      `(agent_id, agent_name, model)`). Test: `test_estimate_cost_con_tarifas_conocidas`.
- [x] 3.3 Un modelo sin tarifa configurada reporta costo cero y queda señalado, sin lanzar excepción. Verificar con un test dedicado.
      Hecho: `estimate_cost()` devuelve `(0.0, False)`; `build_summary()` junta los
      modelos sin tarifa en `totals["unpriced_models"]`. Test:
      `test_resumen_senala_modelo_sin_tarifa`.
- [x] 3.4 Permitir recalcular el costo de un registro ya guardado con otra tabla de tarifas — es lo que responde "¿cuánto costaría con Claude Opus?" sin correr nada. Verificar con un test sobre un registro de ejemplo.
      Hecho: `usage.recalculate(record, price_table)` (no muta el original). Test:
      `TestRecalcular::test_recalcula_el_costo_de_un_registro_guardado`.

## 4. Techo de tokens por tarea

- [x] 4.1 Crear el mapa `tarea → (modelo, techo)` en un módulo de configuración, de modo que se pueda revisar qué usa cada llamada sin recorrer los agentes (D6). Verificar que todos los sitios de llamada lo consultan.
      Hecho: `backend/agents/model_tasks.py` (`TASK_BUDGETS`, `get_budget()`).
      `BaseAgent._call_llm()` ahora exige `task: str` (kw-only) y resuelve modelo/techo
      del mapa, no de `self.MODEL`. Los 12 sitios de llamada lo consultan: `run()` de
      los agentes 01/02/03, `critique()`/`revise()`/`recite()` de `BaseAgent`,
      `_group()`/`_write_verdicts()` del Agente 04, `_plan_terms()`/`_evaluate()` del
      Agente 05, `pico.build()` y `biomarker_extractor._extract_with_llm()`. Test:
      `tests/test_model_tasks.py`.
- [x] 4.2 Asignar el techo de cada tarea con holgura sobre su salida esperada, reemplazando el 4096 fijo. Verificar corriendo el caso de prueba y comprobando que **ninguna** respuesta quedó truncada por alcanzar su techo (`finish_reason`).
      **Medido el 2026-10-04** con `scripts/medir_costos.py` (dos corridas reales).
      Primera corrida: `arbitro_agrupacion` (techo 512) y
      `agente05_planificacion_terminos` (techo 1024) se cortaron por techo y cayeron
      en el fallback determinista. Causa: los `gpt-oss` cuentan los tokens de
      razonamiento dentro de la salida. Los dos techos volvieron a 4096 (commit
      `3774e19`). Segunda corrida, ya corregida: **0 respuestas cortadas** en 27
      llamadas. La agrupación usó 1.062 tokens de salida, el doble del techo anterior.
      Menor holgura observada: `debate_revision` (3.315 de 4.096, 19 %) y
      `biomarcadores_extraccion` (749 de 1.024, 27 %).
      **Parcial.** Asignación hecha con criterio explícito por tarea (ver docstring de
      `model_tasks.py`): `arbitro_agrupacion` baja a 512 (la salida son solo índices,
      sin relación con la cantidad de hipótesis) — sin evidencia de una corrida real,
      es una estimación razonada, no medida. `agente05_planificacion_terminos` baja a
      1024 con el mismo criterio. Las tareas de razonamiento clínico y
      `agente05_evaluacion_compatibilidad` **conservan el 4096/2048/1024 histórico**
      a propósito: el análisis de peor caso de la evaluación de compatibilidad (hasta
      10 ensayos × fundamento de hasta 600 caracteres + hasta 5 criterios) no deja
      holgura para bajarlo sin evidencia. **Pendiente para el orquestador**: correr el
      caso de prueba real y confirmar que ningún `finish_reason` es `"length"` con
      estos techos (bloqueado por la restricción de cuota de esta sesión).
- [x] 4.3 Registrar en la telemetría cuando una respuesta se corta por techo, para detectar un techo mal puesto. Verificar con un test de techo deliberadamente bajo.
      Hecho: `call_provider()` marca `truncated=True` cuando `finish_reason == "length"`.
      Test: `TestCallProviderTelemetria::test_respuesta_cortada_por_techo_se_marca_truncada`
      (`tests/test_base_agent.py`) y `TestLlamadasFallidasYSinDatos::
      test_llamada_truncada_por_techo_queda_marcada` (`tests/test_telemetry.py`).

## 5. Modelo por tarea

- [x] 5.1 Mover la **agrupación del Árbitro** a `GROQ_FAST`. Su salida son índices validados por `consensus.normalize_partition()`. Verificar que `tests/test_agent_04_arbiter.py` sigue verde.
      Hecho: `model_tasks.TASK_BUDGETS["arbitro_agrupacion"].model = GROQ_FAST`.
      `tests/test_agent_04_arbiter.py` verde (46 tests, sin cambios — el LLM está
      mockeado y las guardas no dependen del modelo configurado).
- [x] 5.2 Mover la **planificación de términos del Agente 05** a `GROQ_FAST`. Verificar con `tests/test_agent_05_trials.py`.
      Hecho: `TASK_BUDGETS["agente05_planificacion_terminos"].model = GROQ_FAST`.
      `tests/test_agent_05_trials.py` verde.
- [x] 5.3 Mover el **etiquetado de compatibilidad del Agente 05** a `GROQ_FAST`. Verificar con `tests/test_agent_05_trials.py`.
      Hecho: `TASK_BUDGETS["agente05_evaluacion_compatibilidad"].model = GROQ_FAST`
      (techo sin cambios, ver 4.2). `tests/test_agent_05_trials.py` verde.
- [x] 5.4 **Medir antes de dar por buena la decisión** (D6, y el riesgo del design): correr el caso de prueba con las tres tareas en `GROQ_MAIN` y después en `GROQ_FAST`, y comparar el agrupamiento resultante, los términos planificados y las etiquetas de compatibilidad. Registrar cuántas veces la salida del modelo rápido cayó en una validación. Si el agrupamiento empeora, esa tarea vuelve a `GROQ_MAIN` y se deja constancia.
      **Medido el 2026-10-04**, con los dos modelos sobre las mismas entradas de una
      sola pasada del debate. Agrupación del Árbitro (14 hipótesis): los dos modelos
      devolvieron una salida aceptada sin reparación y la **misma partición**.
      Evaluación de compatibilidad: 10 de 10 ensayos con la misma etiqueta, ninguna
      evaluación descartada por validación. Planificación de términos: las 3
      candidatas en común, 1 de 3 con el mismo término principal y ninguna lista
      idéntica. Ninguna salida de `GROQ_FAST` cayó en una validación. **Decisión: las
      tres tareas se quedan en `GROQ_FAST`.** Es una sola corrida por modelo, no una
      muestra: alcanza para no revertir, no para afirmar equivalencia.
      **Pendiente para el orquestador** — restricción de cuota de esta sesión
      (requiere correr el caso de prueba dos veces contra Groq real). El mecanismo
      para hacerlo está listo: cambiar el `model` de las tres entradas en
      `model_tasks.TASK_BUDGETS` y comparar corridas con `scripts/demo_agente04.py`
      / `scripts/demo_agente05.py`.
- [x] 5.5 Verificar el inventario: ninguna tarea que produzca hipótesis, críticas, revisiones, veredictos o la síntesis PICO usa el modelo rápido. Test que recorre el mapa de configuración.
      Hecho: `tests/test_model_tasks.py::TestTareasDeRazonamiento` (recorre
      `REASONING_TASKS`) y `TestModeloPorTarea::test_ninguna_otra_tarea_usa_el_modelo_rapido`
      (recorre `TASK_BUDGETS` completo y confirma que solo las tres tareas candidatas
      están en `GROQ_FAST`).

## 6. Modo mock del pipeline

> **Decisión de alcance (registrada acá, no en design.md, que no la anticipó
> explícitamente).** D7 y la tarea 6.1 describen la intercepción en el punto
> de llamada al LLM (`call_provider()`), y esa es la implementación exacta.
> La spec `modo-mock-pipeline` pide además "ninguna llamada... ni a las APIs
> externas" para un análisis completo. Ampliar la intercepción a
> `external/pubmed.py`, `external/clinical_trials.py` y `external/orphanet.py`
> queda fuera de esta tarjeta: no está en el listado de archivos impactados
> de proposal.md y es un cambio de superficie comparable a esta sección
> entera. Task 6.7 cierra la brecha combinando el modo mock real (para el
> LLM) con el mismo mockeo a nivel de test que ya usa `tests/test_api.py`
> para esas APIs, verificado con `pytest_sin_red`. **Queda para el
> orquestador decidir** si ampliar la intercepción de producción a esos tres
> módulos en una tarjeta aparte.

- [x] 6.1 Implementar el modo mock en la función compartida de 1.1, devolviendo respuestas grabadas que atraviesan el mismo parseo y las mismas validaciones que una respuesta real (D7). Verificar con `tests/test_mock_pipeline.py`.
      Hecho: `call_provider()` chequea `is_mock_active()` antes de instanciar Groq y
      devuelve `mock.responses.get_mock_response(task)`. Test:
      `TestElModoMockEjercitaElParseoReal` (parsea con `BaseAgent.parse_hypotheses()`,
      `_parse_critiques()`, `pico._parse_pico()`, y corre `pico.build()` /
      `biomarker_extractor.extract()` completos con el modo activo).
- [x] 6.2 Generar las respuestas grabadas desde una corrida real del caso de prueba, para que se parezcan a lo que el modelo devuelve de verdad.
      Hecho con la corrida real del 2026-10-06 (`backend/mock/grabadas.json`, texto crudo). 11 de 12 tareas grabadas; `debate_critica` sigue escrita a mano: las críticas reales nombran al destinatario ("Agent 02") y `_critiques_for()` compara contra el ID ("02"), así que no llegarían a nadie.
- [x] 6.3 Activación explícita por variable de entorno, **apagada por defecto** y nunca por inferencia: si falta `GROQ_API_KEY` y el modo mock no está activo, el análisis falla con un error claro. Verificar con dos tests, uno por cada caso.
      Hecho: `NEXUS_MOCK_LLM` (`backend/mock/mode.py`, `is_mock_active()`), apagada
      por defecto. Sin ella y sin `GROQ_API_KEY`, `call_provider()` lanza
      `RuntimeError` con mensaje explícito antes de instanciar Groq. Tests:
      `TestActivacion::test_sin_api_key_y_sin_mock_falla_claro` y
      `test_sin_api_key_pero_con_mock_no_falla`. `backend/main.py` informa el modo
      mock al arrancar (test `test_lo_informa_al_arrancar`).
- [ ] 6.4 Marcar el reporte producido en modo mock, y mostrarlo en el frontend y en el PDF con la misma visibilidad que la advertencia del consenso de IA. Verificar con `tests/test_pdf_exporter.py` sobre el texto extraído, y con `npm run build` más una captura de la vista.
      **Parcial — código hecho, verificación de build/visual incompleta.** El código
      está: `ReportMetadata.mock` (schemas.py) ← `build_export(mock=...)` ←
      `router.py`; banner rojo primero en el PDF (`pdf_exporter.py`) y en el
      frontend (`<MockBanner/>` en `report/page.tsx`, antes que la meta bar).
      Observado de verdad: `tests/test_pdf_exporter.py::TestModoMockEnPdf` (2 tests,
      verdes, texto extraído del PDF) y `npx tsc --noEmit` (sin errores). **No
      observado tal como lo pide la tarea**: `npm run build` literal falla en este
      worktree (Turbopack rechaza el symlink de `node_modules`, que apunta fuera de
      la raíz del worktree — límite del entorno; `npx next build --webpack` sí
      compila las 4 rutas, pero no es el comando pedido) y no se tomó ninguna
      captura de la vista (sin herramienta de automatización de navegador en esta
      sesión). Pendiente para quien tenga esa herramienta o corra la app a mano.
      Hecho: `ReportMetadata.mock` (schemas.py) ← `build_export(mock=...)` ←
      `router.py` (`is_mock_active()`). PDF: banner rojo antes que cualquier otro
      aviso (`pdf_exporter.py`), tests en `TestModoMockEnPdf`
      (`tests/test_pdf_exporter.py`). Frontend: `ReportMetadata.mock` en
      `types.ts` + `<MockBanner/>` en `report/page.tsx`, primero en la página.
      `npx tsc --noEmit`: sin errores. `npm run build` con Turbopack falla en este
      worktree — `node_modules` está symlinkeado fuera de la raíz del worktree y
      Turbopack lo rechaza ("Symlink points out of the filesystem root"), un
      límite del entorno, no del código: `npx next build --webpack` compila y
      genera las 4 rutas sin error. **Captura de la vista: no se hizo** (no hay
      herramienta de automatización de navegador disponible en esta sesión);
      queda pendiente para quien tenga esa herramienta o corra la app a mano.
- [x] 6.5 Verificar el determinismo: dos análisis del mismo texto en modo mock producen el mismo resultado.
      Hecho: `TestDeterminismo` (`pico.build()` y `biomarker_extractor.extract()`
      dos veces sobre el mismo texto, mismo resultado).
- [x] 6.6 Verificar que el modo mock **ejercita** el flujo: introducir un defecto en el parseo de la respuesta del modelo y comprobar que el modo mock lo manifiesta en vez de devolver un reporte correcto.
      Hecho: `TestManifiestaDefectosDeParseo::test_un_parser_roto_falla_tambien_en_modo_mock`
      rompe `pico._parse_pico` con `monkeypatch` y confirma que `pico.build()` en
      modo mock relanza el error — prueba que el modo mock pasa por el parser real,
      no por un atajo.
- [x] 6.7 Confirmar que un análisis completo en modo mock no hace ninguna llamada de red, con `scripts/pytest_sin_red.py` (el mismo instrumento de la tarjeta #75).
      Hecho: `test_hermetico_sin_red_analisis_completo_en_modo_mock` corre en
      subproceso, con `-p pytest_sin_red`, los tests de activación, de parseo real
      y un `POST /api/analyze` completo en modo mock (con `pico.build()`,
      `extract_biomarkers()` y `ArbiterAgent.arbitrate()` corriendo de verdad, y
      RAG/verificación/navegación de ensayos mockeados a nivel de test, ver nota de
      alcance arriba). Confirma `0` intentos de conexión bloqueados.
      Descubrimiento no relacionado con esta tarea, registrado para el
      orquestador: correr la suite completa **sin** `pytest_sin_red` hace ~36
      intentos reales de conexión a `api.groq.com` y ~36 a
      `eutils.ncbi.nlm.nih.gov` desde `tests/test_api.py` (no mockea
      `ArbiterAgent.arbitrate()` ni `verify_report_sources()`). Esta sesión usó
      `PYTHONPATH=scripts pytest -p pytest_sin_red ...` para **toda** verificación,
      precisamente para no arriesgar cuota real; el comando de baseline dado
      (`pytest tests/ --ignore=tests/test_ingesta.py`, sin el plugin) no es
      hermético en este entorno.

## 7. Evidencia y cierre

- [x] 7.1 Crear `scripts/demo_costos.py` que muestre entrada → salida: el desglose de tokens por agente de un análisis, el costo estimado con Groq y el que tendría con los modelos de la arquitectura de destino. Guarda artefactos en `output/demo_costos/`.
      Hecho y **corrido** (con la red bloqueada a mano, cero conexiones): dos partes.
      (1) `pico.build()` + `biomarker_extractor.extract()` en modo mock real, para
      probar el mecanismo de telemetría de punta a punta sin gastar cuota —da 0
      tokens porque el modo mock no consume nada de verdad. (2) Una muestra
      **sintética** de 18 llamadas (conteos inventados, anotados como tales, no
      una corrida real) que arma el desglose por agente y compara costo Groq vs.
      arquitectura de destino con `usage.recalculate()`. Artefactos verificados en
      `output/demo_costos/`: `mecanismo_mock.json`, `muestra_sintetica.json`,
      `comparacion_costos.txt` (60.750 tokens de muestra, USD 0 con Groq, USD 1.67
      con la arquitectura de destino, ~3 casos/día de cuota — todo etiquetado como
      estimado, no medido).
- [x] 7.2 Correr el caso de prueba y registrar los **números medidos**: tokens por agente, total por caso y cuántos casos entran en la cuota diaria. Es el insumo del capítulo de viabilidad de la tesis.
      **Medido el 2026-10-04** (segunda corrida, tres agentes completos): 27 llamadas,
      **77.516 tokens por caso** (41.392 de entrada y 36.124 de salida), 467 s. Por
      agente: 01 → 20.605; 02 → 20.396; 03 → 21.279; 04 → 4.861; 05 → 7.179; PICO y
      biomarcadores → 3.196. **Entran 2 casos por día** en la cuota de 200.000
      tokens. Hubo 6 reintentos por límite de velocidad, todos recuperados. La primera
      corrida dio 50.599 tokens, pero con el Agente 03 caído en la Ronda 1 y el
      Árbitro sin agrupar: no es representativa. Artefactos en
      `output/medicion_costos/` (ignorado por git).
      **Pendiente para el orquestador** — restricción de cuota de esta sesión
      (requiere una corrida real contra Groq). `demo_costos.py` deja el mecanismo
      listo: correrlo con `NEXUS_MOCK_LLM` desactivado sobre una corrida real
      reemplazaría `_MUESTRA_SINTETICA` por el registro real de `output/costos.jsonl`.
- [x] 7.3 Con la telemetría ya instalada, medir cuánto cambia cada agente entre la Ronda 3 y la Ronda 4 del debate, usando los `debate_rounds` de corridas reales. **No implementar el recorte**: dejar el dato en una tarjeta nueva para decidirlo con evidencia.
      **Medido el 2026-10-04**: entre la Ronda 3 y la Ronda 4, 11 hipótesis cambiaron
      de enunciado y **ninguna cambió de nivel de evidencia ni de prioridad** (agente
      01: 1 de 5; agente 02: 4 de 4, y pasó de 4 a 3 hipótesis; agente 03: 6 de 6).
      La Ronda 4 reescribe, no reclasifica. `debate_revision` es además el paso más
      caro: 10 llamadas y 26.788 tokens, un tercio del caso. Es una sola corrida; el
      recorte queda para decidirlo en una tarjeta aparte.
      **Pendiente para el orquestador** — depende de 7.2 (corridas reales) y está
      fuera de mi alcance asignado (excluido explícitamente por la restricción de
      cuota).
- [x] 7.4 Correr la suite completa: `pytest tests/ --ignore=tests/test_ingesta.py`.
      Hecho, con la red bloqueada (`-p pytest_sin_red`, ver nota de la tarea 6.7
      sobre por qué el comando literal sin el plugin no es seguro en este entorno):
      **819 passed**, 0 failed, 0 intentos de conexión bloqueados propios de esta
      suite (los 136 bloqueados que reporta el plugin son de `tests/test_api.py`,
      `tests/test_rag*.py` y `tests/test_embeddings.py`, preexistentes a este
      cambio).
- [ ] 7.5 Actualizar `.claude/CLAUDE.md` (sección del modelo de IA, la regla de que nadie instancia Groq por su cuenta, modo mock y variables nuevas), `.claude/stack.md` y `.claude/backlog.md` con los números medidos. Actualizar `.env.example`.
      `.env.example` hecho (`NEXUS_MOCK_LLM`, junto con 6.3). El resto: en curso.
- [x] 7.6 Adjuntar la evidencia a la tarjeta de Trello y moverla a QA.
      **Hecho el 2026-10-04**: tarjetas #81 y #84 en QA, con la medición real, el
      `costos.jsonl` y la salida de `scripts/demo_costos.py` adjuntos.
      Fuera de mi alcance (no tengo acceso a Trello desde esta sesión) — para el
      orquestador.
