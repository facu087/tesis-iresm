## Purpose

Evaluar un reporte generado por NEXUS contra criterios objetivos y reproducibles de cobertura, fuentes verificadas y nivel de evidencia, para que la validación del sistema se mida con números y no con opiniones.

## ADDED Requirements

### Requirement: Evaluación determinista de un reporte

El sistema SHALL evaluar un reporte estructurado (el mismo JSON que devuelve `POST /api/analyze`) sin consultar la red ni llamar a un modelo de lenguaje. Dos evaluaciones del mismo reporte con la misma versión de criterios MUST producir el mismo resultado.

#### Scenario: Mismo reporte, mismo resultado
- **WHEN** se evalúa dos veces el mismo reporte con la misma versión de criterios
- **THEN** las dos evaluaciones son idénticas

#### Scenario: Sin red ni modelo
- **WHEN** se evalúa un reporte con la red bloqueada y sin `GROQ_API_KEY`
- **THEN** la evaluación se completa igual

### Requirement: Requisitos para que el reporte sea evaluable

Un reporte SHALL considerarse **no evaluable** cuando cumple alguna de estas condiciones:

- Fue generado en modo mock (`metadata.mock` verdadero).
- El estado de la verificación bibliográfica es `parcial` o `no_disponible`, o el reporte no informa el estado.

Un reporte no evaluable MUST igual mostrar todas sus métricas e indicadores, para que el equipo vea qué dio, pero su veredicto es `no_evaluable` y la evaluación MUST decir qué requisito falló.

#### Scenario: Reporte en modo mock
- **WHEN** se evalúa un reporte con `metadata.mock` verdadero
- **THEN** el veredicto es `no_evaluable`, el motivo dice que el reporte es de modo mock y las métricas se calculan igual

#### Scenario: Verificación caída
- **WHEN** se evalúa un reporte cuya verificación quedó `no_disponible` o `parcial`
- **THEN** el veredicto es `no_evaluable` y el motivo nombra el estado de la verificación

#### Scenario: Reporte anterior sin estado de verificación
- **WHEN** se evalúa un reporte que no informa el estado de la verificación
- **THEN** el veredicto es `no_evaluable`

#### Scenario: Ninguna fuente con PMID
- **WHEN** el estado de la verificación es `sin_consulta`
- **THEN** el reporte es evaluable, y la métrica de precisión de citas queda sin datos

### Requirement: Requisitos de consistencia del reporte

Un reporte evaluable SHALL cumplir estas condiciones; si falla alguna, el veredicto es `no_cumple` aunque las métricas pasen:

- Tiene al menos una hipótesis.
- Lleva el aviso de que NEXUS no emite diagnósticos (`metadata.disclaimer` no vacío).
- Ninguna hipótesis tiene nivel de evidencia efectivo I o II sin al menos una fuente verificada.

#### Scenario: Reporte sin hipótesis
- **WHEN** se evalúa un reporte evaluable sin hipótesis
- **THEN** el veredicto es `no_cumple` y el motivo dice que no hay hipótesis

#### Scenario: Nivel alto sin respaldo
- **WHEN** una hipótesis tiene nivel efectivo II y cero fuentes verificadas
- **THEN** el veredicto es `no_cumple` y el motivo identifica la hipótesis por su posición en el ranking

#### Scenario: Falta el aviso de no diagnóstico
- **WHEN** el reporte trae `metadata.disclaimer` vacío
- **THEN** el veredicto es `no_cumple`

### Requirement: Métricas con umbral

La evaluación SHALL calcular estas tres métricas, una por dimensión de calidad, y compararlas con su umbral:

| Dimensión | Métrica | Cálculo | Pasa si |
|-----------|---------|---------|---------|
| Cobertura | Cobertura de respaldo | hipótesis `respaldadas` / total de hipótesis | ≥ umbral |
| Fuentes verificadas | Precisión de citas | fuentes `verificadas` / (`verificadas` + `discordantes` + `inexistentes`) | ≥ umbral |
| Nivel de evidencia | Sobredeclaración | hipótesis con nivel efectivo por debajo del declarado / total de hipótesis | ≤ umbral |

La comparación MUST hacerse sobre el valor sin redondear. Una métrica cuyo denominador es cero MUST quedar **sin datos** y contar como no cumplida: un reporte sin citas que PubMed pueda contrastar no aprueba la precisión de citas.

#### Scenario: Cobertura en el umbral exacto
- **WHEN** la cobertura de respaldo es exactamente igual al umbral
- **THEN** la métrica se cumple

#### Scenario: Precisión con citas inventadas
- **WHEN** de 10 citas contrastadas, 4 son verificadas, 5 discordantes y 1 inexistente
- **THEN** la precisión de citas es 0,4 y, con el umbral provisional, no se cumple

