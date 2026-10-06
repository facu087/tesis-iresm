## 1. Tarea en el presupuesto de tokens

- [x] 1.1 Agregar `"agente06_sintesis": TaskBudget(GROQ_MAIN, 4096)` a `TASK_BUDGETS` en
  `backend/agents/model_tasks.py` y añadir `"agente06_sintesis"` a la lista
  `_CLINICAL_REASONING_TASKS` del test de inventario. Verificar con
  `pytest tests/test_model_tasks.py`.

## 2. Campo en el reporte

- [x] 2.1 Agregar `executive_summary: str | None = None` a `StructuredReport` en
  `backend/api/schemas.py`, después de `arbitration`, con el mismo comentario de
  retrocompatibilidad que los campos de Ag04 y Ag05. Verificar que
  `pytest tests/test_api.py tests/test_report_builder.py` sigue pasando sin tocar esos
  tests (el campo es aditivo y optional).

## 3. Agente 06 — SynthesizerAgent

- [x] 3.1 Crear `backend/agents/agent_06_synthesizer.py` con `SynthesizerAgent`
  (`AGENT_ID="06"`, `AGENT_NAME="Sintetizador"`, hereda de `BaseAgent`). El
  `SYSTEM_PROMPT` indica que el agente escribe un párrafo conciso (máximo 5 oraciones) en
  español para el médico, sin introducir datos que no estén en el reporte recibido y sin
  usar terminología diagnóstica definitiva. Verificar que el archivo importa sin errores:
  `python3 -c "from backend.agents.agent_06_synthesizer import SynthesizerAgent"`.

- [x] 3.2 Implementar `synthesize(self, structured_report: StructuredReport) -> str | None`
  en `SynthesizerAgent`. El método serializa el reporte a texto (hipótesis priorizadas +
  veredictos del Árbitro + ensayos + métricas de verificación), llama a `_call_llm()` con
  `task="agente06_sintesis"`, aplica la guarda anti-invención (ver 3.3) y devuelve el
  resumen o `None`. Verificar con los tests de 3.4.

- [x] 3.3 Implementar la guarda anti-invención como método privado
  `_check_invention(text, structured_report) -> str | None`. Extraer con regex:
  PMIDs (`\d{7,8}`), NCTs (`NCT\d{8}`), símbolos génicos
  (`\b[A-Z][A-Z0-9]{1,7}\b` excluyendo `_NON_GENE_TERMS` importado de
  `backend/ingestion/biomarker_extractor.py`). Verificar que cada token extraído
  aparece en las fuentes, ensayos o genes del reporte; si alguno falta, loggear el token
  infractor y devolver `None`. Verificar con los tests de 3.4.

- [x] 3.4 Crear `tests/test_agent_06_synthesizer.py` con `_call_llm` mockeado:
  - Resumen válido sin referencias externas → `executive_summary` no es `None`
  - LLM devuelve texto con PMID inventado → `None`
  - LLM devuelve texto con NCT inventado → `None`
  - LLM devuelve texto con gen inventado → `None`
  - LLM falla con excepción → `None` (no propaga)
  - Modo mock (`NEXUS_MOCK_LLM=1`) → devuelve la respuesta grabada sin llamar al proveedor
  - El módulo no importa `groq` directamente
  Verificar con `pytest tests/test_agent_06_synthesizer.py`.

- [x] 3.5 Exportar `SynthesizerAgent` en `backend/agents/__init__.py`. Verificar con
  `python3 -c "from backend.agents import SynthesizerAgent"`.

## 4. Integración en el router

- [x] 4.1 Agregar la función auxiliar `_synthesize_safe(structured_report)` en
  `backend/api/router.py` siguiendo el patrón de `_arbitrate_safe` y
  `_navigate_trials_safe`: instancia `SynthesizerAgent`, llama a `synthesize()`, atrapa
  toda excepción y devuelve `None` en lugar de propagar. Verificar que la función existe
  y que `pytest tests/test_api.py` sigue pasando.

- [x] 4.2 Insertar el paso 9 en `backend/api/router.py` (después de `build_export()`):
  ```python
  structured = build_export(...)
  structured.executive_summary = await asyncio.to_thread(_synthesize_safe_sync, structured)
  return structured
  ```
  o usar `await _synthesize_safe(structured)` si se implementa como corrutina. Verificar
  con `pytest tests/test_api.py` usando `client_medico_verificado` de `tests/conftest.py`
  y con el campo `executive_summary` presente (con valor `None` en mock sin tarea grabada).

## 5. Modo mock — respuesta grabada

