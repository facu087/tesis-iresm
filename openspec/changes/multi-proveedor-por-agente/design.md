# Design

## Context

Toda llamada al modelo pasa por `call_provider()` (`backend/agents/base_agent.py`), que
hoy instancia solo el cliente de Groq. Recibe `task`, `agent_id` y el modelo y techo que
`BaseAgent._call_llm()` resuelve en `model_tasks.TASK_BUDGETS` por tarea. Las tareas del
debate (`debate_critica`, `debate_revision`, `debate_recitacion`) las comparten los tres
agentes, así que la tarea sola no alcanza para elegir el proveedor. La telemetría
(`backend/telemetry/usage.py`) ya abre un registro por análisis y anota cada llamada con
su agente y modelo. Motivación: ver `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Que el proveedor se elija por agente sin que ningún agente cambie su código.
- Que el comportamiento por defecto sea idéntico al de hoy, byte a byte en lo que llega
  a Groq.
- Que una muestra pueda probar qué modelo respondió por cada agente, también al
  reproducir una corrida grabada.

**Non-Goals:**
- Comparar la calidad de los modelos entre sí: eso es una evaluación aparte.
- Asignar proveedor al Agente 05, a la síntesis PICO o a los biomarcadores.
- Ajustar los prompts a cada modelo. Si un modelo responde con otro formato, el parseo
  y los fallbacks de hoy se encargan; si falla seguido, se ajusta en otro cambio.

## Decisions

**D1. El mapa por agente vive en `model_tasks.py`, al lado de `TASK_BUDGETS`.** Un
`AGENT_PROVIDERS` con `agent_id → (proveedor, modelo, techo)`, consultado por
`call_provider()` solo si la arquitectura de destino está activa y la llamada trae un
`agent_id` del mapa. Así la regla "la configuración queda en un solo lugar" se cumple sin
tocar `_call_llm()` ni los agentes. *Alternativa descartada:* una tarea por agente
(`debate_critica_01`, …): multiplica el mapa por tres y obliga a cambiar el debate.

**D2. Activación con `NEXUS_PROVEEDORES`, valores `groq` (por defecto) y `destino`.**
Que la mera presencia de una clave active un proveedor pago es peligroso: `.env.example`
ya lista `ANTHROPIC_API_KEY` y una clave cargada para otra cosa empezaría a gastar sin
que nadie lo decida. Un valor desconocido avisa por stderr y queda en `groq`, como hace
`NEXUS_RAG_MIN_SCORE` con los valores inválidos.

**D3. Un adaptador por proveedor, adentro del mismo módulo que `call_provider()`.** Cada
uno recibe `system_prompt`, `user_message`, modelo y techo y devuelve
`(texto, tokens_entrada, tokens_salida, truncada)`. `call_provider()` sigue siendo el
único punto que importa un SDK de proveedor (el test que lo verifica se extiende a los
cuatro). SDK: `anthropic` y `openai` oficiales, y para Gemini el paquete actual de Google
(`google-genai`), que reemplaza a `google-generativeai`, deprecado. Las versiones se fijan
al implementar, contra la documentación vigente de cada SDK.

**D4. Particularidades de Claude Opus.** El modelo por defecto es `claude-opus-5-5`.
Razona siempre (no se puede desactivar) y el razonamiento cuenta dentro del techo de
salida, así que sus tareas usan un techo de 16.000 tokens en lugar de 4.096 y
`effort: "medium"` explícito. No admite `temperature`: el adaptador no la envía. Una
respuesta con `stop_reason: "refusal"` se trata como falla y va al respaldo (D6), en
lugar de usar el respaldo del lado del servidor: un solo mecanismo de respaldo, que
además queda registrado. Gemini Pro también razona: mismo criterio de techo. GPT-4o
conserva el techo de hoy.

**D5. Reintentos: los del SDK, con un tiempo máximo por llamada.** Los tres SDK
reintentan 429 y errores 5xx por su cuenta. Se usa ese reintento con un timeout por
llamada (120 s), para que un proveedor colgado no frene un pipeline de 8 minutos. El
backoff propio de 8/20/40 s queda solo para Groq, como hoy.

**D6. Respaldo por llamada, no por análisis.** Si falta la clave o la llamada falla
(error del SDK después de sus reintentos, timeout o rechazo), la misma llamada se repite
en Groq con el modelo y techo de `TASK_BUDGETS`. Por llamada y no "todo el agente pasa a
Groq": una caída momentánea no le cuesta al agente el resto del análisis. El aviso por
stderr se emite una vez por análisis, proveedor y motivo, con el tipo de la excepción y
nunca su mensaje.

**D7. El reporte se arma desde la telemetría.** El registro por análisis ya conoce cada
llamada. Se agregan `proveedor`, `respaldo` y `motivo_respaldo` a cada entrada, y al
cerrar el análisis el router resume por agente qué proveedor y modelo respondieron.
El resumen va a `StructuredReport.metadata.proveedores`, un campo opcional: un reporte
anterior lo trae nulo y la vista y el PDF omiten la sección. *Alternativa descartada:*
que cada agente devuelva qué modelo usó en su `AgentOutput`: toca los seis agentes y el
debate.

**D8. La grabación guarda proveedor y modelo, y el modo mock los reproduce.**
`backend/mock/recorder.py` agrega a cada respuesta grabada el proveedor y el modelo que
la produjeron, y el modo mock los anota en la telemetría al entregarla. Así, una corrida
real con la arquitectura de destino, grabada y reproducida en la muestra, muestra
"Claude Opus" donde respondió Claude, sin dejar de marcar el reporte como modo mock. Las
grabaciones viejas, sin esos campos, se reproducen como Groq.

**D9. Tarifas.** `pricing.py` suma `claude-opus-5-5` (US$4 / US$20 por millón),
`gpt-4o` (US$2,50 / US$10) y el modelo de Gemini elegido, con la fecha en que se
tomaron. Se revisan contra las páginas de precios al implementar.

## Risks / Trade-offs

- [El respaldo esconde que un proveedor no anda] → Queda en stderr, en la telemetría y,
  sobre todo, en el reporte, que es lo que se muestra.
- [Otro modelo, otro formato de respuesta: más JSON inválido] → El parseo y los
  fallbacks de hoy cubren JSON inválido. Se mide con una corrida real antes de la muestra.
- [El razonamiento de Opus y Gemini alarga la corrida y sube el costo] → Techo y
  `effort` explícitos (D4); la corrida grabada se mide con `scripts/medir_costos.py`.
- [Actualizar `anthropic` y `openai` puede romper otras dependencias] → Es el ítem de
  riesgo 5 (dependencias): CI completo y verificador independiente.
- [Los datos clínicos van a tres proveedores más] → Son los mismos datos que hoy van a
  Groq; la anonimización (PR #82 de GitHub) aplica antes de cualquier proveedor. Queda
  escrito en la documentación de despliegue.

## Migration Plan

Sin migración: desactivado por defecto. Para la muestra: cargar las claves, poner
`NEXUS_PROVEEDORES=destino`, hacer una corrida real con `scripts/medir_costos.py --grabar`
y regenerar las grabaciones del modo mock. Volver atrás es borrar la variable.

## Open Questions

- Identificador exacto del modelo Gemini Pro vigente: se elige al implementar contra la
  lista de modelos de Google y queda configurable con una variable por proveedor
  (`NEXUS_MODELO_GOOGLE`, y sus equivalentes para Anthropic y OpenAI).