#### Scenario: Sin citas contrastables
- **WHEN** ninguna fuente citada pudo contrastarse contra PubMed
- **THEN** la precisión de citas queda sin datos y no se cumple

#### Scenario: Agentes que sobredeclaran
- **WHEN** 6 de 10 hipótesis quedaron con nivel efectivo por debajo del declarado
- **THEN** la sobredeclaración es 0,6 y, con el umbral provisional, no se cumple

### Requirement: Umbrales versionados y provisionales

Los umbrales SHALL vivir en una única tabla con una versión de criterios. Los valores iniciales MUST ser:

- Cobertura de respaldo: ≥ 0,50
- Precisión de citas: ≥ 0,70
- Sobredeclaración: ≤ 0,50

Estos valores son provisionales: se recalibran con la corrida real de la validación end-to-end (tarjeta #58). Toda evaluación MUST incluir la versión de criterios y los umbrales con que se calculó, para que un cambio posterior de umbrales no reinterprete resultados anteriores.

#### Scenario: La evaluación declara sus criterios
- **WHEN** se evalúa cualquier reporte
- **THEN** el resultado incluye la versión de criterios y el valor de cada umbral usado

### Requirement: Indicadores informativos

La evaluación SHALL incluir, sin umbral ni efecto en el veredicto:

- Distribución de niveles de evidencia efectivos (I, II, III).
- Hipótesis respaldadas, pendientes y especulativas.
- Fuentes verificadas, discordantes, inexistentes, sin PMID y no verificables.
- Anclaje en el RAG: citas que coinciden con artículos que el RAG ofreció, sobre el total de citas del arbitraje.
- Recitación (Ronda 5): si corrió, cuántas hipótesis entraron y cuántas mejoraron.
- Contradicciones detectadas por el Árbitro.
- Agentes que aportaron al menos una hipótesis al consenso.
- Ensayos clínicos encontrados.

Un indicador cuyo dato no está en el reporte (por ejemplo, un reporte sin arbitraje) MUST aparecer como no disponible, no como cero.

#### Scenario: Reporte sin arbitraje
- **WHEN** se evalúa un reporte que no trae la sección de arbitraje
- **THEN** el anclaje en el RAG, la recitación y las contradicciones aparecen como no disponibles

### Requirement: Veredicto global

La evaluación SHALL devolver exactamente uno de estos veredictos:

- `no_evaluable`: falló un requisito para que el reporte sea evaluable.
- `no_cumple`: el reporte es evaluable y falló un requisito de consistencia o al menos una métrica.
- `cumple`: el reporte es evaluable, cumple los requisitos de consistencia y las tres métricas.

El veredicto MUST ir acompañado de la lista de motivos (cada requisito o métrica que falló).

#### Scenario: Todo en orden
- **WHEN** un reporte evaluable cumple los requisitos de consistencia y las tres métricas
- **THEN** el veredicto es `cumple` y la lista de motivos está vacía

#### Scenario: Una métrica falla
- **WHEN** un reporte evaluable cumple los requisitos de consistencia pero la precisión de citas no llega al umbral
- **THEN** el veredicto es `no_cumple` y el motivo nombra la precisión de citas con su valor y su umbral

### Requirement: La evaluación no expone texto clínico

La evaluación SHALL contener solo conteos, proporciones, niveles, estados y la posición de cada hipótesis en el ranking. MUST NOT copiar el texto de las hipótesis, su fundamentación, el resumen del caso ni el resumen ejecutivo.

#### Scenario: Detalle por hipótesis
- **WHEN** la evaluación lista el detalle por hipótesis
- **THEN** cada fila identifica la hipótesis por su posición en el ranking, con su estado, nivel declarado, nivel efectivo y fuentes verificadas, sin su texto

### Requirement: Evaluar un reporte guardado desde la línea de comandos

El equipo SHALL poder evaluar un reporte guardado en un archivo JSON con un comando, que imprime la evaluación legible, guarda la evaluación completa en `output/evaluacion_calidad/` y termina con un código de salida según el veredicto:

- `0`: `cumple`
- `1`: `no_cumple`
- `2`: `no_evaluable`
- `3`: el archivo no existe, no es JSON o no es un reporte válido

#### Scenario: Reporte que cumple
- **WHEN** se evalúa un archivo con un reporte que cumple
- **THEN** el comando imprime la evaluación, guarda el resultado y sale con código 0

#### Scenario: Archivo inválido
- **WHEN** se le pasa un archivo que no es un reporte válido
- **THEN** el comando explica por qué no lo pudo leer, no guarda nada y sale con código 3
