## Context

Ver `proposal.md` — Why. Lo que importa para el diseño es el estado del código:

- `BaseAgent._call_llm()` (`base_agent.py:137-173`) es el punto por donde pasan
  las llamadas de **los agentes**: 10 llamadores entrantes, verificado en el
  grafo del código. Instancia `Groq` directamente y usa `max_tokens=4096` y
  `temperature=0.3` fijos. Ya reintenta ante 429 con backoff `[8, 20, 40]`.
- **Dos módulos se lo saltean**: `pipeline/pico.py:93` (`max_tokens=2048`) e
  `ingestion/biomarker_extractor.py:156` (`max_tokens=1024`). Cada uno arma su
  propio cliente y su propio manejo de errores.
- `GROQ_MAIN` y `GROQ_FAST` están definidos en `base_agent.py`; `GROQ_FAST` no
  lo usa nadie.
- `agent_05_trials.py` ya separa sus dos llamadas en métodos distintos
  (`_plan_terms`, `_evaluate`), y `agent_04_arbiter.py` también (`_group`,
  `_write_verdicts`). Eso hace que "modelo por tarea" sea un cambio local.
- El router (`api/router.py`) es el único lugar que conoce el ciclo de vida de un
  análisis completo, así que es donde empieza y termina el registro.
- Medición del 2026-09-22 sobre el caso de prueba: 456 s, 18 fuentes, arbitraje
  completo sin fallbacks.

## Goals / Non-Goals

**Goals:**

- Que el total reportado sea el consumo real: si una llamada no se cuenta, el
  número miente y no sirve ni para planificar cuota ni para la tesis.
- Que la telemetría sea imposible de confundir con un canal de datos clínicos.
- Que bajar una tarea de modelo sea reversible y medible, tarea por tarea.
- Que el modo mock ejercite el código de verdad, no lo puentee.

**Non-Goals:**

- No se toca la lógica clínica: ni cómo se generan hipótesis, ni cómo se
  clasifican, ni cómo se ordenan.
- No se agrega un backend de métricas (Prometheus, OpenTelemetry). Un archivo
  local alcanza para el volumen de este proyecto y no suma dependencias.
- No se implementa control de presupuesto activo (cortar un análisis a mitad por
  exceder un tope). Primero medir; decidir después si hace falta.
- No se persiste nada entre sesiones más allá del archivo local de consumo, que
  es descartable y gitignoreado.

## Decisions

### D1 — Un único punto de llamada al proveedor, y los dos módulos sueltos se alinean

**Decisión.** Extraer la llamada al proveedor a una función compartida que
reciba el system prompt, el mensaje, el modelo, el techo de tokens y una
etiqueta del paso que la originó. `BaseAgent._call_llm()` pasa a delegar en
ella, y `pico.py` y `biomarker_extractor.py` también.

**Por qué.** Es la condición para que el requisito "toda llamada queda
contabilizada" sea verdad y no una aspiración. Instrumentar solo
`_call_llm()` dejaría fuera dos llamadas por caso.

Hay dos beneficios que no son de este cambio pero vienen gratis: los dos módulos
quedan alineados con la regla del proyecto, y el swap de proveedor —que hoy
habría que hacer en tres lugares— vuelve a ser uno.

**Alternativa descartada.** Instrumentar los tres lugares por separado:
triplica el código de registro y deja el problema del swap intacto.

### D2 — El registro vive en un contexto por análisis, no en un global

**Decisión.** El router abre un registro al empezar el análisis y lo cierra al
terminar. Las llamadas escriben en el registro activo.

**Por qué.** Un acumulador global mezclaría análisis concurrentes: FastAPI
atiende pedidos en paralelo y el desglose por caso dejaría de significar nada.
Además un contexto explícito se puede testear sin estado compartido.

**Implementación.** `contextvars`, que es lo que corresponde con `asyncio`: el
contexto se propaga a las corrutinas hijas y a los `asyncio.to_thread()` que usa
el pipeline. Una variable de módulo no sobreviviría a la concurrencia.

**Sin registro activo.** Una llamada fuera de un análisis —un script de demo, un
test— no falla: se ignora el registro. La telemetría nunca es condición para que
algo funcione.

### D3 — Identificador aleatorio por corrida, no hash del caso

**Decisión.** El id de un análisis es aleatorio, generado al abrir el registro.

**Por qué.** Un hash del texto clínico sería cómodo para deduplicar corridas del
mismo caso, pero es un **identificador pseudónimo derivado de datos del
paciente**: permitiría vincular dos análisis de la misma persona a través de un
archivo que no está pensado como dato sensible. La regla del proyecto es no
persistir datos clínicos más allá de la sesión, y un derivado estable es
persistencia. El costo es perder el dedupe, que no vale eso.

### D4 — JSONL, una línea por análisis

**Decisión.** `output/costos.jsonl`, append de una línea JSON por análisis.

**Por qué.** Se acumula sin releer ni reescribir el archivo, sobrevive a una
corrida interrumpida sin corromperse, y se promedia con tres líneas de Python
para el capítulo de la tesis. Un JSON único habría que leerlo y reescribirlo
entero en cada corrida.

`output/` ya está gitignoreada.

### D5 — La tabla de tarifas es configuración, no código

