# Grabación de respuestas reales para el modo mock

Rama: `feature/s4-grabacion-respuestas-mock` (base `develop`, `5d95564`).
Cierra la tarea 6.2 de `openspec/changes/control-de-costos-del-pipeline/tasks.md`
y el punto 4.2 de `.claude/traspaso.md`.

## Objetivo

Que las respuestas grabadas de `backend/mock/responses.py` salgan de una corrida
real contra Groq, y que esa misma corrida verifique los arreglos de parseo de los
PR #25 y #26.

## Problema

Las respuestas del modo mock están escritas a mano. No existe un mecanismo que
guarde el texto crudo que devuelve el modelo: la telemetría solo guarda conteos.
Sin eso, una corrida real (dos por día de cuota) no deja nada reutilizable.

## Alcance

- Grabador de respuestas crudas, apagado salvo que un script lo abra de forma
  explícita. Mismo patrón que `backend/telemetry/usage.py` (`contextvars`).
- Opción `--grabar` en `scripts/medir_costos.py`.
- Regenerar `backend/mock/responses.py` desde la grabación.

Fuera de alcance: cambiar el formato de `MOCK_RESPONSES` (una respuesta por
tarea), tocar `TASK_BUDGETS`, tareas 6.4 y 7.5.

## Restricciones

- El grabador nunca se activa por variable de entorno ni desde `POST /api/analyze`:
  solo lo abre un script. Sin grabador abierto, `call_provider()` se comporta
  exactamente igual que hoy.
- Solo guarda la respuesta del modelo, nunca el prompt ni el mensaje del usuario.
- Salida en `output/` (ignorada por git). El caso es el de prueba, anonimizado.
- Un fallo al grabar nunca rompe la llamada al proveedor.
- En modo mock no se graba nada.
- Cuota de Groq: 200k tokens por día, ~77,5k por caso. Una sola corrida real.

## TDD

Modo estricto (fuente: `~/.claude/CLAUDE.md`, "Strict TDD Mode: enabled").
Runner: `.venv/bin/python -m pytest`.

## Tareas

- [x] **T1 — Grabador y opción `--grabar`** · ruta: delegada (escritor único;
  toca `backend/mock/`, `backend/agents/base_agent.py`, `scripts/medir_costos.py`
  y tests).
  - Criterios: con grabador abierto, cada llamada exitosa queda registrada con
    tarea, agente, modelo y texto crudo, en orden; sin grabador, nada cambia; en
    modo mock no graba; `--grabar --mock` no escribe grabación.
  - Checks: `.venv/bin/python -m pytest tests/ -q`;
    `.venv/bin/python scripts/medir_costos.py --mock`;
    `rg -n "Groq\(api_key" backend/` devuelve una sola línea.
- [x] **T2 — Corrida real con grabación** · ruta: inline (una ejecución).
  - Criterios: `output/medicion_costos/` con medición y grabación; debate con
    tres agentes; anotar si aparece `[NEXUS] Respuesta del modelo saneada`.
  - Checks: lectura de `resumen.txt` y de la grabación.
- [x] **T3 — Regenerar `backend/mock/responses.py`** · ruta: delegada.
  - Criterios: cada tarea de `TASK_BUDGETS` usa una respuesta salida de la
    grabación, o queda documentado por qué se conserva la escrita a mano.
  - Checks: `.venv/bin/python -m pytest tests/ -q`;
    `.venv/bin/python scripts/medir_costos.py --mock`.

- [x] **T4 — Destinatario de las críticas** · ruta: delegada (commit `a2227ae`).
  - El parser normaliza el destinatario ("Agent 02" → "02") y el prompt muestra un ID real de ejemplo.
  - RED observado sin el arreglo: 9 failed / 23 passed en `tests/test_debate.py`.
  - GREEN: 32 passed; suite completa 1080 passed.
- [x] **T5 — `debate_critica` grabada** · ruta: delegada.
  - Criterios: primera entrada por `seq` de la corrida real (seq 6, agente 01), copiada
    verbatim a `backend/mock/grabadas.json`; las 12 tareas son grabaciones; se elimina
    `HAND_WRITTEN_TASKS` (nada más lo usaba).
  - La grabación rinde 5 críticas con destinatarios "02", "02", "03", "03", "03" tras normalizar.
  - RED: `tests/test_mock_responses.py` y `tests/test_mock_pipeline.py` -> `7 failed, 66 passed`.
  - GREEN: los mismos archivos -> 73 passed; `.venv/bin/python -m pytest tests/ -q` -> 1082 passed.
  - Observación: en mock los tres agentes reciben la misma respuesta, incluido el autor
    (01, que no se critica a sí mismo en la grabación). El agente 02 recibe críticas con
    `from_agent_id` "02" y destinatario "02": ni `_critiques_for()` ni el resto del pipeline
    filtran las autocríticas. Solo ocurre en mock; producción no se tocó.

## Entrega

Estrategia `ask-on-risk`. Pronóstico: ~350 líneas autoría (T1 ~200, T3 ~150).

## Progreso y evidencia

T1 hecha (ruta delegada: escritor único; disparador de escritura sobre 2+ archivos no triviales).
- RED: `tests/test_recorder.py` falló en la colección con
  `ImportError: cannot import name 'recorder' from 'backend.mock'`.
