# sintetizador Specification

## Purpose
Definir qué produce el Agente 06 (Sintetizador), bajo qué condiciones lo descarta y cómo
se integra al reporte exportado, sin que el agente tome ninguna decisión sobre los datos
ya producidos por el pipeline determinístico.

## Requirements

### Requirement: El Sintetizador genera un resumen ejecutivo en prosa

El Agente 06 SHALL producir un `executive_summary` en prosa concisa (máximo 5 oraciones)
que narrativice el resultado clínico del reporte para el médico responsable.

El resumen SHALL basarse exclusivamente en la información ya presente en el
`StructuredReport` que recibe: hipótesis priorizadas, nivel de evidencia, veredictos del
Árbitro, ensayos encontrados y métricas de verificación.

El Sintetizador SHALL NOT tomar decisiones sobre los datos: no agrupa hipótesis, no
modifica niveles de evidencia, no introduce referencias bibliográficas nuevas y no
descarta ni añade ensayos clínicos.

#### Scenario: Resumen producido correctamente
- **WHEN** el pipeline completó todos los pasos anteriores y el LLM responde con un resumen válido
- **THEN** `StructuredReport.executive_summary` contiene el texto en prosa y no es `None`

#### Scenario: LLM no disponible
- **WHEN** la llamada al LLM falla por error de red o cuota agotada
- **THEN** `executive_summary` queda `None`, el reporte se entrega igual y el error se registra

### Requirement: Guarda anti-invención

El Sintetizador SHALL descartar el resumen completo si contiene cualquier PMID, número
NCT o símbolo génico que no esté presente en el `StructuredReport` recibido.

#### Scenario: Resumen con PMID inventado
- **WHEN** el LLM incluye en el resumen un PMID que no aparece en ninguna fuente del reporte
- **THEN** `executive_summary` queda `None` y se registra el PMID infractor

#### Scenario: Resumen con NCT inventado
- **WHEN** el LLM incluye un número NCT ausente en los ensayos del reporte
- **THEN** `executive_summary` queda `None` y se registra el NCT infractor

#### Scenario: Resumen limpio
- **WHEN** el resumen no cita ningún PMID, NCT ni gen fuera del reporte
- **THEN** el resumen se acepta y se asigna a `executive_summary`

### Requirement: Retrocompatibilidad del campo en el reporte

`StructuredReport.executive_summary` SHALL ser un campo nullable con valor por defecto
`None`, de modo que un reporte generado antes del Agente 06 valide correctamente y los
clientes que no lo consuman sigan funcionando sin cambios.

#### Scenario: Reporte previo al Agente 06
- **WHEN** se lee un reporte sin el campo `executive_summary`
- **THEN** el campo toma valor `None` y el cliente no falla

#### Scenario: Frontend con Agente 06 activo
- **WHEN** `executive_summary` no es `None`
- **THEN** el frontend muestra el resumen en la vista del reporte

#### Scenario: Frontend sin Agente 06
- **WHEN** `executive_summary` es `None`
- **THEN** el frontend omite la sección sin mostrar error ni placeholder vacío

### Requirement: Modo mock funcional

El Agente 06 SHALL funcionar con `NEXUS_MOCK_LLM=1` sin realizar ninguna llamada a Groq,
usando la respuesta grabada en `backend/mock/grabadas.json` bajo la clave
`agente06_sintesis`.

#### Scenario: Mock activo
- **WHEN** `NEXUS_MOCK_LLM=1` está configurado y se llama a `synthesize()`
- **THEN** se devuelve la respuesta grabada sin llamar al proveedor LLM

### Requirement: Tarea registrada en el presupuesto de tokens

La llamada al LLM del Sintetizador SHALL declarar la tarea `"agente06_sintesis"` y el
techo SHALL ser de al menos 4096 tokens, igual al resto de las tareas de razonamiento
clínico, hasta que una medición real justifique ajustarlo.

#### Scenario: Tarea en model_tasks
- **WHEN** el Sintetizador llama a `_call_llm()`
- **THEN** usa `task="agente06_sintesis"` y el techo es ≥ 4096
