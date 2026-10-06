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
- [ ] **T2 — Corrida real con grabación** · ruta: inline (una ejecución).
  - Criterios: `output/medicion_costos/` con medición y grabación; debate con
    tres agentes; anotar si aparece `[NEXUS] Respuesta del modelo saneada`.
  - Checks: lectura de `resumen.txt` y de la grabación.
- [ ] **T3 — Regenerar `backend/mock/responses.py`** · ruta: delegada.
  - Criterios: cada tarea de `TASK_BUDGETS` usa una respuesta salida de la
    grabación, o queda documentado por qué se conserva la escrita a mano.
  - Checks: `.venv/bin/python -m pytest tests/ -q`;
    `.venv/bin/python scripts/medir_costos.py --mock`.

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

## Próximo paso

T2 (corrida real con `--grabar`, la lanza el padre).
