## Purpose

Consulta a Orphanet desde el pipeline para señalar qué hipótesis de investigación
corresponden a enfermedades raras catalogadas, con su código ORPHA y enlace, priorizando
la precisión sobre la cobertura para no etiquetar mal una hipótesis clínica.

## ADDED Requirements

### Requirement: Búsqueda por nombre contra el servicio vigente de Orphanet
El sistema SHALL buscar entidades clínicas de Orphanet por nombre aproximado usando el
servicio público vigente (`api.orphacode.org`, recurso de nombre aproximado en inglés) y
SHALL devolver, por cada candidata, su código ORPHA, su nombre preferido y el enlace a su
ficha en orpha.net. El término de búsqueda MUST codificarse como segmento de URL.

#### Scenario: Término con coincidencias
- **WHEN** se busca `hereditary transthyretin amyloidosis`
- **THEN** la respuesta incluye candidatas con código y nombre preferido, entre ellas `271861` — `Hereditary ATTR amyloidosis`, con enlace `https://www.orpha.net/en/disease/detail/271861`

#### Scenario: Término con caracteres reservados de URL
- **WHEN** se busca un término que contiene `/` o `'`
- **THEN** la consulta se envía con el término codificado y no altera la ruta del recurso

### Requirement: Distinción entre "sin coincidencias" y error
El sistema SHALL tratar como "sin coincidencias" (lista vacía) únicamente la respuesta HTTP 404
cuyo cuerpo indica que la consulta no tuvo resultados (`"Query not found"`). Cualquier otra
falla (404 de ruta inexistente, 401, 5xx, timeout o error de conexión) MUST señalarse como
error de API externa y MUST NOT devolverse como lista vacía. Solo los errores transitorios
(timeout, conexión, 5xx) SHALL reintentarse; 401 y 404 MUST NOT reintentarse.

#### Scenario: Consulta sin resultados
- **WHEN** Orphanet responde 404 con cuerpo `"Query not found"`
- **THEN** la búsqueda devuelve una lista vacía sin error

#### Scenario: Ruta inexistente
- **WHEN** Orphanet responde 404 con el cuerpo genérico `"title": "Not Found"`
- **THEN** la búsqueda señala un error de API externa en lugar de devolver una lista vacía

#### Scenario: Servicio caído
- **WHEN** Orphanet responde 503
- **THEN** la búsqueda señala un error de API externa, que el Agente 05 traduce a `estado_orphanet`

### Requirement: La credencial es opcional y no condiciona la consulta
Orphanet SHALL consultarse siempre, haya o no credencial configurada: medido contra la API
real, responde sin ninguna clave. El sistema SHALL leer `ORPHANET_API_KEY` del entorno cuando
esté definida y, si no lo está, SHALL enviar igual el header con el valor público de
desarrollo que la API acepta. La ausencia de la variable MUST NOT impedir la consulta ni
producir un estado propio.

#### Scenario: Entorno sin credencial
- **WHEN** `ORPHANET_API_KEY` no está definida y Orphanet responde con resultados
- **THEN** la consulta se realiza igual, las coincidencias exactas se marcan y `estado_orphanet` vale `ok`

### Requirement: Coincidencia exacta para marcar una enfermedad rara
El Agente 05 SHALL consultar Orphanet con el término principal de cada hipótesis candidata y,
si no hay coincidencia, con sus sinónimos. Una hipótesis SHALL marcarse como enfermedad rara
solo si el nombre preferido de alguna candidata de Orphanet es igual, tras normalizar
(minúsculas, sin puntuación ni guiones, espacios colapsados, sin importar el orden de las
palabras), al término principal o a uno de sus sinónimos. Coincidencias parciales o por
inclusión de palabras MUST NOT marcar la hipótesis. Cada hipótesis SHALL marcarse como máximo
una vez.

#### Scenario: Coincidencia exacta con un sinónimo
- **WHEN** los términos de la hipótesis son `hereditary transthyretin amyloidosis` y `hereditary ATTR amyloidosis`, y Orphanet devuelve `Hereditary ATTR amyloidosis` (ORPHA 271861)
- **THEN** la hipótesis se marca como enfermedad rara con código `271861`, el término coincidente y su enlace

#### Scenario: Coincidencia por inclusión de palabras
- **WHEN** el término es `axonal sensorimotor polyneuropathy` y la primera candidata de Orphanet es `Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy`
- **THEN** la hipótesis no se marca como enfermedad rara

#### Scenario: Diferencias de formato
- **WHEN** el término es `ATTR amyloidosis, hereditary` y Orphanet devuelve `Hereditary ATTR amyloidosis`
- **THEN** la hipótesis se marca como enfermedad rara

### Requirement: Orphanet no bloquea la búsqueda de ensayos
Una falla de Orphanet MUST NOT impedir ni retrasar indefinidamente la búsqueda y evaluación de
ensayos. El Agente 05 SHALL informar `estado_orphanet` como `ok`, `parcial`, `no_disponible`
o `sin_consulta` (sin términos válidos para consultar).

#### Scenario: Orphanet caído con ClinicalTrials.gov disponible
- **WHEN** todas las consultas a Orphanet fallan y ClinicalTrials.gov responde
- **THEN** el resultado incluye los ensayos evaluados, `rare_diseases` vacío y `estado_orphanet: "no_disponible"`
