## Context

El `StructuredReport` (`backend/api/schemas.py`) ya trae lo que hay que medir:

- Por hipótesis (`RankedHypothesis`): `rank`, `status` (`respaldada`/`pendiente`/`especulativa`), `verified_sources`, `evidence_level` (efectivo), `declared_evidence_level` y `supporting_agents` (nombres de agentes).
- `verification` (`VerificationSummary`): conteos de fuentes deduplicadas por veredicto y `estado` de la verificación (tarjeta #91).
- `arbitration` (`ArbitrationOut`, opcional): `cited_sources`, `rag_overlap`, `contradictions` y `recitation`.
- `metadata`: `mock` y `disclaimer`.
- `clinical_trials`.

Ninguna de estas cifras se combina hoy en un juicio. El reporte real se arma con `build_export()`; `scripts/medir_costos.py` ya lo construye en su pasada base pero no lo guarda.

## Goals / Non-Goals

**Goals:**
- Una función pura que convierte un `StructuredReport` en una evaluación, testeable con reportes sintéticos.
- Que la #58 pueda evaluar la corrida real sin escribir código nuevo.

**Non-Goals:**
- Mostrar la evaluación en `/report` o en el PDF.
- Cobertura clínica (si las hipótesis abordan los hallazgos del caso): queda para la #60.
- Calibrar los umbrales: es trabajo de la #58.

## Decisions

### D1 — Módulo puro en `backend/pipeline/calidad.py`, fuera del pipeline

`evaluar(reporte: StructuredReport, criterios: Criterios = CRITERIOS) -> EvaluacionCalidad`, sin I/O. La evaluación es una herramienta de validación del equipo, no parte del producto: no se llama desde `router.py` ni cambia el contrato de `POST /api/analyze`.

*Alternativa descartada:* agregar la evaluación al `StructuredReport`. Cambiaría un contrato que consumen el frontend y el PDF, y mostrarle al médico un "no cumple" sobre umbrales provisionales confunde más de lo que ayuda.

### D2 — Fuentes desde `VerificationSummary`, hipótesis desde la lista

La precisión de citas usa los conteos de `verification` (fuentes deduplicadas por PMID). Si se contara desde `hypotheses[].sources`, una cita repetida en dos hipótesis pesaría doble. La cobertura y la sobredeclaración se calculan recorriendo `hypotheses`: la sobredeclaración compara `declared_evidence_level` con `evidence_level`, y una hipótesis sin nivel declarado no cuenta como sobredeclarada. Se calcula en vez de leer `hipotesis_topeadas`, porque ese contador sale de la misma regla y así el detalle por hipótesis y la métrica no se desincronizan.

### D3 — Criterios como datos versionados

`Criterios` es un modelo Pydantic congelado con `version` (`"2026-11-provisional"`) y los tres umbrales; `CRITERIOS` es la instancia vigente. La evaluación copia los criterios que usó. Recalibrar en la #58 es cambiar esa instancia y su versión, sin tocar la lógica.

*Alternativa descartada:* umbrales por variable de entorno. Un umbral que cambia según la máquina vuelve irreproducible la evaluación, que es lo que se busca evitar.

### D4 — Tres niveles con efecto distinto en el veredicto

- **Evaluabilidad** (mock, estado de la verificación): si falla, el veredicto es `no_evaluable`. Las métricas se calculan igual, porque sirven para ensayar la #58 en modo mock.
- **Consistencia** (hipótesis presentes, aviso de no diagnóstico, ningún nivel I/II sin fuente verificada): si falla, `no_cumple`. El último ya lo garantiza `evidence.py`; medirlo detecta una regresión.
- **Métricas**: si falla una, `no_cumple`.

Una métrica sin datos (denominador cero) es `None` en el valor y `cumple=False`: el reporte no puede aprobar lo que no se pudo medir.

### D5 — El script lee un archivo; `medir_costos.py` guarda el reporte

`scripts/evaluar_reporte.py <reporte.json>` valida el archivo con `StructuredReport.model_validate_json()`, imprime una tabla, escribe `evaluacion.json` y `evaluacion.txt` en `output/evaluacion_calidad/<nombre-del-reporte>/` y sale con 0/1/2/3. Para que la #58 tenga de dónde sacar el JSON, `scripts/medir_costos.py` suma una salida, `reporte.json`, con el `StructuredReport` de la pasada base y su `executive_summary`. Es aditivo: ninguna salida existente cambia.

*Alternativa descartada:* que el script llame a `POST /api/analyze`. Exige una sesión de médico verificado y gasta cuota en cada evaluación; separar generar de evaluar permite evaluar la misma corrida todas las veces que haga falta.

### D6 — Sin texto clínico en la evaluación

`EvaluacionCalidad` no tiene ningún campo de texto libre que venga del reporte. Los motivos son frases armadas por el evaluador ("Precisión de citas 0,40 < 0,70"), y el detalle por hipótesis usa `rank`. Un test lo comprueba buscando el texto de las hipótesis del caso base en la evaluación serializada.

## Risks / Trade-offs

- [Los umbrales provisionales pueden ser demasiado exigentes o laxos para un caso de enfermedad rara, donde la literatura de nivel I es escasa] → Están marcados como provisionales, la sobredeclaración no exige niveles altos (solo que el agente no declare más de lo que respalda) y la #58 los recalibra con datos.
- [La precisión de citas no distingue una cita discordante leve de una inventada] → La verificación ya decide qué es discordante (`_title_match_score`); la evaluación no reabre ese juicio.
- [Un reporte puede `cumplir` y aun así ser clínicamente pobre] → Es explícito en el alcance: la calidad clínica la juzga el médico en la #60.
