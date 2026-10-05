## Purpose

Define la ronda de recitación: el intento acotado de que las hipótesis sin respaldo
bibliográfico vuelvan a citarse sobre la literatura real que el RAG ya había
recuperado, en lugar de sobre PMIDs inventados, y el criterio de parada que reemplaza
al originalmente documentado, imposible de cumplir.

## ADDED Requirements

### Requirement: Trazabilidad de la literatura recuperada

El sistema SHALL conservar, a lo largo del análisis, los artículos que la búsqueda
semántica recuperó y ofreció a los agentes, con su PMID y su título, y no solamente el
texto ya formateado que se insertó en el prompt.

#### Scenario: Artículos disponibles para el Árbitro
- **WHEN** la búsqueda semántica recuperó artículos y los incluyó en el contexto de la primera ronda
- **THEN** esos artículos, con sus PMIDs, están disponibles para el Árbitro al final del análisis

#### Scenario: Búsqueda semántica no disponible
- **WHEN** la búsqueda semántica falló o no devolvió resultados
- **THEN** el análisis continúa y el conjunto de artículos recuperados queda vacío

### Requirement: Medición del solapamiento entre lo recuperado y lo citado

El sistema SHALL medir y exponer cuántas de las fuentes citadas por los agentes
corresponden a artículos que la búsqueda semántica les había ofrecido.

#### Scenario: Los agentes ignoran la literatura recuperada
- **WHEN** ninguna de las fuentes citadas por los agentes figura entre los artículos recuperados
- **THEN** el reporte informa un solapamiento de cero sobre el total de fuentes citadas

#### Scenario: Cita proveniente del contexto recuperado
- **WHEN** un agente cita un PMID que estaba entre los artículos ofrecidos
- **THEN** esa fuente cuenta como solapamiento

### Requirement: Selección de las hipótesis a recitar

El sistema SHALL seleccionar para la ronda de recitación únicamente las hipótesis de
consenso cuyo estado bibliográfico no es `respaldada`, es decir aquellas sin ninguna
fuente verificada.

Una hipótesis cuyo estado es `pendiente` porque la verificación no pudo ejecutarse
MUST NOT recitarse: el problema es de infraestructura, no de la cita.

#### Scenario: Hipótesis especulativa
- **WHEN** una hipótesis de consenso no tiene ninguna fuente verificada y la verificación sí pudo ejecutarse
- **THEN** la hipótesis entra en la ronda de recitación

#### Scenario: Hipótesis respaldada
- **WHEN** una hipótesis de consenso tiene al menos una fuente verificada
- **THEN** la hipótesis no entra en la ronda de recitación

#### Scenario: PubMed caído
- **WHEN** la verificación no pudo ejecutarse y todas las hipótesis quedaron pendientes
- **THEN** no se ejecuta ninguna recitación

#### Scenario: Sin literatura que ofrecer
- **WHEN** hay hipótesis sin respaldo pero el conjunto de artículos recuperados está vacío
- **THEN** no se ejecuta la recitación y las hipótesis quedan especulativas

### Requirement: La recitación ofrece literatura real

Al pedir a un agente que vuelva a citar, el sistema SHALL incluir en el pedido los
artículos recuperados por la búsqueda semántica, con su PMID, título y resumen, y
SHALL indicar explícitamente que las nuevas referencias deben salir de ese conjunto.

#### Scenario: Pedido de recitación
- **WHEN** una hipótesis entra en la ronda de recitación
- **THEN** el pedido al agente incluye los artículos recuperados con sus PMIDs y títulos reales

### Requirement: Validación de los PMIDs recitados

El sistema SHALL aceptar de la recitación únicamente fuentes cuyo PMID pertenezca al
conjunto de artículos ofrecidos. Una fuente con un PMID fuera de ese conjunto SHALL
descartarse sin consultar PubMed.

El sistema SHALL registrar cuántas fuentes se descartaron por esta regla.

