## 1. Saneamiento de fuentes (hallazgo G)

- [x] 1.1 Restringir `BaseAgent.parse_hypotheses()` a una whitelist de campos al construir `Source` (`pmid`, `title`, `journal`, `year`, `url`), descartando en silencio `verified`, `verification_status`, `actual_title` y `publication_types` (D9).
- [x] 1.2 **Crear** `tests/test_base_agent.py` — hoy no existe, `BaseAgent` no tiene suite propia. Verificar que una respuesta con `verified: true` y tipos de publicación inventados produce una `Source` con esos campos en `None`/vacío, y que el resto del parseo (fences de markdown, JSON embebido, hipótesis malformada) sigue funcionando.
- [x] 1.3 Correr `scripts/demo_agente01.py`, `demo_agente03.py` y `demo_base_agent.py` y confirmar que su salida no cambió. Los tres llaman `parse_hypotheses()` pero ninguno imprime campos de verificación, así que no debería haber regresión visible; `demo_base_agent.py` es evidencia de una tarjeta ya aprobada por el profesor, y si su salida cambia hay que re-adjuntarla en Trello.
- [x] 1.4 Verificar que la suite existente sigue verde tras el cambio de parseo: `pytest tests/ --ignore=tests/test_ingesta.py` (Tesseract no está instalado en la máquina de desarrollo). Prestar atención a `tests/test_orchestrator.py` y `tests/test_api.py`, que construyen `Source(...)` a mano.

## 2. Modelos del arbitraje

- [x] 2.1 Crear `backend/models/arbitration.py` con los modelos Pydantic `ConsensusHypothesis` (hipótesis representativa, agrupadas, agentes de respaldo y refutación, contradicciones, veredicto, si fue recitada), `Contradiction`, `ArbitrationInput`, `ArbitrationResult` y `ArbitrationSummary`, todos tipados y con docstrings en español (D8). Verificar con `tests/test_arbitration_models.py` que los modelos validan y que los campos nuevos tienen default.
- [x] 2.2 Agregar `retrieved_articles: list[RetrievedArticle]` (o su equivalente Pydantic) a `Report` en `backend/models/report.py`, con default vacío (D5). Verificar que `tests/test_report_builder.py` sigue pasando sin tocarlo.

## 3. Trazabilidad del RAG

- [x] 3.1 Hacer que `orchestrator._enrich_context_with_rag()` devuelva `(contexto, articulos)` conservando los `RetrievedArticle`, sin cambiar `PubMedRetriever.get_context_for_agent()` (D5). Verificar con un test en `tests/test_rag_integration.py`, mockeado y sin red, que los artículos llegan al `Report`.
- [x] 3.2 Propagar los artículos recuperados hasta el `Report` que devuelve `run_round_1()`, y que el conjunto quede vacío sin romper nada cuando la búsqueda semántica falla. Verificar con un test que simula el fallo del RAG y comprueba que `retrieved_articles == []` y que el análisis continúa.
- [x] 3.3 Implementar la métrica de solapamiento entre PMIDs recuperados y PMIDs citados. Verificar con un test que, con fuentes citadas ajenas al conjunto recuperado, el solapamiento da 0, y con una cita del conjunto da 1.

## 4. Consenso determinista

- [x] 4.1 Crear `backend/pipeline/consensus.py` con la validación de la partición propuesta por el modelo: índices dentro de rango, sin repetidos, cobertura total; los faltantes se agregan como grupo propio y los repetidos se asignan al primer grupo (D1). Verificar con `tests/test_consensus.py` cubriendo partición válida, índice fuera de rango, índice repetido y omisión.
- [x] 4.2 Implementar la elección del texto representativo de cada grupo por regla (mejor estado → mejor nivel efectivo → menor ID de agente) (D3). Verificar con un test que construye un grupo con hipótesis de distinto estado y comprueba cuál queda como representativa.
- [x] 4.3 Implementar la consolidación de fuentes del grupo, deduplicando por PMID. Verificar con un test de dos hipótesis con una fuente compartida y una propia cada una.
- [x] 4.4 Implementar la detección de contradicciones a partir de los `Critique` de la Ronda 2, con el criterio de "el agente cedió" por containment de tokens entre Ronda 1 y Ronda 4 (D4). Verificar con `tests/test_consensus.py`: crítica HIGH mantenida → contradicción; crítica HIGH incorporada → sin contradicción; crítica MEDIUM → sin contradicción.
- [x] 4.5 Implementar el consenso degradado (cada hipótesis su propio grupo, sin veredicto) usado como fallback. Verificar con un test que comprueba que conserva las N hipótesis y marca el arbitraje como fallido.

## 5. Agente 04

