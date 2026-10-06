# clinvar-variantes Specification

## Purpose
Consultar en ClinVar la significancia clínica de las variantes genéticas que trae el caso, con
una coincidencia verificada contra la variante consultada, y entregarla al Agente 02 como parte
del contexto genómico, sin que el LLM tenga que recordarla.

## Requirements

### Requirement: Consulta de la clasificación de una variante
Dada una variante y el símbolo de su gen, el sistema SHALL consultar ClinVar (NCBI E-utilities,
base `clinvar`) y SHALL devolver, para el registro que coincide, la clasificación germinal, el
estado de revisión, la fecha de última evaluación, el título del registro y su accession `VCV`
con el enlace a su ficha pública en ClinVar.

#### Scenario: Variante HGVS con registro único
- **WHEN** se consulta la variante `c.148G>A` del gen `TTR`
- **THEN** el resultado tiene estado `encontrada`, accession `VCV000013417`, clasificación `Pathogenic` y un enlace a `https://www.ncbi.nlm.nih.gov/clinvar/variation/13417/`

### Requirement: Coincidencia verificada contra la variante consultada
El sistema SHALL aceptar un registro solo si su título contiene la notación consultada y su lista
de genes contiene el gen consultado. Cuando la búsqueda devuelve uno o más registros y ninguno
cumple esa condición, o cuando más de uno la cumple con clasificaciones distintas, el resultado
SHALL tener estado `ambigua`, incluir la cantidad de candidatos y no informar ninguna
clasificación. El sistema MUST NOT elegir el primer registro de la lista como respuesta.

#### Scenario: Notación clásica que trae registros de otras variantes
- **WHEN** se consulta `Val30Met` del gen `TTR` y ClinVar devuelve 5 registros, ninguno con `Val30Met` en el título
- **THEN** el resultado tiene estado `ambigua`, informa 5 candidatos y no informa clasificación

#### Scenario: Registro de otro gen
- **WHEN** el único registro devuelto contiene la notación en el título pero corresponde a otro gen
- **THEN** el resultado no tiene estado `encontrada`

### Requirement: Estados explícitos y errores distinguibles
Cada variante consultada SHALL terminar con exactamente uno de estos estados: `encontrada`,
`sin_resultados` (ClinVar respondió sin registros), `ambigua` o `no_disponible` (error de red,
HTTP distinto de 200, respuesta malformada, límite de velocidad o circuito abierto). Un error de
la API MUST NOT informarse como `sin_resultados`, y la consulta MUST NOT propagar la excepción al
pipeline.

#### Scenario: ClinVar sin registros
- **WHEN** la búsqueda responde con cero identificadores
- **THEN** el estado es `sin_resultados`

#### Scenario: Caída del servicio
- **WHEN** NCBI responde HTTP 500 o no responde dentro del tiempo límite
- **THEN** el estado es `no_disponible` y el análisis continúa

### Requirement: Privacidad y cupo compartido de NCBI
A ClinVar SHALL viajar únicamente el símbolo del gen y la notación de la variante; MUST NOT
viajar texto clínico, edad, sexo ni ningún otro dato del caso. Las consultas SHALL respetar el
mismo límite de velocidad que las consultas a PubMed, porque ambos usan el mismo servicio de NCBI
y el mismo cupo. El sistema SHALL consultar como máximo 5 variantes por análisis.

#### Scenario: Parámetros enviados
- **WHEN** se consulta una variante del caso
- **THEN** los parámetros de la solicitud contienen solo el gen, la notación, la base `clinvar` y los parámetros técnicos de E-utilities (formato, cantidad, clave de API si está configurada)

#### Scenario: Caso con más de 5 variantes
- **WHEN** el caso trae 7 variantes
- **THEN** se consultan las 5 primeras y las otras 2 quedan sin consultar, informado en el detalle de la fuente

### Requirement: Uso en el contexto genómico del Agente 02
Cuando el caso trae variantes con gen identificable, el contexto genómico SHALL incluir el
resultado de ClinVar de cada variante consultada y una fuente `ClinVar` con su estado agregado,
y el bloque que recibe el Agente 02 SHALL mostrar la clasificación y el accession de cada
variante `encontrada` y el estado de las demás. Cuando el caso no trae variantes, la fuente
`ClinVar` SHALL quedar `no_consultada` y no se SHALL hacer ninguna solicitud. Las fuentes ya
existentes del contexto (PharmGKB) MUST conservarse.

#### Scenario: Caso con variante TTR
- **WHEN** el caso informa `TTR c.148G>A` y ClinVar responde con el registro exacto
- **THEN** el bloque del Agente 02 incluye `Pathogenic` y `VCV000013417` para esa variante, y las fuentes del contexto incluyen tanto `PharmGKB` como `ClinVar`

#### Scenario: Caso base sin variantes
- **WHEN** se analiza el caso base (neuropatía axonal, varón de 42 años, sin variantes)
- **THEN** no se hace ninguna solicitud a ClinVar y la fuente `ClinVar` queda `no_consultada`
