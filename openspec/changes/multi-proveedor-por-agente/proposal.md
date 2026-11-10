# Proposal

## Why

La arquitectura de la tesis asigna un modelo distinto a cada agente: Claude Opus a los
Agentes 01, 04 y 06, GPT-4o al 02 y Gemini Pro al 03. Hoy todos corren en Groq
`gpt-oss`, como proveedor temporal. Para la muestra del proyecto hace falta que el
sistema pueda correr con esa arquitectura, sin que la falta de una clave o la caída
de un proveedor deje el análisis roto.

## What Changes

- Cada agente puede usar el proveedor y el modelo que le asigna la arquitectura de
  destino. La asignación vive en un solo mapa, junto al de tareas.
- La arquitectura de destino se activa con una variable de entorno explícita
  (`NEXUS_PROVEEDORES=destino`). Sin ella, el sistema se comporta exactamente como
  hoy: todo en Groq.
- Respaldo por agente: si falta la clave de un proveedor, o su llamada falla después
  de los reintentos, esa llamada se hace en Groq con el modelo de hoy y el análisis
  sigue.
- El reporte informa qué proveedor y qué modelo respondió por cada agente, incluido
  cuándo se usó el respaldo. Una muestra que dice "Claude" tiene que poder probar que
  respondió Claude.
- La telemetría registra el proveedor de cada llamada y si fue un respaldo. La tabla
  de tarifas suma los modelos de destino con su precio vigente.
- `call_provider()` sigue siendo el único punto que habla con un proveedor: suma los
  clientes de Anthropic, OpenAI y Google adentro de esa función.
- Sin cambios: el modo mock, las tareas que no son de un agente (PICO y
  biomarcadores) y el Agente 05, que no tiene un modelo asignado en la arquitectura y
  sigue en Groq.

## Capabilities

### New Capabilities
- `proveedor-por-agente`: qué proveedor y qué modelo usa cada agente, cómo se activa
  la arquitectura de destino, el respaldo en Groq y cómo el reporte informa quién
  respondió.

### Modified Capabilities
- `presupuesto-por-tarea`: el modelo de una llamada pasa a depender de la tarea **y**
  del agente; la configuración sigue en un solo lugar y el proveedor sigue eligiéndose
  en un único punto.
- `telemetria-de-costos`: cada llamada registra además el proveedor y si fue un
  respaldo; la tabla de tarifas incluye los modelos de destino.

## Impact

- Código: `backend/agents/base_agent.py` (`call_provider()`),
  `backend/agents/model_tasks.py` (mapa por agente), `backend/telemetry/usage.py` y
  `pricing.py`, `backend/api/schemas.py` y `pipeline/report_builder.py` (metadato de
  proveedores), `pipeline/pdf_exporter.py` y la vista `/report` (mostrarlo).
- Dependencias: los SDK de Anthropic, OpenAI y Google en `backend/requirements.txt`.
  `anthropic` y `openai` ya figuran con versiones viejas; el de Google cambia de
  paquete. Es un cambio de dependencias: lo revisa un verificador independiente.
- Configuración: `NEXUS_PROVEEDORES`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GOOGLE_API_KEY` (ya listadas en `.env.example`, hoy sin uso) y una variable opcional
  por proveedor para cambiar el modelo.
- Costo: con la arquitectura de destino activa, cada análisis tiene costo real
  (estimado en menos de un dólar por caso). Sin activarla, sigue siendo cero.
- Documentación: `CLAUDE.md`, `docs/arquitectura.md`, `docs/instalacion-y-despliegue.md`.
