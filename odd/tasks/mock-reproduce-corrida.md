# El modo mock reproduce la corrida grabada completa

Rama: `feature/s4-mock-reproduce-corrida` (base `develop`, `3f5a02c`).

## Objetivo

Que el modo mock pueda reproducir todas las respuestas de una corrida real, cada una para
el agente y la llamada que la produjo, en vez de una sola respuesta por tarea.

## Problema

`backend/mock/grabadas.json` guarda una respuesta por tarea (la primera por `seq`) y
`get_mock_response(task)` devuelve siempre esa. En el debate los tres agentes reciben la
misma crítica, la misma revisión y la misma recitación. Medido en el ensayo del 2026-10-06
sobre el caso base: las 10 hipótesis de consenso eran 5 textos repetidos dos veces, casi
todas atribuidas al Especialista Genómica, y las notas del Árbitro no correspondían a su
hipótesis. Sirve para ejercitar el flujo, no para mostrar un reporte.

## Alcance

- Formato de `grabadas.json`: una tarea puede tener varias grabaciones, cada una con su
  `agent_id` y su `seq`. El formato actual (una entrada por tarea) sigue siendo válido.
- Selección: para una llamada de la tarea T hecha por el agente A, la n-ésima grabación de
  (T, A) en orden de `seq`, donde n es cuántas veces (T, A) ya se pidió en el análisis en
  curso. Si no quedan, la última de (T, A); si A no tiene ninguna, la primera de T.
- El conteo es por análisis: dos análisis del mismo texto dan el mismo resultado
  (`modo-mock-pipeline`, Requirement: Resultado determinista).
- Herramienta para generar `grabadas.json` con todas las entradas a partir del
  `grabacion.json` que deja `scripts/medir_costos.py --grabar`.
- Fuera de alcance: regrabar (necesita cuota de Groq), prompts, parseo, y cualquier cambio
  de comportamiento con el `grabadas.json` actual.

## Restricciones

- Con el `grabadas.json` actual el resultado del modo mock no cambia.
- Toda grabación que se use tiene que atravesar el parseo real sin descartarse
  (`tests/test_mock_responses.py`), no solo la primera de cada tarea.
- Ningún test llama al proveedor ni a la red.
- La operación real (sin modo mock) no lee el archivo ni cambia.

## Tareas

- [x] **T1 — Selección por agente y por llamada** · ruta: delegada (un escritor).
- [x] **T2 — Conteo por análisis, abierto y cerrado donde se abre la telemetría** · misma
  delegación.
- [x] **T3 — Generador de `grabadas.json` desde `grabacion.json`** · misma delegación.

## Criterios de aceptación

- Con dos grabaciones de una tarea para agentes distintos, cada agente recibe la suya.
- Con dos grabaciones de una tarea para el mismo agente, la primera llamada recibe la
  primera y la segunda la segunda; una tercera recibe la última.
- Dos análisis seguidos reciben la misma secuencia.
- Sin análisis abierto, se comporta como hoy (primera grabación que corresponda).
- La suite pasa con el `grabadas.json` actual sin modificarlo.

## Verificación

- `pytest tests/test_mock_responses.py tests/test_mock_pipeline.py tests/test_recorder.py tests/test_api.py -q`
- `pytest tests -q` (en Windows fallan 4 tests ajenos: tres de `tests/test_ingesta.py` por
  Tesseract y `test_hermetico_sin_red_analisis_completo_en_modo_mock`).

## Progreso

Las tres tareas quedaron hechas el 2026-10-06 por un escritor delegado, en un solo commit.

- **RED** observado antes de implementar: `tests/test_regenerar_mock.py` no se podía importar
  y en los otros cuatro archivos fallaban 29 tests y 22 daban error.
- **GREEN**: los seis archivos de test del modo mock y la API, 219 pasan y falla 1, el test de
  hermeticidad ya conocido en Windows (corrido por el escritor y vuelto a correr por el
  orquestador). Su comando interno, corrido a mano, pasa: 26 tests y 0 conexiones bloqueadas.
- Suite completa en Windows: 1330 pasan y 4 fallan, los cuatro ajenos ya conocidos.
- `backend/mock/grabadas.json` no cambió.

Determinismo, revisado tarea por tarea: ningún par (tarea, agente) se llama en paralelo.
`debate_revision` es la única tarea que un mismo agente llama dos veces (Rondas 3 y 4), y las
rondas se esperan una después de la otra (`backend/pipeline/debate.py`). Las llamadas llegan
desde threads (`asyncio.to_thread`), por eso el contador tiene un lock.

Decisiones que el diseño no cubría:
- La sesión se abre siempre en el router y en el script, no solo en modo mock: copia el patrón
  de la telemetría, no lee el archivo y fuera del modo mock nadie la consulta.
- La forma de lista es más estricta que la de objeto: cada entrada necesita `agent_id` y un
  `seq` entero y único dentro de la tarea.
- El generador escribe siempre la forma de lista y conserva las respuestas truncadas, avisando
  cuántas son.
- El chequeo de recitación asume un total de 3 hipótesis para cada entrada: una grabación que
  numere solo hipótesis por encima de 3 lo haría fallar y habría que ajustar el total.

Sin verificar:
- El beneficio sobre una corrida real: no hay un `grabacion.json` completo en esta máquina, así
  que los caminos con varias entradas se probaron solo con datos sintéticos.
- `scripts/regenerar_mock.py` nunca se corrió contra una grabación real.

Pendiente fuera de este cambio: `orchestrator.run_pipeline` (síncrono) y los scripts de demo no
abren sesión, así que con un archivo de varias entradas recibirían la primera revisión en las
Rondas 3 y 4.

Revisión nativa (commit `23ee391`, riesgo medio, exigida por superar el presupuesto de líneas):
consentida por Matías, una lente (fiabilidad), **aprobada** y reconocida el 2026-10-06. Dejó
tres observaciones no bloqueantes:
- **Escritura no atómica del generador** (`backend/mock/regenerar.py`). **Arreglada** en un
  commit aparte: escribe en un archivo vecino y reemplaza; un fallo de escritura levanta
  `DestinoNoEscribible`, deja el destino como estaba y el script sale con código 2. Tres tests
  nuevos, que fallaban antes del arreglo.
- **Cobertura de los chequeos de parseo** (`tests/test_mock_responses.py`). **Abierta**: los
  cuatro chequeos que llegan a la grabación por `call_provider` (biomarcadores, agrupación,
  planificación de términos y compatibilidad) recorren las entradas pero no afirman cuál
  recibió cada llamada. Con un archivo de varias entradas, alguna podría quedar sin parsear y
  el test pasar igual. Mirarlo al regenerar el archivo.
- **El invariante de orden no se detecta, solo se documenta** (`backend/mock/responses.py`).
  **Abierta**: nada avisa si algún día un par (tarea, agente) se llama en paralelo.

Siguiente paso, con cuota de Groq:
1. `python scripts/medir_costos.py --grabar` (deja `output/medicion_costos/grabacion.json`).
2. `python scripts/regenerar_mock.py output/medicion_costos/grabacion.json backend/mock/grabadas.json`
3. `pytest tests/test_mock_responses.py -q` y un análisis en modo mock para mirar el reporte.
