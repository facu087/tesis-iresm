## Context

Recorrido actual de una cita (ver proposal.md, "Why"):

- **Ronda 1** (`pipeline/orchestrator.py`): el contexto es la síntesis PICO más el bloque del RAG (`PubMedRetriever.get_context_with_articles(rag_query, max_results=5)`), que cierra con "Cuando cites estas referencias, usá el PMID exacto". Los `SYSTEM_PROMPT` de los Agentes 01, 02 y 03 no mencionan ese bloque y su ejemplo de formato trae `"pmid": "12345678"`.
- **Rondas 2 a 4** (`pipeline/debate.py`): el contexto es solo `pico.format_for_agents(case.pico)`, sin la literatura. `BaseAgent.revise()` arma el pedido con ese contexto, las hipótesis propias y las críticas.
- **Cierre del debate**: `run_debate()` junta las hipótesis de la Ronda 4 en un `Report` que ya propaga `retrieved_articles`.
- **Verificación y Ronda 5**: `verify_report_sources()` consulta PubMed por cada PMID; la recitación usa `recitation.allowed_pmids()` y `validate_recited()` para aceptar solo PMIDs ofrecidos.

El mismo `run_debate()` lo usan `router.analyze()` y `scripts/medir_costos.py`, así que un cambio ahí cubre los dos.

## Goals / Non-Goals

**Goals:**
- Que ninguna cita con PMID llegue a la verificación sin haber sido ofrecida por el RAG.
- Que los agentes tengan la literatura a mano en todas las rondas en que citan.

**Non-Goals:**
- Mejorar la relevancia de la búsqueda semántica (consulta, modelo de embeddings, umbral). La corrida grabada trae artículos de neuropatía óptica de Leber que no tienen que ver con el caso; el umbral sigue en 0,55 y se revisa con los datos de la corrida de verificación.
- Mostrar las citas descartadas en `/report` o en el PDF.
- Cambiar las métricas de la #59.

## Decisions

### D1 — Un único filtro al cerrar el debate, reusando la regla de la Ronda 5

`run_debate()` aplica `recitation.validate_recited()` con `recitation.allowed_pmids(round_1_report.retrieved_articles)` a las fuentes de cada hipótesis final, y guarda el total descartado en `Report.citas_fuera_del_rag`. Un solo punto, después de la Ronda 4, cubre las citas de todas las rondas y deja la verificación sin consultas inútiles.

`validate_recited()` hoy descarta también las fuentes sin PMID, que en la recitación no sirven. Acá se conservan (spec: "Fuentes sin PMID"), así que el filtro separa primero las fuentes sin PMID, filtra las otras y las vuelve a juntar en el orden original.

*Alternativa descartada:* filtrar en cada ronda. Multiplica los puntos de control y las críticas de la Ronda 2 citan hipótesis con fuentes que igual se filtran al final.

### D2 — El conteo viaja en `Report` y llega al resumen de verificación

`Report` suma `citas_fuera_del_rag: int = 0` (modelo interno). `build_export()` lo copia a `VerificationSummary.fuera_del_rag: int | None = None`. En el `StructuredReport`, `None` significa "reporte anterior al cambio" y `0` significa "se aplicó el filtro y no descartó nada": el evaluador muestra el primero como no disponible (spec de `criterios-calidad-reporte`).

### D3 — La literatura en las revisiones, en formato corto

`run_debate()` arma una vez la lista de artículos ofrecidos con una línea por artículo (`[PMID: …] título (año)`) y se la pasa a `_round_revision()`, que la agrega al contexto de cada `revise()`. Sin el resumen: con 10 artículos son unos 1.200 caracteres por pedido, contra unos 6.000 con resumen, y se repite en 6 revisiones. El formato de una línea sale de una función nueva en `recitation.py` (`lista_de_literatura()`), al lado de `allowed_pmids()`, para que la regla y la lista vivan juntas. La Ronda 2 (críticas) no la recibe: no cita fuentes.

### D4 — Prompts: regla explícita y sin PMID de relleno

- En los `SYSTEM_PROMPT` de los Agentes 01, 02 y 03, la regla de citas pasa a ser: "Solo podés citar PMIDs que figuren en el bloque LITERATURA CIENTÍFICA del contexto. Si ningún artículo de ese bloque respalda la hipótesis, dejá `sources` vacío y usá `evidence_level: "III"`." El ejemplo de formato muestra `"pmid": "PMID del bloque de literatura"`.
- `BaseAgent.revise()` suma la misma regla al pedido de revisión.
- El bloque de `get_context_with_articles()` cierra con "OBLIGATORIO: citá solo PMIDs de esta lista. Cualquier otro PMID se descarta."

Los tests verifican el texto de los prompts (presencia de la regla, ausencia de un PMID numérico de ejemplo), no la conducta del modelo: esa se mide con la corrida real.

### D5 — Tope de 10 artículos en una constante

`orchestrator.py` pasa `max_results=MAX_ARTICULOS_RAG` (10), con una constante en el módulo. El umbral de relevancia no cambia; si menos de 10 lo superan, se ofrecen menos.

### D6 — Modo mock: el filtro se aplica igual

El filtro es determinista y corre también en modo mock: es la condición para que el mock sirva para desarrollar sobre el pipeline real (`modo-mock-pipeline`). Con las grabaciones actuales, la mayoría de las citas de las Rondas 1 a 4 se descartan y más hipótesis entran en la recitación. Los tests de modo mock que fijan conteos se ajustan a lo que produce el pipeline con el filtro. Las grabaciones se regeneran con `scripts/medir_costos.py --grabar` en la corrida de verificación (tarea separada, gasta cuota).

## Risks / Trade-offs

- [Con pocos artículos ofrecidos, un agente puede citar un artículo ofrecido que no respalda la hipótesis, solo para tener fuente] → La verificación confirma que el PMID corresponde al título, no que respalde la hipótesis. La instrucción dice que sin respaldo va sin fuentes; la revisión con el médico (#60) lo juzga. Queda como limitación documentada.
- [Se pierden las citas de memoria correctas (2 de 25 en la #58)] → Es el costo aceptado de la opción estricta. La recitación de la Ronda 5 recupera respaldo con literatura real.
- [La precisión de citas de la #59 sube porque las citas inventadas ya no llegan a la verificación] → El indicador "citas fuera del RAG" deja a la vista cuántas se descartaron; la cobertura de respaldo sigue midiendo cuántas hipótesis quedan respaldadas.
- [Más texto en los prompts] → Unos 3.000 caracteres más por agente en la Ronda 1 y unos 1.200 en cada revisión; se mide en la corrida de verificación con `medir_costos.py`.
