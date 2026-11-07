## MODIFIED Requirements

### Requirement: Indicadores informativos

La evaluación SHALL incluir, sin umbral ni efecto en el veredicto:

- Distribución de niveles de evidencia efectivos (I, II, III).
- Hipótesis respaldadas, pendientes y especulativas.
- Fuentes verificadas, discordantes, inexistentes, sin PMID y no verificables.
- Citas descartadas por no venir de la literatura que ofreció el RAG.
- Anclaje en el RAG: citas que coinciden con artículos que el RAG ofreció, sobre el total de citas del arbitraje.
- Recitación (Ronda 5): si corrió, cuántas hipótesis entraron y cuántas mejoraron.
- Contradicciones detectadas por el Árbitro.
- Agentes que aportaron al menos una hipótesis al consenso.
- Ensayos clínicos encontrados.

Un indicador cuyo dato no está en el reporte (por ejemplo, un reporte sin arbitraje) MUST aparecer como no disponible, no como cero.

#### Scenario: Reporte sin arbitraje
- **WHEN** se evalúa un reporte que no trae la sección de arbitraje
- **THEN** el anclaje en el RAG, la recitación y las contradicciones aparecen como no disponibles

#### Scenario: Citas descartadas por no venir del RAG
- **WHEN** se evalúa un reporte que informa 23 citas descartadas por no venir del RAG
- **THEN** el indicador de citas fuera del RAG vale 23 y el veredicto no cambia por ese dato

#### Scenario: Reporte anterior sin el conteo de citas fuera del RAG
- **WHEN** se evalúa un reporte generado antes de que existiera ese conteo
- **THEN** el indicador de citas fuera del RAG aparece como no disponible
