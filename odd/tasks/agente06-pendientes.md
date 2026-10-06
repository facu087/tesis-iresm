# Pendientes del Agente 06 tras la revisión del PR #35

Rama: `fix/s4-agente06-pendientes` (base `develop`, `cc5105b`).

## Objetivo

Cerrar lo que la revisión posterior al merge del Agente 06 dejó abierto.

## Problema

- **Guarda de siglas**: cualquier sigla de 2 a 8 mayúsculas que no esté en el
  reporte descarta el resumen entero, y el modelo no sabe que lo juzgan por eso.
  En modo mock el resumen grabado se descarta siempre (cita genes de otra
  corrida), así que el Agente 06 no se ve en modo mock.
- **Recorte del contexto**: se trunca a 6000 caracteres desde el final, donde
  van los ensayos y la verificación.
- **PDF**: varios campos de texto libre llegan sin escapar a ReportLab.
- **Documentación**: el traspaso no menciona la protección de los tests contra
  llamadas reales al proveedor; las tareas 6.2 y 7.2 del cambio OpenSpec
  `agente-06-sintetizador` siguen sin tildar.

## Alcance

Los cuatro puntos de arriba. Fuera de alcance: cambiar la decisión de descartar
el resumen entero, aflojar la guarda, tocar `TASK_BUDGETS`, el defecto de fondo
del `RateLimiter` y las cuatro observaciones abiertas de la revisión de los PR
#30 y #31.

## Restricciones

- La guarda no se afloja: una sigla con forma de gen que no está en el reporte
  sigue descartando el resumen.
- Las respuestas del modo mock son grabaciones textuales; no se editan a mano.
- Cuota de Groq agotada el 2026-10-06: los escritores no llaman al modelo real.
- Los datos clínicos no se loggean.

## TDD

Modo estricto (fuente: `~/.claude/CLAUDE.md`). Runner: `.venv/bin/python -m pytest`.

## Tareas

- [x] **T1 — Contexto y prompt del Agente 06** · ruta: delegada.
  - El recorte conserva siempre los bloques de ensayos y de verificación; lo que
    se acorta es lo más largo (narrativa y fundamentos).
  - El prompt le dice al modelo la regla por la que se lo juzga: no introducir
    siglas ni símbolos que no figuren en el reporte.
  - Checks: `pytest tests/test_agent_06_synthesizer.py -q`; suite completa.
- [x] **T2 — Texto libre del PDF como texto literal** · ruta: delegada.
  - Todo campo de texto libre que llega a un `Paragraph` se escapa; el marcado
    propio del exportador se conserva.
  - Checks: `pytest tests/test_pdf_exporter.py -q`; suite completa.
- [x] **T3 — Documentación** · ruta: delegada.
  - Traspaso al día (protección de los tests, estado de las observaciones);
    tareas 6.2 y 7.2 tildadas solo si lo que piden está observado.
- [ ] **T4 — Resumen del modo mock coherente con el reporte mock** · ruta: inline.
  - Grabar la respuesta del Agente 06 sobre el reporte del modo mock (una sola
    llamada real, con el prompt ya corregido en T1), para que la guarda la
    acepte y el agente se vea en modo mock.
  - Depende de la cuota de Groq: si no hay, queda pendiente para el día siguiente.
  - Checks: en una corrida mock, `executive_summary` no es `None`.

## Entrega

Estrategia `ask-on-risk`. Pronóstico: ~350 líneas (T1 ~120, T2 ~150, T3 ~80).

## Progreso y evidencia

- **T1** (ruta: delegada; disparador: escritura de 2 archivos + preparación). RED: con el código
  anterior, 4 de 33 fallaron (`test_recorte_conserva_ensayos_y_verificacion_completos`,
  `test_recorte_conserva_cada_hipotesis_con_sus_pmids`,
  `test_caso_patologico_no_pierde_bloques_aunque_exceda_el_limite`,
  `test_el_prompt_pide_no_introducir_siglas`); GREEN: 33 passed. El contexto corto queda
  idéntico byte a byte (fijado en un test). Commit `bbfa333`.
- **T2** (ruta: delegada). RED: con el exportador anterior, 27 fallaron y 60 pasaron;
  GREEN: 87 passed en `tests/test_pdf_exporter.py` (los tests previos sin cambios). Commits
  `ef1f57c` y `67759b2` (este último corrige un assert del test nuevo, sin tocar código).
- **T3** (ruta: delegada). `pytest tests/ -q`: 1186 passed en ~62 s;
  `medir_costos.py --mock` termina sin error; `rg "Groq\(api_key" backend/` devuelve una
  sola línea (`base_agent.py:148`); `npm run build` en `frontend/` compila. Tarea 7.2 del
  OpenSpec tildada; 6.2 queda abierta con nota (nadie vio la sección en el navegador).

- **T4** (ruta: inline). Intentada el 2026-10-06: Groq rechazó la llamada por límite de
  cuota en los tres reintentos (`RateLimitError`); no se grabó nada y `executive_summary`
  sigue en `None` en modo mock. El reporte del modo mock tiene 10 hipótesis y 10 ensayos, y
  su contexto para el Agente 06 mide 5982 caracteres.

## Próximo paso

T4, con cuota (una llamada de unos 2.000 tokens). Método: correr la pasada base en modo
mock para obtener el `StructuredReport`, desactivar el modo mock y llamar una vez a
`SynthesizerAgent().synthesize()` con el grabador de `backend/mock/recorder.py` abierto. Si
la guarda acepta el resumen, copiar la respuesta textual a `backend/mock/grabadas.json` en
la tarea `agente06_sintesis` con su procedencia (reemplaza a la grabada sobre el reporte
real) y ajustar `tests/test_mock_responses.py`. El guion usado quedó en
`output/pendientes/grabar_ag06_mock.py` (local, no versionado). Si la guarda lo descarta,
anotar por qué token antes de reintentar.