#### Scenario: El agente vuelve a inventar un PMID
- **WHEN** la recitación devuelve una fuente cuyo PMID no estaba entre los artículos ofrecidos
- **THEN** esa fuente se descarta, no se consulta PubMed por ella y el descarte queda contabilizado

#### Scenario: El agente cita del conjunto ofrecido
- **WHEN** la recitación devuelve una fuente cuyo PMID estaba entre los artículos ofrecidos
- **THEN** esa fuente se conserva y pasa a re-verificarse contra PubMed

### Requirement: Re-verificación de lo recitado

Las fuentes aceptadas en la recitación SHALL verificarse contra PubMed con el mismo
criterio que las citas originales: el PMID debe existir y su título real debe coincidir
con el declarado.

Una fuente recitada MUST NOT darse por válida sin re-verificar, aunque su PMID
provenga del conjunto ofrecido.

#### Scenario: Recitación con título correcto
- **WHEN** una fuente recitada declara el mismo título que PubMed devuelve para ese PMID
- **THEN** la fuente queda verificada y la hipótesis pasa a estado respaldada

#### Scenario: Recitación con título que no corresponde
- **WHEN** una fuente recitada usa un PMID del conjunto ofrecido pero declara un título que no corresponde a ese artículo
- **THEN** la fuente queda discordante y no respalda la hipótesis

### Requirement: Una sola iteración de recitación

El sistema SHALL ejecutar como máximo una ronda de recitación por análisis. Una
hipótesis que sigue sin respaldo después de recitar MUST NOT volver a recitarse.

#### Scenario: La recitación no mejoró la hipótesis
- **WHEN** después de recitar la hipótesis sigue sin ninguna fuente verificada
- **THEN** queda especulativa, se documenta el intento y no se recita otra vez

### Requirement: Criterio de parada del análisis

El análisis SHALL terminar después de la ronda de recitación, tenga o no respaldo cada
hipótesis. El sistema MUST NOT condicionar la finalización a que todas las hipótesis
alcancen respaldo bibliográfico verificable.

Ninguna hipótesis SHALL descartarse por falta de respaldo: queda etiquetada como
especulativa y se reporta.

#### Scenario: Ninguna hipótesis alcanza respaldo
- **WHEN** después de la recitación ninguna hipótesis tiene fuentes verificadas
- **THEN** el análisis termina y el reporte entrega todas las hipótesis como especulativas

#### Scenario: Respaldo parcial
- **WHEN** después de la recitación algunas hipótesis quedaron respaldadas y otras no
- **THEN** el análisis termina y el reporte distingue unas de otras

### Requirement: Trazabilidad del resultado de la recitación

El reporte SHALL informar cuántas hipótesis entraron en la recitación, cuántas pasaron a
estado respaldada gracias a ella y cuántas fuentes recitadas se descartaron por PMID
fuera del conjunto ofrecido.

Cada hipótesis que fue recitada SHALL quedar identificable como tal en el reporte.

#### Scenario: Resumen de la recitación
- **WHEN** el análisis ejecutó una ronda de recitación sobre tres hipótesis y una quedó respaldada
- **THEN** el reporte informa 3 recitadas y 1 mejorada

#### Scenario: Reporte sin recitación
- **WHEN** no hubo hipótesis que recitar
- **THEN** el reporte informa cero hipótesis recitadas y el análisis no reporta fallo

### Requirement: Fallback ante fallo de la recitación

Si la recitación de un agente falla, el análisis SHALL continuar con las hipótesis
restantes y con el estado bibliográfico que ya tenían. `POST /api/analyze` MUST NOT
fallar por un error en la recitación.

#### Scenario: Un agente falla al recitar
- **WHEN** la llamada al modelo para recitar falla para uno de los agentes
- **THEN** sus hipótesis conservan el estado previo, el resto de la recitación se completa y el análisis termina correctamente