- [x] 5.1 Añadir `"agente06_sintesis"` a la lista de tareas grabables en
  `scripts/medir_costos.py` (la lista que controla qué tareas se graban con `--grabar`).
  Verificar que `python3 scripts/medir_costos.py --mock --dry-run` no falla.

- [x] 5.2 Correr `python3 scripts/medir_costos.py --grabar` una vez contra Groq real para
  capturar la respuesta del Sintetizador. Agregar la clave `agente06_sintesis` resultante
  a `backend/mock/grabadas.json`. Verificar que `python3 scripts/medir_costos.py --mock`
  completa sin error y que el campo `executive_summary` del reporte no es `None`.
  _Resultado:_ grabado (seq 22, sin truncar) y aceptado por la guarda en la corrida real.
  En modo mock la guarda lo descarta porque el reporte mock no contiene SPTLC1/DNMT1
  (las grabadas guardan una respuesta por tarea): `executive_summary` queda `None` en mock.

## 6. Frontend y PDF

- [x] 6.1 Agregar el tipo `executive_summary?: string | null` a `StructuredReport` en
  `frontend/src/lib/types.ts`. Verificar con `npx tsc --noEmit` en `frontend/`.

- [x] 6.2 Mostrar el `executive_summary` en `frontend/src/app/report/page.tsx`: si no es
  `null` ni `undefined`, renderizar una sección "Resumen ejecutivo" antes de la lista de
  hipótesis. Si es `null`, no mostrar nada (sin placeholder). Verificar con
  `npm run build` en `frontend/` y viendo la sección en la vista de reporte con el mock
  activo.
  _Verificado (2026-10-06):_ `report/page.tsx` renderiza la sección "Resumen ejecutivo"
  (pestaña de hipótesis, antes de la lista) solo si `executive_summary` tiene valor, sin
  placeholder; `npm run build` en `frontend/` compila con el cambio del Agente 06 (todas
  las rutas generadas). _Sin verificar:_ nadie vio la sección en el navegador; con el mock
  activo hoy `executive_summary` es `None` (la guarda descarta el resumen grabado), así que
  eso depende de T4 de `odd/tasks/agente06-pendientes.md`.
  _Resultado (2026-10-06):_ `npm run build` sin errores; con un reporte cargado en
  `sessionStorage` la sección "Resumen ejecutivo" aparece arriba de "Hipótesis respaldadas",
  y con `executive_summary: null` no aparece nada (sin errores de consola). Con el mock
  activo el resumen es `None` (la guarda lo descarta, ver 5.2), por eso se verificó con un
  reporte de prueba.

- [x] 6.3 Mostrar el `executive_summary` en el PDF (`backend/pipeline/pdf_exporter.py`):
  si no es `None`, agregar un bloque de texto con título "Resumen ejecutivo" al inicio del
  reporte, antes de las hipótesis. Si es `None`, omitir. Verificar con
  `pytest tests/test_pdf_exporter.py`.

## 7. Evidencia para Trello y tests finales

- [x] 7.1 Crear `scripts/demo_agente06.py` que construye un `StructuredReport` de prueba
  (a mano, sin llamar al pipeline completo), llama a `SynthesizerAgent().synthesize()` y
  muestra el resumen generado, el estado de la guarda y si se descartó algún token.
  Guarda `output/demo_agente06/resumen.json`. Verificar corriendo
  `python3 scripts/demo_agente06.py` (con Groq o en modo mock).

- [x] 7.2 Correr `pytest tests/` completo y verificar que no hay fallas nuevas respecto
  de `develop`. Los tests que usen `POST /api/analyze` deben usar `client_medico_verificado`
  de `tests/conftest.py`. Verificar que la suite pasa en verde.
  _Verificado (2026-10-06):_ `pytest tests/ -q` → 1186 passed en ~62 s en la rama
  `fix/s4-agente06-pendientes` (línea base en `develop` `cc5105b`: 1150 passed). Los tests
  de `POST /api/analyze` (`test_api.py`, `test_router_telemetry.py`, `test_mock_pipeline.py`)
  usan `client_medico_verificado`; `test_proteccion_analisis.py` usa además clientes sin
  cuenta o sin verificar a propósito, para probar el rechazo.

- [x] 7.3 Actualizar `.claude/CLAUDE.md`: Agente 06 marcado como hecho en Sprint 4 y en
  la tabla de numeración, `agent_06_synthesizer.py` en el árbol de carpetas,
  `demo_agente06.py` en la lista de scripts. Verificar leyendo las secciones actualizadas.

- [x] 7.4 Actualizar `.claude/backlog.md`: tarea 13 marcada como hecha con archivos clave,
  campo `executive_summary` documentado en el contrato JSON, nota sobre la respuesta mock
  grabada. Verificar leyendo la tabla del Sprint 4.
