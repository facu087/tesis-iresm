## Purpose

Define cómo llegan al reporte exportado (JSON, vista web y PDF) los ensayos clínicos del
Agente 05, su compatibilidad orientativa, las enfermedades raras de Orphanet y el estado de
la búsqueda, manteniendo compatible el contrato que ya consumen el frontend y el PDF.

## ADDED Requirements

### Requirement: Contrato aditivo de ensayos clínicos
`StructuredReport.clinical_trials` SHALL seguir siendo una lista de ensayos con todos los campos
vigentes. Cada ensayo SHALL sumar campos opcionales con valor por defecto: `compatibility`
(`alta` | `media` | `baja` | `sin_evaluar`, por defecto `sin_evaluar`),
`compatibility_rationale` (texto o nulo), `criteria_to_verify` (lista, por defecto vacía),
`related_hypotheses` (lista, por defecto vacía) y `matched_terms` (lista, por defecto vacía).
Un reporte generado antes de este cambio MUST seguir siendo aceptado por `POST /api/report/pdf`.
El reporte SHALL conservar el orden de ensayos que entrega el Agente 05.

#### Scenario: Reporte previo sin campos nuevos
- **WHEN** se envía a `POST /api/report/pdf` un JSON cuyos ensayos no tienen `compatibility`
- **THEN** el endpoint responde HTTP 200 con el PDF y la sección de ensayos se imprime como antes de este cambio, sin etiquetas de compatibilidad

#### Scenario: Ensayo evaluado
- **WHEN** el Agente 05 evalúa un ensayo como `media` con fundamento y criterios a verificar
- **THEN** `POST /api/analyze` devuelve ese ensayo con `compatibility`, `compatibility_rationale` y `criteria_to_verify` completos

### Requirement: Enfermedades raras en el reporte
`StructuredReport` SHALL incluir `rare_diseases`, una lista (vacía por defecto) donde cada
elemento informa `orpha_code`, `name`, `url`, `hypothesis` (texto de la hipótesis marcada) y
`matched_term`. La sección MUST presentarse como "hipótesis que corresponden a una enfermedad
rara catalogada", nunca como diagnóstico del paciente.

#### Scenario: Hipótesis marcada como enfermedad rara
- **WHEN** el Agente 05 marca la hipótesis de amiloidosis hereditaria con ORPHA 271861
- **THEN** `rare_diseases` contiene un elemento con ese código, el nombre preferido, el enlace a orpha.net y el texto de la hipótesis

#### Scenario: Sin coincidencias
- **WHEN** ninguna hipótesis coincide con Orphanet
- **THEN** `rare_diseases` es una lista vacía

### Requirement: Estado de la búsqueda en el reporte
`StructuredReport` SHALL incluir `trial_search` con `estado_clinicaltrials`, `estado_orphanet`,
`planificacion`, `evaluacion`, `terminos_consultados` (términos en inglés enviados a las APIs),
`encontrados`, `excluidos_por_edad`, `excluidos_por_sexo` y `evaluaciones_descartadas`. En
reportes generados antes de este cambio `trial_search` MUST poder estar ausente o ser nulo.

#### Scenario: Reporte con búsqueda completa
- **WHEN** el Agente 05 termina con ClinicalTrials.gov disponible y Orphanet sin configurar
- **THEN** `trial_search` informa `estado_clinicaltrials: "ok"`, `estado_orphanet: "sin_configurar"` y los términos consultados

#### Scenario: Reporte previo sin estado de búsqueda
- **WHEN** un reporte no trae `trial_search`
- **THEN** el reporte se valida igual y `trial_search` queda nulo

### Requirement: Vista de ensayos en el frontend
La tab "Ensayos clínicos" SHALL mostrar, por ensayo, una etiqueta de compatibilidad, el
fundamento, los criterios a verificar y las hipótesis relacionadas cuando existan. La tab SHALL
mostrar un bloque de enfermedades raras de Orphanet con código y enlace cuando `rare_diseases`
no esté vacío, y SHALL mostrar la aclaración fija: "La compatibilidad es orientativa: la
elegibilidad la determina el equipo investigador de cada ensayo." Cuando no haya ensayos, el
mensaje MUST distinguir "no se encontraron ensayos" de "no se pudo consultar ClinicalTrials.gov".
Un reporte sin `trial_search` (generado antes de este cambio) MUST mostrarse como antes: sin
etiquetas de compatibilidad, sin aclaración y sin bloque de Orphanet.

#### Scenario: ClinicalTrials.gov no disponible
- **WHEN** el reporte trae 0 ensayos y `estado_clinicaltrials: "no_disponible"`
- **THEN** la tab indica que no se pudo consultar ClinicalTrials.gov, no que no existan ensayos

#### Scenario: Ensayo sin evaluar
- **WHEN** un ensayo tiene `compatibility: "sin_evaluar"`
- **THEN** la tab lo muestra con una etiqueta neutra "Sin evaluar" y sin fundamento

#### Scenario: Reporte previo
- **WHEN** el reporte no trae `trial_search` ni `rare_diseases` y sus ensayos no traen `compatibility`
- **THEN** la tab muestra los ensayos con los mismos datos que antes y sin errores de render

### Requirement: Ensayos en el PDF exportado
La sección "ENSAYOS CLÍNICOS ACTIVOS RELEVANTES" del PDF SHALL incluir por ensayo la
compatibilidad y los criterios a verificar, un apartado de enfermedades raras de Orphanet cuando
existan, la misma aclaración orientativa que el frontend y, si ClinicalTrials.gov no pudo
consultarse, un aviso explícito en lugar del texto "No se encontraron ensayos clínicos activos
relacionados." Un reporte sin `trial_search` MUST imprimirse como antes de este cambio.

#### Scenario: PDF con ensayos evaluados
- **WHEN** se exporta un reporte con un ensayo `alta` y una enfermedad rara marcada
- **THEN** el PDF contiene la etiqueta de compatibilidad, sus criterios a verificar, el código ORPHA con su enlace y la aclaración orientativa

#### Scenario: PDF con la API caída
- **WHEN** se exporta un reporte con 0 ensayos y `estado_clinicaltrials: "no_disponible"`
- **THEN** el PDF avisa que ClinicalTrials.gov no pudo consultarse