**Decisión.** Precios por modelo en un archivo de configuración, con los valores
de Groq (cero) por defecto y los de la arquitectura de destino comentados.

**Por qué.** El valor real de la tabla no es contar lo que Groq no cobra: es
poder responder *"¿cuánto costaría este mismo caso con Claude Opus?"*
recalculando sobre registros ya guardados, sin correr nada. Eso es exactamente
el insumo del capítulo de viabilidad.

**Modelo sin tarifa.** Costo cero y una marca, nunca una excepción: que falte un
precio no puede tumbar un análisis clínico.

### D6 — Techo y modelo viajan con la llamada, declarados en un solo mapa

**Decisión.** Una tabla `tarea → (modelo, techo)` en un módulo de configuración.
Cada sitio de llamada nombra su tarea.

**Por qué.** Si el techo y el modelo quedan hardcodeados en cada método, revisar
"qué usa cada cosa" obliga a recorrer todos los agentes, y ajustar la política
—por ejemplo, revertir una tarea al modelo grande— se vuelve una cacería.

**Qué baja a `GROQ_FAST`, y por qué solo eso.** Las tres tareas cuya salida ya
pasa por una validación determinista:

| Tarea | Qué devuelve | Quién valida |
|---|---|---|
| Agrupación del Árbitro | índices | `consensus.normalize_partition()` |
| Planificación de términos (Ag. 05) | términos en inglés | `trial_matching`, saneamiento |
| Compatibilidad (Ag. 05) | etiqueta + NCT ID | `trial_matching`, contra los NCT enviados |

En las tres, una respuesta peor del modelo chico cae en una validación que ya
existe y tiene fallback probado. No hay camino desde "el modelo respondió peor"
hasta "el reporte afirma algo incorrecto".

Todo lo demás —hipótesis, críticas, revisiones, veredictos, PICO— se queda en
`GROQ_MAIN`: ahí la calidad del modelo **es** la calidad del análisis.

### D7 — El modo mock intercepta en el punto de llamada, no en el router

**Decisión.** El modo mock devuelve respuestas grabadas desde la misma función
compartida de D1, no desde un endpoint alternativo.

**Por qué.** Es lo que hace que sirva: la respuesta grabada atraviesa el mismo
parseo, las mismas validaciones y los mismos fallbacks que una real. Un mock que
devuelva el `StructuredReport` ya armado no ejercita nada de lo que uno está
modificando, que es justo cuando se lo usa.

**Activación.** Variable de entorno, apagado por defecto, y **nunca por
inferencia**. Que falte `GROQ_API_KEY` tiene que fallar: caer a respuestas
grabadas en silencio es la forma de que alguien presente una demo creyendo que
analizó algo.

**Marca en el reporte.** El reporte de modo mock lo declara, y el frontend y el
PDF lo muestran. Es el mismo criterio que la advertencia del consenso de IA: el
lector tiene que poder distinguir lo producido de lo grabado.

## Risks / Trade-offs

- **El modelo rápido degrada una tarea sin que se note** → La guarda es que las
  tres tareas candidatas tienen validación determinista, pero una salida *válida
  y peor* (un agrupamiento que junta cosas distintas) pasaría la validación.
  Mitigación: la tarea 3 se mide comparando una corrida antes y después sobre el
  caso de prueba, y la decisión es reversible tarea por tarea. Si el
  agrupamiento empeora, esa tarea vuelve a `GROQ_MAIN` y las otras dos quedan.

- **Instrumentar toca `base_agent.py`, que es el corazón del sistema** → Un
  defecto ahí afecta a todos los agentes. Mitigación: la telemetría no puede
  hacer fallar una llamada (requisito explícito de la spec), y la refactorización
  de D1 se hace con la suite completa como red — hoy son 736 tests.

- **Colisión con el PR #19** → Toca `base_agent.py`, `agent_04_arbiter.py`,
  `agent_05_trials.py` y `router.py`. Mitigación: este cambio se implementa
  **después** de mergear #19. Anotado en tasks.md.

- **El modo mock se desactualiza** → Respuestas grabadas que ya no se parecen a
  lo que devuelve el modelo hacen que el pipeline "ande" en mock y falle en real.
  Mitigación: regenerar las respuestas desde una corrida real, y un test que
  verifique que atraviesan el parseo vigente.

- **Medir cambia lo medido** → El registro agrega latencia por llamada.
  Mitigación: es escritura en memoria durante el análisis y un solo append al
  cerrar; frente a llamadas de LLM de segundos, es ruido.

## Migration Plan

No hay datos que migrar ni contrato que romper: el `StructuredReport` no cambia.

Orden sugerido: punto de llamada compartido (D1) → telemetría sobre él →
tarifas → techos por tarea → modelo por tarea con su medición → modo mock. Cada
bloque deja la suite verde y se puede frenar ahí.

Rollback: revertir el merge. Como la telemetría no altera el reporte ni el
contrato, quitarla no deja rastro en los datos.

## Open Questions

- Dónde conviene guardar las respuestas grabadas del modo mock: un archivo por
  agente o uno solo con todas. Afecta a la ergonomía de regenerarlas, no al
  contrato ni a las specs; se decide al implementar esa tarea.
- Si el resumen por consola conviene por análisis o también acumulado por
  sesión. Es presentación; se ve con el primer uso real.
