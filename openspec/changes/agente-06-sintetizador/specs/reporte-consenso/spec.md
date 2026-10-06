# reporte-consenso Specification (delta)

## ADDED Requirements

### Requirement: El reporte expone el resumen ejecutivo del Sintetizador

`StructuredReport` SHALL incluir el campo `executive_summary: str | None` con valor por
defecto `None`.

Cuando el Agente 06 produce un resumen válido, el campo SHALL contener el texto en prosa.
Cuando el agente no está disponible o la guarda anti-invención descarta el texto, el campo
SHALL ser `None`.

El campo SHALL ser aditivo: su ausencia en reportes anteriores al Agente 06 no invalida
el reporte ni rompe ningún cliente existente.

#### Scenario: Campo presente en el JSON exportado
- **WHEN** el Agente 06 produjo un resumen válido
- **THEN** `StructuredReport.executive_summary` es una cadena no vacía en el JSON de respuesta
  del endpoint `POST /api/analyze`

#### Scenario: Campo ausente o nulo
- **WHEN** el Agente 06 no está disponible o descartó el resumen
- **THEN** `StructuredReport.executive_summary` es `null` en el JSON y el contrato
  del endpoint sigue siendo válido
