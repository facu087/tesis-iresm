# Agente que sostiene y objeta la misma hipótesis: "sostiene con reservas" (tarjeta #80)

Rama: `fix/s4-sostiene-con-reservas` (base `develop`, `b9bd0c5`).

## Objetivo

Que el reporte deje de mostrar a un mismo agente en la lista de quienes
sostienen una hipótesis de consenso y en la de quienes la objetan, y lo muestre
como lo que es: un agente que la sostiene con reservas.

## Problema

El Árbitro agrupa hipótesis equivalentes de varios agentes. `supporting_agents`
sale de quiénes aportaron alguna hipótesis al grupo y `refuting_agents` de las
objeciones HIGH sin resolver contra alguna hipótesis del grupo. Un agente puede
estar en las dos: aportó una hipótesis y criticó otra que terminó agrupada con
la suya. El dato es correcto; el reporte lo aplana en dos listas y parece un
error del sistema. Frecuencia medida el 2026-09-22: 1 de 7 hipótesis.

## Decisión

Tomada por Matías el 2026-10-06, entre las cuatro ideas de la tarjeta #80:
la 1, mostrar el matiz. No se quita al agente de ninguna lista de datos.

## Alcance

- Los datos del consenso no cambian: `supporting_agents` y `refuting_agents`
  siguen como están (el orden del reporte usa la cantidad de agentes que
  sostienen).
- Se agrega un dato derivado y determinista: los agentes que están en ambas
  listas (`agents_with_reservations`), en el orden de `supporting_agents`.
- El reporte web y el PDF muestran tres grupos sin repetir nombres: quienes
  sostienen, quienes sostienen con reservas y quienes objetan.
- Fuera de alcance: prompts, llamadas al LLM, agrupamiento, detección de
  contradicciones, clasificación EBM y cambio OpenSpec.

## Restricciones

- Aditivo: un reporte sin el campo nuevo se renderiza como antes.
- Sin llamadas al proveedor ni a la red en los tests.

## Tareas

- [x] **T1 — Dato derivado y exportación** · ruta: delegada (un escritor; el
  cambio toca más de dos archivos no triviales).
  - `ConsensusHypothesis.agents_with_reservations` (propiedad) en
    `backend/models/arbitration.py`.
  - Campo `agents_with_reservations: list[str] = []` en `RankedHypothesis`
    (`backend/api/schemas.py`), cargado por `backend/pipeline/report_builder.py`.
  - Tests primero (RED → GREEN).
- [x] **T2 — PDF** · misma delegación.
  - Celda de agentes sin los que tienen reservas; línea "Sostenida con reservas
    por: …"; "Objetada por: …" solo con quienes objetan sin sostener.
- [x] **T3 — Reporte web** · misma delegación.
  - Tipo en `frontend/src/lib/types.ts` y chips en
    `frontend/src/app/report/page.tsx`.

## Criterios de aceptación

- Con un agente en ambas listas, el JSON exportado lo trae en
  `agents_with_reservations` y conserva las dos listas originales.
- El PDF y el reporte web no repiten ese nombre: aparece una sola vez, como
  "con reservas".
- Sin agentes en ambas listas, el JSON, el PDF y la pantalla quedan igual que
  antes.

## Verificación

- `pytest tests/test_arbitration_models.py tests/test_consensus.py tests/test_report_builder.py tests/test_pdf_exporter.py tests/test_arbitration_pipeline.py -q`
- `pytest tests -q` (en Windows fallan 4 tests ajenos: tres de
  `tests/test_ingesta.py` por Tesseract y
  `test_hermetico_sin_red_analisis_completo_en_modo_mock`).
- `npx tsc --noEmit` y `npm run build` en `frontend/`.

## Progreso

Las tres tareas quedaron hechas el 2026-10-06 por un escritor delegado, en un solo commit de
la rama.

- **RED** observado antes de implementar: 14 tests nuevos fallando (falta del atributo y de la
  línea del PDF) y 126 pasando.
- **GREEN**: los cinco archivos de test de consenso, modelos, exportación y PDF, 232 pasan
  (corrido por el escritor y vuelto a correr por el orquestador).
- Suite completa en Windows: 1239 pasan y 4 fallan, los cuatro ajenos ya conocidos.
- `npx tsc --noEmit` sin errores y `npm run build` compila, con `/report` entre las páginas.

Los tests de `build_export()` con arbitraje fueron a `tests/test_arbitration_pipeline.py`, que
es donde ya se cubre ese camino; `tests/test_report_builder.py` no se tocó.

Decisiones que el diseño no cubría:
- La línea del PDF usa el color `_ORANGE` ya existente; `_AMBER` es claro para texto de 8 pt.
- El PDF y la vista filtran por el campo exportado y no recalculan la intersección.

Sin verificar:
- Los chips del reporte web no tienen test automatizado ni se vieron en un navegador: solo
  pasan el chequeo de tipos y el build.
- El color de la línea del PDF no se revisó a la vista; los tests miran el texto extraído.

Siguiente paso: ver el chip y la línea del PDF en una corrida donde un agente quede en ambas
listas, y adjuntar la captura a la tarjeta #80.
