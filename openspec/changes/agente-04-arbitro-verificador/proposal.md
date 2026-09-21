## Why

El Agente 04 existe hoy sólo a medias. La **verificación** funciona y es el hallazgo
más fuerte del Sprint 4: `pipeline/verification.py` contrasta cada PMID citado contra
PubMed y compara el título real con el declarado, y en la corrida del 2026-09-15 sobre
el caso de la tesis **las 15 citas de los agentes resultaron discordantes** — PMIDs que
existen pero apuntan a otro artículo. Falta la mitad de **síntesis**: nadie razona
sobre el conjunto.

Por eso `debate.py:run_debate()` termina con una concatenación plana —
`final_hypotheses = [h for o in outputs_r4.values() for h in o.hypotheses]` — y el
médico recibe nueve entradas donde hay cuatro hipótesis distintas, la misma repetida
por tres agentes con distinta redacción, sin decir en ningún lado que los tres
coincidieron ni que un cuarto la contradijo. El único registro de desacuerdo es
`_detect_divergences()`, una heurística de solapamiento de palabras sobre las críticas
HIGH de la Ronda 2.

Hay además un dato medido que ningún módulo aprovecha: **ninguno de los PMIDs que
citaron los agentes coincide con los que el RAG les puso en el prompt**. Los agentes
ignoran la literatura recuperada e inventan referencias. El RAG recupera artículos
reales de PubMed y el orquestador tira los objetos `RetrievedArticle` quedándose sólo
con el string formateado, así que nadie puede contrastar lo citado contra lo ofrecido.

## What Changes

- Nuevo **Agente 04 — Árbitro Verificador** (`backend/agents/agent_04_arbiter.py`),
  hereda de `BaseAgent` y usa el LLM **sólo** vía `BaseAgent._call_llm()`. No participa
  del debate ni emite hipótesis propias: expone
  `arbitrate(ArbitrationInput) -> ArbitrationResult`.
- **Agente híbrido**, mismo precedente que el Agente 05. El LLM hace sólo dos cosas —
  agrupar hipótesis equivalentes y redactar el fundamento del veredicto— y **nunca**
  descarta una hipótesis, nunca inventa fuentes y nunca sube un nivel de evidencia. La
  verificación, la clasificación EBM, el orden y la decisión de qué se recita son
  deterministas y ya existen (`verification.py`, `evidence.py`).
- **Consenso en lugar de concatenación plana**: el Árbitro agrupa las hipótesis
  equivalentes de los tres agentes en una `ConsensusHypothesis` con los agentes que la
  respaldan, los que la refutan y las contradicciones detectadas. Toda hipótesis de
  entrada cae en exactamente un grupo: agrupar no descarta.
- **Ronda 5 — recitación acotada**: las hipótesis que quedan sin respaldo verificable
  vuelven a su agente de origen junto con los artículos que el RAG había recuperado, y
  se les pide volver a citar **sobre esa literatura real**. Los PMIDs nuevos se validan
  contra el conjunto ofrecido (un PMID fuera de esa lista se rechaza sin consultar
  PubMed) y se re-verifican contra PubMed. **Máximo una iteración**: lo que siga sin
  respaldo queda especulativo y se documenta. Esto reemplaza el criterio de parada de
  `architecture.md:397`, que exigía que toda hipótesis tuviera referencia verificable y
  con 15/15 citas discordantes no se cumple nunca.
- **Trazabilidad del RAG**: `orchestrator.run_round_1()` deja de descartar los
  `RetrievedArticle` y los conserva en el `Report`, para que el Árbitro pueda medir el
  solapamiento entre lo recuperado y lo citado, y alimentar la recitación. El reporte
  expone ese número — es el dato que justifica que el Árbitro exista.
- **Hallazgo G** (`base_agent.py:92`): `parse_hypotheses()` arma `Source(**s)` con lo
  que manda el LLM, así que hoy acepta `verified`, `verification_status`,
  `actual_title` y `publication_types` autodeclarados. Pasan a sanearse en el parseo:
  esos campos son salida de la verificación, nunca entrada del modelo. `evidence.py` y
  `_annotate_source()` ya los ignoraban aguas abajo, pero el dato sucio viajaba en el
  `Report` interno hasta ahí.
- **Orden del pipeline** (`api/router.py`): los pasos 6 y 7 dejan de correr en paralelo
  y pasan a ser `debate → verificación → Árbitro → navegación de ensayos`. El Agente 05
  recibe las hipótesis de consenso en vez de las crudas, que es lo que
  `architecture.md:78` anticipaba y lo que reduce el ruido de su búsqueda (busca sobre
  el consenso, no sobre nueve entradas con duplicados). El adaptador
  `trial_matching.build_navigation_input()` es el único punto que cambia; el Agente 05
  no se toca.
- **Contrato de exportación aditivo**, mismo precedente que `Source.verified` y
  `trial_search`: `RankedHypothesis` suma `supporting_agents` reales del consenso,
  `refuting_agents`, `contradictions` y `arbiter_note`; `StructuredReport` suma
  `arbitration: ArbitrationSummary | None` (hipótesis de entrada vs. de consenso,
  cuántas se recitaron, cuántas mejoraron, solapamiento RAG↔citas). Un reporte previo
  al Árbitro sigue siendo válido con `arbitration: null`.
