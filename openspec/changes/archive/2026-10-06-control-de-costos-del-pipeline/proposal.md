## Why

El pipeline hace **17 a 20 llamadas al LLM por caso** y no existe ninguna
contabilidad de cuántos tokens consume. El 2026-09-21 eso dejó de ser un dato
curioso y pasó a bloquear el trabajo: **tres corridas del caso de prueba
agotaron los 200.000 tokens diarios** del tier gratuito de Groq
(197.800/200.000), el debate empezó a caerse desde la Ronda 2 y hubo que
esperar al día siguiente para poder medir. Nadie lo vio venir porque no hay
forma de verlo venir.

El problema se agranda en lo que sigue. El Sprint 5 es validación clínica:
correr el pipeline sobre **varios** casos, varias veces. Y la arquitectura de
destino reemplaza Groq por Claude Opus, GPT-4o y Gemini Pro, donde cada token
se factura. Llegar a ese punto sin saber qué consume cada agente es llegar a
ciegas.

Hay además una razón de tesis: la **viabilidad económica** del sistema es un
capítulo que hoy no se puede escribir con datos propios.

Tres hallazgos concretos que salieron de revisar el código:

- **`max_tokens=4096` es fijo para toda llamada** (`base_agent.py:158`), sin
  importar la tarea. La agrupación del Árbitro devuelve
  `{"groups": [[1,3],[2]]}` —unas decenas de tokens— y reserva lo mismo que un
  razonamiento clínico completo.
- **`GROQ_FAST` existe, se exporta en `agents/__init__.py` y no lo usa nadie.**
  Todos los agentes corren sobre `GROQ_MAIN`, incluidas las tareas mecánicas.
- **Dos módulos instancian el cliente de Groq por su cuenta**, salteándose
  `BaseAgent._call_llm()`: `pipeline/pico.py:93` y
  `ingestion/biomarker_extractor.py:156`. Eso contradice la regla del proyecto
  ("nunca instancia el cliente de Groq por su cuenta"), multiplica el trabajo
  del swap de proveedor, y —para este cambio— significa que instrumentar un
  solo punto **dejaría esas llamadas sin contabilizar**.

## What Changes

- **Telemetría de tokens por agente y por caso.** Cada llamada al LLM registra
  el modelo usado, los tokens de entrada y de salida, la latencia y el paso del
  pipeline que la originó. Al terminar el análisis se escribe **una línea JSON
  por caso** en un archivo local (`output/costos.jsonl`, gitignoreado) con el
  total y el desglose por agente, más un resumen por stderr.
- **Ninguna llamada queda sin contar.** `pipeline/pico.py` y
  `ingestion/biomarker_extractor.py` pasan a usar el mismo punto de llamada que
  los agentes, en vez de instanciar Groq por su cuenta. Además de cerrar el
  agujero de la telemetría, alinea esos dos módulos con la regla del proyecto y
  deja el swap de proveedor en un solo lugar.
- **La telemetría no contiene datos clínicos.** Se registran conteos,
  identificadores de agente y nombres de modelo. **Nunca** el prompt, la
  respuesta del modelo ni fragmento alguno del caso. El identificador de caso es
  un id aleatorio por corrida, no un hash del texto clínico: no debe poder
  usarse para vincular dos análisis del mismo paciente.
- **Estimación de costo con tarifas configurables.** Una tabla de precios por
  modelo (en `.env` o un archivo de configuración) convierte tokens a dólares.
  Con Groq gratuito el costo es cero y se informa como tal; el valor de la tabla
  es poder responder "¿cuánto costaría esto con Claude Opus?" sin correr nada.
- **`max_tokens` por tarea**, en vez del 4096 fijo. Cada llamada declara el
  techo que su salida necesita. Es un tope, no un objetivo: no cambia lo que el
  modelo produce mientras no lo trunque.
- **Modelo por tarea**: las tareas mecánicas, con salida acotada y **ya validada
  deterministicamente por código**, pasan a `GROQ_FAST`. Son tres: la agrupación
  del Árbitro (devuelve índices que valida `consensus.normalize_partition()`),
  la planificación de términos y el etiquetado de compatibilidad del Agente 05
  (validados en `pipeline/trial_matching.py`). El razonamiento clínico, las
  críticas del debate, las revisiones, los veredictos del Árbitro y la síntesis
  PICO **siguen en `GROQ_MAIN`**.
