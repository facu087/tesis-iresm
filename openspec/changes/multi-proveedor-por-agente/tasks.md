# Tasks

## 1. Dependencias

- [x] 1.1 En `backend/requirements.txt`, actualizar `anthropic` y `openai` a las versiones vigentes y reemplazar `google-generativeai` por `google-genai` (design D3), con versiones fijadas contra la documentación de cada SDK. Verificar con `pip install -r backend/requirements.txt` en el `.venv` y con `pytest tests/` sin regresiones antes de tocar código.

## 2. Mapa por agente y activación

- [x] 2.1 En `backend/agents/model_tasks.py`, agregar `AGENT_PROVIDERS` (01/04/06 → Anthropic `claude-opus-5-5`, 02 → OpenAI `gpt-4o`, 03 → Google Gemini Pro) con su techo (D4), la lectura de `NEXUS_PROVEEDORES` (`groq` por defecto, `destino`, cualquier otro valor avisa por stderr y queda en `groq`, D2) y las variables opcionales `NEXUS_MODELO_ANTHROPIC`/`_OPENAI`/`_GOOGLE`. Verificar en `tests/test_proveedor_por_agente.py` el escenario "Valor de activación no reconocido", que el Agente 05 y `agent_id=None` no tienen proveedor asignado y que el mapa se lee en un solo lugar ("Revisar qué proveedor usa cada agente").

## 3. Adaptadores y respaldo en `call_provider()`

- [x] 3.1 En `backend/agents/base_agent.py`, agregar un adaptador por proveedor (D3) con import diferido del SDK: Anthropic sin `temperature`, con `effort: "medium"`, streaming y `stop_reason: "refusal"` tratado como falla (D4); OpenAI y Google con su API vigente; timeout de 120 s por llamada (D5). Verificar en `tests/test_proveedor_por_agente.py`, con los clientes de los SDK reemplazados por dobles y sin red, que cada adaptador arma el pedido esperado y devuelve texto, tokens y truncamiento, y que Anthropic no recibe `temperature`.
- [x] 3.2 En `call_provider()`, resolver el proveedor por `agent_id` solo con `destino` activo, y repetir la llamada en Groq con el modelo y techo de `TASK_BUDGETS` si falta la clave o el adaptador falla (D6). El aviso por stderr sale una vez por análisis, proveedor y motivo, con el tipo de la excepción y nunca su mensaje. Verificar en `tests/test_proveedor_por_agente.py` los escenarios "Llamada de un agente con proveedor asignado", "Debate con tres proveedores", "Síntesis PICO…", "Agente 05…", "Sin activar, con claves presentes" (ninguna llamada al doble de Anthropic), "Falta la clave de Google", "Ninguna clave de destino", "Anthropic no responde", "Clave inválida", "Aviso de falla del proveedor" (el mensaje de la excepción no aparece en stderr) y "Misma tarea, distinto agente"; y que con `groq` lo que llega al cliente de Groq es idéntico a hoy.
- [x] 3.3 Extender el test que verifica que `call_provider()` es el único lugar que instancia un cliente de proveedor (`grep` de `Groq(api_key`) a los cuatro SDK. Verificar que pasa y que falla si se agrega un cliente fuera de `base_agent.py`.
- [x] 3.4 Verificar en `tests/test_proveedor_por_agente.py` el escenario "Modo mock con la arquitectura de destino activa": con `NEXUS_MOCK_LLM=1` y `destino`, ningún doble de SDK recibe llamadas y las respuestas son las grabadas.

## 4. Telemetría y tarifas

- [x] 4.1 En `backend/telemetry/usage.py`, agregar `proveedor`, `respaldo` y `motivo_respaldo` a cada llamada registrada, y el resumen por agente que usará el reporte (D7). Una entrada vieja sin esos campos se lee como Groq. Verificar en `tests/test_telemetria.py` (o el test vigente de telemetría) el escenario "Llamada de respaldo" y que un `costos.jsonl` anterior se sigue recalculando.
- [x] 4.2 En `backend/telemetry/pricing.py`, agregar las tarifas de `claude-opus-5-5`, `gpt-4o` y el modelo de Gemini elegido, con la fecha en que se tomaron (D9), revisadas contra las páginas de precios. Verificar el escenario "Costo real de la arquitectura de destino" con un registro sintético.

## 5. Grabación y modo mock

- [x] 5.1 En `backend/mock/recorder.py` y `backend/mock/responses.py`, guardar y reproducir el proveedor y el modelo de cada respuesta (D8); una grabación sin esos campos se reproduce como Groq. Verificar con un test que una grabación con `proveedor: "anthropic"` produce en la telemetría del modo mock ese proveedor, y que `grabadas.json` actual sigue cargando sin cambios.

## 6. Reporte, vista y PDF

- [x] 6.1 Agregar `metadata.proveedores` (opcional) al schema del reporte en `backend/api/schemas.py`, llenarlo en `api/router.py` desde el resumen de la telemetría al cerrar el análisis, y mostrarlo en `pipeline/pdf_exporter.py`. Verificar en tests los escenarios "Corrida completa en la arquitectura de destino", "Corrida con respaldo" y "Reporte anterior a este cambio" (el PDF se genera sin la sección), y que el bloque solo contiene agente, proveedor, modelo y motivo.
- [x] 6.2 Mostrar los proveedores en la vista `/report` (`frontend/src/lib/types.ts` y `frontend/src/components/report/`), con el sistema visual de `.landing` y los dos temas, omitiendo la sección si el campo falta. Verificar con un test de Vitest para los dos casos y con `npm run lint` y `tsc --noEmit`.

## 7. Evidencia y documentación

- [x] 7.1 Crear `scripts/demo_multi_proveedor.py`, sin red ni cuota: con los SDK reemplazados por dobles, muestra entrada → salida para cuatro casos (todo en `groq`; `destino` con las tres claves; `destino` sin la clave de Google; Anthropic fallando), con qué proveedor respondió cada agente, los avisos de stderr y el bloque `proveedores` del reporte. Guarda `resultado.txt` y `resumen.json` en `output/demo_multi_proveedor/` y sale con código 1 si algún caso no da lo esperado. Verificar corriéndolo.
- [ ] 7.2 Documentar `NEXUS_PROVEEDORES`, las claves y las variables de modelo en `docs/instalacion-y-despliegue.md` y `.env.example`, la arquitectura en `docs/arquitectura.md`, y que los datos anonimizados también van a esos proveedores. Verificar releyendo las secciones tocadas.

## 8. Cierre

- [x] 8.1 Correr la suite completa (`pytest tests/`) y en el frontend `npm run lint`, `tsc --noEmit` y `npm test`. Verificar que pasan, salvo los tests de Tesseract si el binario no está en la máquina local.
- [x] 8.2 Actualizar `.claude/CLAUDE.md` (sección "Modelo de IA actual", estructura de carpetas, lista de demos, estado del Sprint 5) y `.claude/backlog.md`. Verificar releyendo las secciones tocadas.

## Workflow follow-up

- Con las claves cargadas: corrida real con `NEXUS_PROVEEDORES=destino scripts/medir_costos.py --grabar`, regenerar `grabadas.json` y evaluar el reporte con `scripts/evaluar_reporte.py`.
- Archivar el cambio después del merge.