- [ ] 5.1 Crear `backend/agents/agent_04_arbiter.py` heredando de `BaseAgent`, con `AGENT_ID = "04"`, llamando al LLM **solo** vía `BaseAgent._call_llm()`, y exponiendo `arbitrate(ArbitrationInput) -> ArbitrationResult`. Verificar con `tests/test_agent_04_arbiter.py` (LLM mockeado, sin red) que produce un consenso a partir de un reporte de debate de prueba.
- [ ] 5.2 Implementar el prompt de agrupación con hipótesis numeradas y salida por índices, más el mapeo de cada crítica a un grupo (D1, D2). Verificar con un test que una salida del modelo con un índice inventado no rompe y cae en la validación de 4.1.
- [ ] 5.3 Implementar el prompt de veredictos, alimentado con el estado bibliográfico y el nivel efectivo que ya calculó `evidence.classify_hypothesis()`. Verificar con un test que un veredicto que contradice el estado calculado no altera el estado ni el nivel del resultado.
- [ ] 5.4 Implementar las guardas de salida del modelo: descartar referencias que no estaban en la entrada, ignorar intentos de subir nivel y de descartar hipótesis, y contabilizar los descartes (spec `arbitro-consenso`). Modelarlas sobre la guarda anti-invención que **ya existe** en `agent_02_genomics.py`, con su suite `TestGuardaAntiInvencion` en `tests/test_agent_02_genomics.py` como referencia de forma, en vez de inventar un patrón nuevo. Verificar con tests dedicados para cada una de las tres guardas.
- [ ] 5.5 Implementar el fallback completo del agente ante fallo del LLM o JSON no parseable, devolviendo el consenso degradado de 4.5. Verificar con un test que fuerza la excepción y comprueba que `arbitrate()` devuelve resultado válido y no propaga.
- [ ] 5.6 Verificar que ningún log del agente emite texto clínico, hipótesis ni respuestas del modelo: test que captura stderr ante un fallo y comprueba que solo aparece el tipo de excepción.

## 6. Ronda 5 — recitación

- [ ] 6.1 Agregar a `BaseAgent` el método de recitación que recibe las hipótesis sin respaldo del agente, el motivo de fallo de cada cita y los artículos recuperados, y devuelve fuentes nuevas (D6). Verificar con un test mockeado que el prompt incluye los PMIDs ofrecidos y los motivos.
- [ ] 6.1b Sobreescribir la recitación en `GenomicsSpecialistAgent`, igual que hace hoy con `run()`, `critique()` y `revise()` (`agent_02_genomics.py:84,99,101`): enriquecer el contexto con el perfil genómico y aplicar la guarda anti-invención sobre la salida. Sin este override el Agente 02 recita sin contexto genómico y sin guarda. Verificar con un test en `tests/test_agent_02_genomics.py` que el prompt de recitación contiene el contexto genómico y que un hallazgo inventado se degrada.
- [ ] 6.2 Implementar la selección de hipótesis a recitar: solo las que no están `respaldada` y solo si la verificación pudo ejecutarse y hay artículos recuperados (spec `recitacion-evidencia`). Verificar con tests para los casos: especulativa → recita; respaldada → no; pendiente por PubMed caído → no; sin artículos → no.
- [ ] 6.3 Implementar la validación de los PMIDs recitados contra el conjunto ofrecido, descartando sin consultar PubMed los que no pertenecen y contando los descartes. Verificar con un test que un PMID inventado se descarta y no genera llamada a PubMed.
- [ ] 6.4 Implementar la re-verificación contra PubMed de las fuentes aceptadas, agregando en `verification.py` una función que verifique un subconjunto de `Source`. **Sin cambiar la firma de `verify_report_sources(report)`**: la llaman `scripts/demo_verificacion.py:127` y `scripts/demo_priorizacion_evidencia.py:138`, ambos evidencia de tarjetas en QA. Lo natural es extraer el cuerpo actual a la función nueva y dejar `verify_report_sources()` delegando en ella. Verificar con un test mockeado: título correcto → verificada y la hipótesis pasa a respaldada; título que no corresponde → discordante; y que los dos demos siguen corriendo.
- [ ] 6.5 Garantizar el tope de una sola iteración y el criterio de parada nuevo. Verificar con un test que, con todas las hipótesis aún sin respaldo después de recitar, el análisis termina y no hay segunda recitación.
- [ ] 6.6 Implementar el fallback ante fallo de recitación de un agente, conservando el estado previo de sus hipótesis y completando el resto. Verificar con un test que falla un agente de tres y comprueba que el análisis termina bien.
- [ ] 6.7 Implementar el resumen de la recitación (recitadas, mejoradas, descartadas por PMID ajeno). Verificar con un test de conteos sobre un escenario armado.

## 7. Orden EBM con respaldo del consenso

- [ ] 7.1 Agregar a `evidence.prioritize()` el criterio de cantidad de agentes de respaldo, después del nivel efectivo y antes de la prioridad, como parámetro opcional con default 1 (D8, spec `clasificacion-evidencia-ebm` modificada). Verificar con los escenarios nuevos de la spec en `tests/test_evidence.py`.
- [ ] 7.2 Verificar explícitamente la no regresión: un reporte armado sin arbitraje ordena igual que antes del cambio. Test dedicado en `tests/test_evidence.py`.

## 8. Integración en el pipeline

