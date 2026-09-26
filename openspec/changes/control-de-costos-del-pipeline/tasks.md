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

- [ ] 4.1 Crear el mapa `tarea → (modelo, techo)` en un módulo de configuración, de modo que se pueda revisar qué usa cada llamada sin recorrer los agentes (D6). Verificar que todos los sitios de llamada lo consultan.
- [ ] 4.2 Asignar el techo de cada tarea con holgura sobre su salida esperada, reemplazando el 4096 fijo. Verificar corriendo el caso de prueba y comprobando que **ninguna** respuesta quedó truncada por alcanzar su techo (`finish_reason`).
- [ ] 4.3 Registrar en la telemetría cuando una respuesta se corta por techo, para detectar un techo mal puesto. Verificar con un test de techo deliberadamente bajo.

## 5. Modelo por tarea

- [ ] 5.1 Mover la **agrupación del Árbitro** a `GROQ_FAST`. Su salida son índices validados por `consensus.normalize_partition()`. Verificar que `tests/test_agent_04_arbiter.py` sigue verde.
- [ ] 5.2 Mover la **planificación de términos del Agente 05** a `GROQ_FAST`. Verificar con `tests/test_agent_05_trials.py`.
- [ ] 5.3 Mover el **etiquetado de compatibilidad del Agente 05** a `GROQ_FAST`. Verificar con `tests/test_agent_05_trials.py`.
- [ ] 5.4 **Medir antes de dar por buena la decisión** (D6, y el riesgo del design): correr el caso de prueba con las tres tareas en `GROQ_MAIN` y después en `GROQ_FAST`, y comparar el agrupamiento resultante, los términos planificados y las etiquetas de compatibilidad. Registrar cuántas veces la salida del modelo rápido cayó en una validación. Si el agrupamiento empeora, esa tarea vuelve a `GROQ_MAIN` y se deja constancia.
- [ ] 5.5 Verificar el inventario: ninguna tarea que produzca hipótesis, críticas, revisiones, veredictos o la síntesis PICO usa el modelo rápido. Test que recorre el mapa de configuración.

## 6. Modo mock del pipeline

- [ ] 6.1 Implementar el modo mock en la función compartida de 1.1, devolviendo respuestas grabadas que atraviesan el mismo parseo y las mismas validaciones que una respuesta real (D7). Verificar con `tests/test_mock_pipeline.py`.
- [ ] 6.2 Generar las respuestas grabadas desde una corrida real del caso de prueba, para que se parezcan a lo que el modelo devuelve de verdad.
- [ ] 6.3 Activación explícita por variable de entorno, **apagada por defecto** y nunca por inferencia: si falta `GROQ_API_KEY` y el modo mock no está activo, el análisis falla con un error claro. Verificar con dos tests, uno por cada caso.
- [ ] 6.4 Marcar el reporte producido en modo mock, y mostrarlo en el frontend y en el PDF con la misma visibilidad que la advertencia del consenso de IA. Verificar con `tests/test_pdf_exporter.py` sobre el texto extraído, y con `npm run build` más una captura de la vista.
- [ ] 6.5 Verificar el determinismo: dos análisis del mismo texto en modo mock producen el mismo resultado.
- [ ] 6.6 Verificar que el modo mock **ejercita** el flujo: introducir un defecto en el parseo de la respuesta del modelo y comprobar que el modo mock lo manifiesta en vez de devolver un reporte correcto.
- [ ] 6.7 Confirmar que un análisis completo en modo mock no hace ninguna llamada de red, con `scripts/pytest_sin_red.py` (el mismo instrumento de la tarjeta #75).

## 7. Evidencia y cierre

- [ ] 7.1 Crear `scripts/demo_costos.py` que muestre entrada → salida: el desglose de tokens por agente de un análisis, el costo estimado con Groq y el que tendría con los modelos de la arquitectura de destino. Guarda artefactos en `output/demo_costos/`.
- [ ] 7.2 Correr el caso de prueba y registrar los **números medidos**: tokens por agente, total por caso y cuántos casos entran en la cuota diaria. Es el insumo del capítulo de viabilidad de la tesis.
- [ ] 7.3 Con la telemetría ya instalada, medir cuánto cambia cada agente entre la Ronda 3 y la Ronda 4 del debate, usando los `debate_rounds` de corridas reales. **No implementar el recorte**: dejar el dato en una tarjeta nueva para decidirlo con evidencia.
- [ ] 7.4 Correr la suite completa: `pytest tests/ --ignore=tests/test_ingesta.py`.
- [ ] 7.5 Actualizar `.claude/CLAUDE.md` (sección del modelo de IA, la regla de que nadie instancia Groq por su cuenta, modo mock y variables nuevas), `.claude/stack.md` y `.claude/backlog.md` con los números medidos. Actualizar `.env.example`.
- [ ] 7.6 Adjuntar la evidencia a la tarjeta de Trello y moverla a QA.