- Frontend (tab de hipótesis) y PDF muestran quién respalda y quién refuta cada
  hipótesis de consenso, las contradicciones documentadas y el resultado de la
  recitación, con la aclaración de que el consenso es entre agentes de IA y no
  constituye diagnóstico.
- Privacidad: a PubMed sólo viajan PMIDs; el prompt del Árbitro recibe hipótesis y
  fundamentos ya anonimizados por el PICO; los logs registran tipo de excepción y
  conteos, nunca texto clínico ni respuestas del LLM.

## Capabilities

### New Capabilities
- `arbitro-consenso`: Agente 04 — contrato de entrada y salida, agrupación de hipótesis
  equivalentes en consenso, registro de agentes que respaldan y refutan, detección de
  contradicciones, veredicto por hipótesis, garantía de que agrupar no descarta, límites
  del LLM (no inventa fuentes, no sube niveles, no excluye) y fallbacks.
- `recitacion-evidencia`: Ronda 5 — qué hipótesis se recitan, cómo se les ofrece la
  literatura recuperada por el RAG, validación de los PMIDs nuevos contra el conjunto
  ofrecido, re-verificación, tope de una iteración, criterio de parada que reemplaza al
  documentado, y trazabilidad del solapamiento entre lo recuperado y lo citado.
- `reporte-consenso`: cómo llegan el consenso, las contradicciones y el resumen de
  arbitraje al `StructuredReport`, al frontend y al PDF sin romper el contrato vigente.

### Modified Capabilities
- `clasificacion-evidencia-ebm`: dos requisitos cambian. **"Solo cuentan los veredictos
  de la verificación"** se extiende al parseo — hoy el requisito obliga a ignorar los
  campos autodeclarados al clasificar, y pasa a obligar además a descartarlos al
  construir la `Source` (hallazgo G), para que el dato sucio no viaje en el `Report`.
  **"Orden de las hipótesis en el reporte"** suma el respaldo del consenso como criterio
  de desempate, después del nivel efectivo y antes de la cantidad de fuentes
  verificadas: entre dos hipótesis respaldadas del mismo nivel, la que sostienen tres
  agentes va antes que la que sostiene uno.

## Impact

- **Código nuevo**: `backend/agents/agent_04_arbiter.py`,
  `backend/pipeline/consensus.py` (agrupación determinista, contradicciones y
  ensamblado del resultado), `backend/models/arbitration.py`,
  `tests/test_agent_04_arbiter.py`, `tests/test_consensus.py`,
  `scripts/demo_agente04.py`.
- **Código modificado**: `backend/agents/base_agent.py` (saneamiento del hallazgo G y
  el método de recitación), `backend/pipeline/orchestrator.py` (conservar los
  `RetrievedArticle`), `backend/pipeline/debate.py` (dejar de consolidar a mano:
  `_detect_divergences()` pasa al Árbitro), `backend/pipeline/evidence.py` (criterio de
  orden), `backend/pipeline/verification.py` (re-verificación acotada a un subconjunto),
  `backend/pipeline/trial_matching.py` (adaptador desde el consenso),
  `backend/pipeline/report_builder.py`, `backend/pipeline/pdf_exporter.py`,
  `backend/models/report.py`, `backend/api/router.py`, `backend/api/schemas.py`,
  `frontend/src/lib/types.ts`, `frontend/src/app/report/page.tsx`,
  `frontend/src/app/analyzing/page.tsx`, `tests/test_api.py`, `tests/test_evidence.py`,
  `tests/test_report_builder.py`, `tests/test_pdf_exporter.py`, `tests/test_debate.py`.
- **APIs externas**: PubMed suma una segunda consulta `esummary` por análisis (la
  re-verificación de las hipótesis recitadas), en batch y sólo si hubo recitación. Groq
  suma 2 llamadas fijas (agrupación y veredictos) más 1 por agente que tenga hipótesis
  a recitar, sujetas al límite de 12k TPM del tier gratuito.
- **Latencia**: el análisis completo pasa de ~5 min a ~7 min estimados. La navegación de
  ensayos deja de solaparse con la verificación y se suma la Ronda 5. Es el costo
  aceptado al elegir que el Agente 05 busque sobre el consenso.
- **Contrato JSON**: sólo aditivo; un cliente que ignore los campos nuevos sigue
  andando, y un reporte generado antes de este cambio sigue validando.
- **Cambios en paralelo**: #53 (Agente 05) y #54 (EBM) ya están en `develop`. Este
  cambio toca `trial_matching.build_navigation_input()` pero no el Agente 05.
  El reparto del 2026-09-15 asigna `verification.py`, `evidence.py` y el paso 7 del
  router a Matías, así que no hay colisión con las tarjetas de Facundo (#71, ingesta y
  genómica) ni con las de Fede (#74, #76, #77, #78: RAG, frontend y PDF) — salvo
  `pdf_exporter.py`, que Fede toca en #78: va coordinado o después.
- **Documentación**: `.claude/architecture.md` (flujo, Ronda 5 y el criterio de parada,
  que hoy describe algo inalcanzable), `.claude/CLAUDE.md`, `.claude/backlog.md`
  (tarea 9 y hallazgo G).