- [ ] 8.1 Reemplazar la consolidación manual de `debate.run_debate()` y mover `_detect_divergences()` al Árbitro, dejando que el debate entregue las hipótesis sin consolidar. Verificar que `tests/test_debate.py` sigue verde con los ajustes correspondientes.
- [ ] 8.2 Serializar `api/router.py`: `debate → verificación → Árbitro → navegación`, reemplazando el `asyncio.gather` de los pasos 6 y 7 (D7). Verificar con `tests/test_api.py` que `POST /api/analyze` responde 200 con todo mockeado.
- [ ] 8.3 Adaptar `trial_matching.build_navigation_input()` para recibir las hipótesis de consenso sin tocar el Agente 05. Verificar con `tests/test_trial_matching.py` que la entrada se arma desde el consenso y que un consenso degradado también funciona.
- [ ] 8.3b Actualizar `scripts/demo_agente05.py`, que llama `build_navigation_input()` en `_correr_real()` y `_correr_sin_red()` y se rompe con la firma nueva. Es la evidencia de la tarjeta #53, ya en QA: correr las dos variantes (con red y `--sin-red`) y confirmar que producen los mismos artefactos que antes. Si la salida cambia, re-adjuntarla en #53.
- [ ] 8.4 Agregar la red de seguridad del router alrededor del Árbitro, con el mismo patrón que `_navigate_trials_safe()`. Verificar con un test que una excepción inesperada del Árbitro no rompe `POST /api/analyze`.

## 9. Reporte exportado

- [ ] 9.1 Extender `api/schemas.py`: `RankedHypothesis` suma `supporting_agents` del consenso, `refuting_agents`, `contradictions`, `arbiter_note` y la marca de recitada; `StructuredReport` suma `arbitration: ArbitrationSummary | None`. Todo aditivo con default (spec `reporte-consenso`). Verificar con un test que un reporte previo, sin esos campos, sigue validando.
- [ ] 9.2 Hacer que `report_builder._rank_hypotheses()` consuma el consenso en vez del índice por texto exacto. Verificar con un test que tres hipótesis equivalentes agrupadas producen una entrada con tres agentes de respaldo.
- [ ] 9.3 Construir el `ArbitrationSummary` (entrada vs. consenso, contradicciones, recitación, solapamiento RAG). Verificar con un test de consistencia de conteos: consenso ≤ entrada y mejoradas ≤ recitadas.
- [ ] 9.4 Actualizar `pipeline/pdf_exporter.py` con respaldo, refutación, contradicciones y resultado de la recitación, más la aclaración de que el consenso es entre agentes de IA y no es diagnóstico. **Coordinar con la tarjeta #78 de Fede, que toca el mismo archivo** (ver Risks en design.md). Verificar con `tests/test_pdf_exporter.py` y abriendo el PDF generado.

## 10. Frontend

- [ ] 10.1 Actualizar `frontend/src/lib/types.ts` con los campos nuevos del reporte, todos opcionales. Verificar con `npx tsc --noEmit` en `frontend/`.
- [ ] 10.2 Mostrar en la tab de hipótesis de `frontend/src/app/report/page.tsx` los agentes que respaldan y refutan, las contradicciones, el veredicto del Árbitro y la marca de recitada, con la aclaración sobre el consenso de IA. Verificar con `npm run build` y una captura de la vista con un reporte real inyectado por `sessionStorage`.
- [ ] 10.3 Reflejar el paso del Árbitro en la animación de `frontend/src/app/analyzing/page.tsx`, ahora que el pipeline es más largo. Verificar visualmente durante una corrida real.

## 11. Evidencia y cierre

- [ ] 11.1 Crear `scripts/demo_agente04.py` que muestre entrada → salida del Árbitro: hipótesis del debate, partición del agrupamiento (qué se agrupó con qué), contradicciones detectadas, veredictos, resultado de la recitación y solapamiento RAG↔citas. Con modo `--sin-red` que use respuestas grabadas y simule la caída del LLM y de PubMed para mostrar cada fallback. Guarda artefactos en `output/demo_agente04/`.
- [ ] 11.2 Correr `POST /api/analyze` de punta a punta sobre el caso base (neuropatía axonal sensitivomotora, paciente masculino de 42 años) y guardar los artefactos en `output/corrida_agente04/`. Registrar los números medidos: hipótesis de entrada vs. consenso, contradicciones, recitadas, mejoradas y solapamiento RAG↔citas antes y después de recitar.
- [ ] 11.3 Correr la suite completa: `pytest tests/ --ignore=tests/test_ingesta.py` y dejar constancia del resultado.
- [ ] 11.4 Actualizar `.claude/architecture.md`: flujo con el Árbitro serializado, la Ronda 5 de recitación y el **criterio de parada corregido** (hoy en `architecture.md:397` describe algo inalcanzable), más el Agente 04 marcado como implementado.
- [ ] 11.5 Actualizar `.claude/CLAUDE.md` y `.claude/backlog.md`: tarea 9 cerrada, hallazgo G resuelto, Agente 04 ✅ en la tabla de agentes, `demo_agente04.py` en la lista de scripts, y los números de la corrida real en la nota de la tarea.
- [ ] 11.6 Adjuntar la evidencia a la tarjeta #52 de Trello (capturas de entrada → salida, `.json` y `.txt` de `output/`), actualizar su descripción con los números medidos y moverla a QA.