- **Modo mock del pipeline completo**, con el mismo criterio que el `--sin-red`
  de los scripts de demo: `POST /api/analyze` responde con outputs grabados,
  deterministas y sin tocar la red. Para iterar en desarrollo sin gastar cuota.

## Capabilities

### New Capabilities
- `telemetria-de-costos`: qué se mide en cada llamada al LLM, la garantía de que
  **toda** llamada queda contabilizada, dónde se registra, qué **no** puede
  contener (datos clínicos), y el formato del resumen por caso.
- `presupuesto-por-tarea`: cómo se asigna el techo de `max_tokens` y el modelo a
  cada llamada, qué tareas pueden bajar a un modelo rápido y bajo qué condición
  (salida acotada y validada por código), y la garantía de que las tareas de
  razonamiento clínico no se degradan.
- `modo-mock-pipeline`: comportamiento del pipeline en modo de desarrollo sin
  LLM — qué devuelve, cómo se activa y cómo se distingue de una corrida real
  para que nadie confunda un reporte grabado con uno producido.

### Modified Capabilities
<!-- Ninguna. `clasificacion-evidencia-ebm` es la única spec vigente y no cambia:
     este cambio no toca cómo se clasifica ni se ordena una hipótesis. -->

## Impact

- **Código nuevo**: `backend/telemetry/usage.py` (registro y agregación),
  `backend/telemetry/pricing.py` (tarifas por modelo), `tests/test_telemetry.py`,
  `tests/test_mock_pipeline.py`, `scripts/demo_costos.py`.
- **Código modificado**: `backend/agents/base_agent.py` (instrumentar
  `_call_llm()`, `max_tokens` por llamada), `backend/pipeline/pico.py` e
  `backend/ingestion/biomarker_extractor.py` (dejar de instanciar Groq),
  `backend/agents/agent_04_arbiter.py` y `backend/agents/agent_05_trials.py`
  (modelo y techo por tarea), `backend/api/router.py` (abrir y cerrar el
  registro por caso, modo mock), `.env.example`, `.gitignore`.
- **Dependencias**: ninguna nueva. La respuesta de Groq ya trae `usage` con
  `prompt_tokens` y `completion_tokens`.
- **Contrato JSON**: **sin cambios.** La telemetría no viaja en el
  `StructuredReport`: es un dato de infraestructura y el reporte es un documento
  clínico. Decisión tomada explícitamente.
- **Riesgo sobre la calidad**: acotado a la tarea 3 (modelo por tarea). Las tres
  tareas candidatas tienen su salida validada por código, así que una respuesta
  peor del modelo chico se degrada a un fallback ya probado, no a un resultado
  incorrecto. Se mide comparando una corrida antes y después.
- **Cambios en paralelo**: el PR #19 (Agente 04) toca `base_agent.py`,
  `agent_04_arbiter.py`, `agent_05_trials.py` y `router.py`. **Este cambio se
  implementa después de que #19 esté mergeado.**
- **Documentación**: `.claude/CLAUDE.md` (sección del modelo de IA y la regla de
  `_call_llm()`), `.claude/backlog.md`, `.claude/stack.md`.

## Fuera de alcance

- **Recortar la Ronda 4 del debate.** Las Rondas 3 y 4 reciben las **mismas**
  críticas de la Ronda 2 (`debate.py:234` y `:237`), así que la 4 podría ser
  redundante y son 3 de las ~18 llamadas. Pero recortar rondas es lo único de
  esta lista que puede costar calidad de análisis, y la premisa es no perderla.
  Hay que **medir** primero, con los `debate_rounds` de corridas reales, cuánto
  cambia cada agente entre la Ronda 3 y la 4. Va en tarjeta aparte, y el dato
  para decidirlo sale de la telemetría que instala este cambio.
- **Batch API.** `POST /api/analyze` es interactivo: el usuario espera el
  reporte. Tendría sentido en el Sprint 5, para correr la validación sobre un
  lote de casos.
- **Prompt caching.** Es de la arquitectura de destino: Anthropic lo cobra más
  barato si el prefijo no cambia, y Groq funciona distinto. Se evalúa cuando se
  haga el swap de proveedor.
- **Límites de gasto en las consolas** de Anthropic, OpenAI y Google, y los
  programas de créditos académicos. Son trámites, no código.
