## Why

La tarjeta #58 pide correr el pipeline completo con el caso base y "evaluar la calidad del output", pero hoy no hay una definición de calidad: cualquier juicio sobre el reporte es una opinión. El reporte ya contiene todo lo necesario para medirlo (estado bibliográfico por hipótesis, niveles EBM declarados y efectivos, resumen de la verificación, solapamiento con el RAG, recitación), aunque disperso y sin umbrales. Esta tarjeta (#59) fija criterios objetivos y reproducibles para que la #58 se mida contra números y la #60 (revisión con un médico) parta de un diagnóstico técnico ya hecho.

## What Changes

- Un **evaluador de calidad determinista**: recibe un `StructuredReport` (el JSON que devuelve `POST /api/analyze`) y devuelve una evaluación con tres partes:
  - **Requisitos de validez**: condiciones sin las cuales el reporte no se puede evaluar (no es modo mock, la verificación bibliográfica corrió completa, hay al menos una hipótesis, lleva el aviso de que no es un diagnóstico) y una de consistencia (ninguna hipótesis con nivel efectivo I o II sin fuente verificada).
  - **Métricas con umbral**, en las tres dimensiones de la tarjeta:
    - *Cobertura*: proporción de hipótesis respaldadas por al menos una fuente verificada.
    - *Fuentes verificadas*: precisión de las citas (verificadas sobre las que PubMed pudo contrastar) y tasa de citas inventadas (discordantes más inexistentes).
    - *Nivel de evidencia*: proporción de hipótesis cuyo nivel declarado por el agente quedó topeado (sobredeclaración).
  - **Indicadores informativos**, sin umbral: distribución de niveles efectivos I/II/III, anclaje de las citas en lo que ofreció el RAG, resultado de la recitación (Ronda 5), contradicciones, agentes que aportaron hipótesis y ensayos encontrados.
- Un **veredicto global**: `cumple`, `no_cumple` o `no_evaluable` (falló un requisito de validez de entrada).
- **Umbrales en una sola tabla**, versionada y marcada como provisional: se calibran con la corrida real de la #58, no se inventan ahora.
- Un **script** `scripts/evaluar_reporte.py <reporte.json>` que imprime la evaluación, guarda `.json` y `.txt` en `output/evaluacion_calidad/` y sale con un código distinto por veredicto.
- Un `scripts/demo_criterios_calidad.py` como evidencia para Trello: reportes sintéticos que muestran cada veredicto y cada métrica fallando, sin red ni cuota.
- Tests en `tests/` sobre el caso base (neuropatía axonal sensitivomotora, 42 años).

Queda **fuera** la cobertura clínica (si las hipótesis abordan los hallazgos relevantes del caso): no se puede medir de forma determinista sin que un modelo o una persona juzgue. Se deja para la revisión con el médico de la #60.

## Capabilities

### New Capabilities
- `criterios-calidad-reporte`: qué condiciones hacen evaluable un reporte, qué métricas se calculan sobre él, con qué umbrales, cómo se combinan en un veredicto y cómo se ejecuta la evaluación sobre un reporte guardado.

### Modified Capabilities
<!-- Ninguna: el evaluador lee el reporte, no cambia cómo se genera ni cómo se muestra. -->

## Impact

- **Backend:** módulo nuevo `backend/pipeline/calidad.py` (evaluador puro y tabla de umbrales). No toca el pipeline, el router ni el contrato de `POST /api/analyze`.
- **Scripts:** `scripts/evaluar_reporte.py` (herramienta para la #58) y `scripts/demo_criterios_calidad.py` (evidencia de la #59).
- **Frontend y PDF:** sin cambios. La evaluación no se muestra al médico: es una herramienta de validación del equipo.
- **Sin dependencias nuevas**, sin red y sin llamadas a un LLM: cero cuota de Groq.
- **Privacidad:** la evaluación guarda conteos, proporciones y textos de criterio; nunca copia el texto de las hipótesis ni del caso.