- GREEN: `.venv/bin/python -m pytest tests/test_recorder.py -q` -> 18 passed.
- `.venv/bin/python -m pytest tests/ -q` -> 1027 passed.
- `.venv/bin/python scripts/medir_costos.py --mock` -> rc 0.
- `... --mock --grabar` -> avisa que no hay nada que grabar; no existe
  `grabacion.json` en `output/medicion_costos/` ni en `.../mock/`.
- `rg -n "Groq\(api_key" backend/` -> una sola línea (`base_agent.py:147`).
- Forma de `grabacion.json`: `{generated_at, entries: [{seq, task, agent_id,
  agent_name, model, truncated, response}]}`.

T2 hecha (ruta inline; la lanzó el padre). Corrida real del 2026-10-06:
- Exit code 0; pasada base de 437 s.
- 29 llamadas, 8 fallaron por límite de tasa y se reintentaron con éxito.
- 78.158 tokens (39.480 de entrada / 38.678 de salida): sigue siendo 2 casos por cuota diaria.
- 0 respuestas cortadas por el techo de tokens; 21 respuestas grabadas.
- Los tres agentes del debate (01, 02, 03) produjeron hipótesis, críticas, revisiones y recitaciones.
- El aviso `[NEXUS] Respuesta del modelo saneada` NO apareció: no hubo ninguna respuesta
  malformada, así que los arreglos de parseo tolerante de los PR #25 y #26 no se
  ejercitaron en esta corrida; siguen verificados solo por tests.

T3 hecha (ruta delegada: escritor único; escribe datos, módulo, tests y documentos).
Regla de elección: la primera grabación por orden de llamada (`seq` más bajo) de cada tarea.
Datos en `backend/mock/grabadas.json` (versionado); `responses.py` los carga al importar.

| Tarea | Origen |
|-------|--------|
| `biomarcadores_extraccion` | grabada (seq 1) |
| `pico_sintesis` | grabada (seq 2) |
| `agente02_hipotesis` | grabada (agente 02, seq 3) |
| `agente01_hipotesis` | grabada (agente 01, seq 4) |
| `agente03_hipotesis` | grabada (agente 03, seq 5) |
| `debate_critica` | grabada (agente 01, seq 6); ver T4 y T5: se escribió a mano hasta que el parser normalizó el destinatario. |
| `debate_revision` | grabada (agente 01, seq 9) |
| `arbitro_agrupacion` | grabada (agente 04, seq 15) |
| `debate_recitacion` | grabada (agente 01, seq 16) |
| `arbitro_veredictos` | grabada (agente 04, seq 19) |
| `agente05_planificacion_terminos` | grabada (agente 05, seq 20) |
| `agente05_evaluacion_compatibilidad` | grabada (agente 05, seq 21) |

- Hallazgo sobre producción (no tocado, fuera de alcance): en la corrida real ninguna crítica
  llegó a su destinatario por el desajuste de `target_agent_id`; `consensus.py:233` usa el
  mismo campo para detectar contradicciones. Conviene una tarjeta aparte.
- Caveat de las grabadas por posición (agrupación, veredictos, recitación, candidatas): en mock
  los tres agentes reciben la misma respuesta, así que se aplican por posición a hipótesis
  distintas de las de la corrida real. Lo que cita NCT o PMID depende de que ClinicalTrials.gov
  y PubMed devuelvan hoy lo mismo (las consultas externas se conservan en mock, como antes).
- RED: `tests/test_mock_responses.py` -> `28 failed, 13 passed` (faltaban `grabadas.json`,
  `RECORDED_RESPONSES` y `HAND_WRITTEN_TASKS`).
- GREEN: `.venv/bin/python -m pytest tests/test_mock_responses.py -q` -> 41 passed.
- Se ajustó una aserción de `tests/test_mock_pipeline.py` que dependía del texto escrito a mano
  ("metformina" en fármacos, aportada por la fixture, no por la regex): ahora verifica los
  anticuerpos que aportó la respuesta grabada. Ningún parser ni validación de producción cambió.
- Corrida mock completa con las grabadas (`pasada_base`, red real para RAG y ClinicalTrials):
  Árbitro `ok`, 14 hipótesis -> 10 grupos, 10 veredictos aplicados, recitación ejecutada
  (10 recitadas, 3 mejoradas, 0 PMID rechazados), Agente 05 `ok`/`ok`, 0 evaluaciones descartadas.
- `.venv/bin/python -m pytest tests/ -q` -> 1068 passed.
- `.venv/bin/python scripts/medir_costos.py --mock` -> rc 0.
- `NEXUS_MOCK_LLM=1 .venv/bin/python scripts/demo_costos.py` -> rc 0.
- `rg -n "Groq\(api_key" backend/` -> una sola línea (`base_agent.py:147`).

Revisión nativa del commit `4e8e984`: evaluada como riesgo medio y debida
(`slice_budget_reached`, 601 líneas), pero NO corrió: STATUS se detuvo con
`managed_assets_outdated`; el usuario eligió correr `gentle-ai sync` al final de la sesión.
El espejo de Engram de este documento está pendiente (el guardado falló: varias sesiones activas).

Test intermitente preexistente: `tests/test_agent_05_trials.py::TestPrivacidad::test_trazabilidad_de_los_ensayos`
falló una vez en una corrida completa y pasó solo y en la corrida siguiente (no se investigó).

## Próximo paso

Confirmar con la segunda corrida real (en curso) y luego PR a `develop`; quedan las tareas 6.4 y 7.5.
