## Context

Ver `proposal.md — Why` para la motivación.

El pipeline serializado en `backend/api/router.py` termina hoy en el paso 8 (Agente 05)
seguido de `build_export()`. El `StructuredReport` que devuelve `build_export()` es
completamente determinístico: hipótesis, veredictos, ensayos, bibliografía y métricas de
verificación ya están calculados cuando el Sintetizador actúa.

El patrón de integración de los agentes 04 y 05 es la referencia:
- Cada agente tiene una función segura (`_arbitrate_safe`, `_navigate_trials_safe`) que
  atrapa excepciones y devuelve un resultado degradado en lugar de propagar el error.
- El resultado se pasa a `build_export()` como argumento keyword; los campos son nullable
  y `None` representa "reporte anterior a ese agente" (retrocompatibilidad).

El Agente 06 sigue exactamente ese patrón.

## Goals / Non-Goals

**Goals**
- Un `executive_summary: str | None` en `StructuredReport`, producido por el LLM una
  vez que el reporte está completo.
- Guarda anti-invención: el texto se descarta si cita PMID, NCT o gen fuera del reporte.
- Modo mock funcional con respuesta grabada.
- Retrocompatibilidad total: un reporte sin el campo valida igual que antes.

**Non-Goals**
- El Sintetizador no reemplaza `report_builder.py`; lo envuelve.
- No se expone `synthesize()` como endpoint propio.
- No se agrega lógica de reintento si la guarda descarta el resumen; queda `None`.

## Decisions

### D1 — `synthesize()` recibe `StructuredReport`, no `Report`

El `StructuredReport` ya viene con hipótesis priorizadas, veredictos del Árbitro,
ensayos y PMIDs verificados. Pasarle el `Report` interno obligaría al agente a
replicar parte de la lógica de selección de `report_builder.py`.

Alternativa descartada: pasar el `Report` interno + los artefactos intermedios.
Inconveniente: el Sintetizador tiene que saber qué hipótesis "ganaron"; eso ya lo
decidió el builder.

### D2 — La guarda opera sobre el texto en lenguaje natural, no sobre el JSON

El LLM recibe el `StructuredReport` serializado como contexto y devuelve texto libre.
La guarda extrae con regex los patrones `\d{7,8}` (PMID), `NCT\d{8}` (ensayo) y
`\b[A-Z][A-Z0-9]{1,7}\b` (símbolo génico — mismo patrón que `_GENE_PATTERN` del
extractor de biomarcadores), y verifica cada uno contra las colecciones del reporte.

Alternativa descartada: pedir al LLM un JSON estructurado con el resumen y una lista
de referencias. Inconveniente: añade complejidad de parseo y un punto de falla extra;
el resumen es texto libre por diseño.

### D3 — Orden en el pipeline: después de `build_export()`

`synthesize()` recibe el `StructuredReport` ya construido. El paso 9 es:
```
structured = build_export(...)
structured.executive_summary = await _synthesize_safe(structured)
return structured
```

Alternativa: correr el Sintetizador antes de `build_export()` y pasar el resultado.
Inconveniente: `build_export()` no tiene parámetro `executive_summary`; habría que
agregarlo o hacer que el Sintetizador reciba los artefactos internos (ver D1).

### D4 — La respuesta mock se graba, no se escribe a mano

El archivo `backend/mock/grabadas.json` ya tiene 12 tareas grabadas con
`scripts/medir_costos.py --grabar` de una corrida real. La tarea `agente06_sintesis`
tiene que seguir el mismo proceso: añadir la tarea a `TASK_BUDGETS` y a la lista de
tareas grabables, correr `--grabar` una vez y commitear el resultado.

Alternativa descartada: escribir un resumen a mano. Inconveniente: el modo mock
dejaría de reflejar el comportamiento real del modelo.

## Risks / Trade-offs

- **Costo de tokens**: +1 llamada ~4 k tokens de entrada por análisis. Dentro del límite de
  2 casos/día. → Medirlo tras la primera corrida real y ajustar el techo si corresponde.
- **Guarda demasiado estricta**: el regex de genes puede capturar siglas clínicas que no
  son genes (p.ej. "CMT"). `_NON_GENE_TERMS` del extractor de biomarcadores ya tiene
  esa lista; reutilizarla. → Importar `_NON_GENE_TERMS` desde `biomarker_extractor.py`.
- **Latencia**: el Sintetizador corre después de `build_export()`, en serie. No es
  paralelizable porque necesita el reporte completo. → Impacto ~5–10 s extra aceptable.

## Migration Plan

1. Mergear el PR; `executive_summary` queda `None` en todos los análisis existentes.
2. Correr `scripts/medir_costos.py --grabar` una vez en real para grabar la respuesta
   mock antes del primer análisis en producción con el agente activo.
3. No hay rollback especial: revertir el PR o desactivar el agente deja el campo en `None`.

## Open Questions

- ¿El PDF muestra el resumen en una página de portada o al inicio de las hipótesis?
  Decisión estética; no afecta la spec ni el contrato del JSON. Se decide al implementar
  `pdf_exporter.py`.
