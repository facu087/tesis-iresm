## Why

La validación end-to-end de la tarjeta #58 (2026-11-03) dio precisión de citas 0,08: de 25 PMIDs citados, 23 existen pero corresponden a otro artículo, y **ninguna** cita salió de los 5 artículos que el RAG ofreció. Los agentes citan de memoria. Las causas son tres: los prompts de las Rondas 1 a 4 no piden citar la literatura ofrecida (y el ejemplo de formato muestra un PMID de relleno), nada controla de dónde salen las citas antes de la Ronda 5, y el RAG ofrece solo 5 artículos. Esta tarjeta (#92) aplica la opción estricta que eligió el equipo: una cita con PMID solo vale si ese PMID lo ofreció el RAG.

## What Changes

- **Filtro estricto de citas** al cerrar el debate (después de la Ronda 4 y antes de la verificación): toda fuente con un PMID que el RAG no ofreció se descarta, sin consultar PubMed. Es la misma regla que ya aplica la recitación de la Ronda 5, ahora para todas las rondas. Ninguna hipótesis se descarta: la que se queda sin fuentes queda especulativa y entra en la recitación de la Ronda 5, que le ofrece la literatura real.
- Las fuentes **sin PMID** (por ejemplo, una guía clínica citada por sociedad y año) se conservan como hoy: nunca cuentan como verificadas.
- Si el RAG no ofreció ningún artículo, se descartan todas las citas con PMID. No hay excepción: sin literatura recuperada no hay forma de anclar una cita.
- El reporte informa **cuántas citas se descartaron** por no venir del RAG (campo opcional nuevo en el resumen de verificación). Es aditivo: un reporte anterior se sigue leyendo.
- **Prompts**: los Agentes 01, 02 y 03 reciben, en la generación y en la revisión, la regla explícita de citar solo PMIDs del bloque de literatura, y el ejemplo de formato deja de mostrar un PMID de relleno. El bloque del RAG pasa de "cuando cites estas referencias" a una instrucción obligatoria.
- **El debate ve la literatura**: hoy las Rondas 2 a 4 reciben solo la síntesis PICO, sin los artículos del RAG, así que al revisar los agentes no pueden citar lo ofrecido aunque quieran. Los pedidos de revisión pasan a listar los artículos ofrecidos (PMID, título y año, sin resumen).
- El RAG ofrece **hasta 10 artículos** en vez de 5, con el mismo umbral de relevancia.
- El evaluador de calidad (#59) suma el indicador **citas fuera del RAG**.

## Capabilities

### New Capabilities
- `citas-ancladas-rag`: qué citas acepta el pipeline (solo PMIDs ofrecidos por el RAG), cuándo se aplica el filtro, qué pasa con las fuentes sin PMID y sin literatura recuperada, cuántos artículos ofrece el RAG, qué se les indica a los agentes y cómo queda registrado en el reporte.

### Modified Capabilities
- `criterios-calidad-reporte`: el requirement "Indicadores informativos" suma las citas descartadas por no venir del RAG.

## Impact

- **Backend:** `backend/pipeline/debate.py` (filtro al consolidar y literatura en las revisiones), `backend/pipeline/recitation.py` (reuso de `allowed_pmids`/`validate_recited`), `backend/models/report.py` (conteo en `Report`), `backend/pipeline/report_builder.py` y `backend/api/schemas.py` (`VerificationSummary.fuera_del_rag`), `backend/pipeline/orchestrator.py` (tope del RAG), `backend/rag/retriever.py` (instrucción del bloque), `backend/agents/agent_01_literature.py`, `agent_02_genomics.py`, `agent_03_clinical.py` y `base_agent.py` (prompts de generación y revisión), `backend/pipeline/calidad.py` y `scripts/evaluar_reporte.py` (indicador).
- **Frontend y PDF:** sin cambios. El conteo queda en el JSON del reporte.
- **Modo mock:** las respuestas grabadas citan 30 PMIDs distintos y solo 5 fueron ofrecidos, así que el reporte del modo mock cambia (menos fuentes antes de la Ronda 5). Las grabaciones se regeneran en la corrida de verificación, que gasta cuota y requiere el OK del equipo.
- **Costo:** sin llamadas nuevas al LLM. Hasta 5 artículos más en el prompt de la Ronda 1 (unos 3.000 caracteres más por agente), una lista corta de artículos en cada una de las 6 revisiones y menos consultas a PubMed (las citas descartadas no se consultan).
- **Verificación:** una corrida real nueva evaluada con `scripts/evaluar_reporte.py` y comparada con la de la #58.
