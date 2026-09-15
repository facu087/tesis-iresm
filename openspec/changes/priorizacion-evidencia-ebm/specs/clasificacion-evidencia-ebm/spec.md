## Purpose

Define cómo NEXUS asigna el nivel de evidencia EBM (I, II, III) efectivo de cada hipótesis a
partir de sus referencias verificadas contra PubMed, qué estado bibliográfico le corresponde
(respaldada, pendiente o especulativa) y en qué orden aparece en el reporte, sin depender del
nivel que autodeclara el LLM y sin descartar ninguna hipótesis.

## ADDED Requirements

### Requirement: Tope de evidencia por tipo de publicación verificado
El sistema SHALL calcular, para cada fuente cuya verificación contra PubMed resultó
`verificada`, un **tope de evidencia** a partir de los tipos de publicación que PubMed indexa
para ese artículo, con esta tabla:

- Tope **I**: `Meta-Analysis`, `Network Meta-Analysis`, `Systematic Review`,
  `Randomized Controlled Trial`.
- Tope **II**: `Observational Study`, `Clinical Trial` (incluidas sus fases
  `Clinical Trial, Phase I` a `Phase IV`), `Controlled Clinical Trial`,
  `Pragmatic Clinical Trial`, `Comparative Study`, `Multicenter Study`,
  `Practice Guideline`, `Guideline`.
- Tope **III**: `Case Reports`, `Review`, `Scoping Review`, `Letter`, `Editorial`, `Comment`,
  `News`, `Consensus Development Conference`.

Cuando un artículo tiene varios tipos, el tope de la fuente SHALL ser el mejor nivel entre los
reconocidos. Si el artículo figura como retractado (`Retracted Publication` o
`Retraction of Publication`), el tope MUST ser III sin importar los demás tipos. Si ninguno de
sus tipos figura en la tabla (por ejemplo, solo `Journal Article`), el tope SHALL ser II.

La comparación de tipos de publicación MUST ser insensible a mayúsculas y espacios
circundantes.

#### Scenario: Meta-análisis verificado habilita nivel I
- **WHEN** una fuente verificada tiene los tipos `Journal Article` y `Meta-Analysis`
- **THEN** su tope de evidencia es I

#### Scenario: Estudio observacional verificado topea en II
- **WHEN** una fuente verificada tiene los tipos `Journal Article` y `Observational Study`
- **THEN** su tope de evidencia es II

#### Scenario: Artículo sin diseño identificable topea en II
- **WHEN** una fuente verificada tiene únicamente el tipo `Journal Article`
- **THEN** su tope de evidencia es II

#### Scenario: Reporte de caso topea en III
- **WHEN** una fuente verificada tiene los tipos `Case Reports` y `Journal Article`
- **THEN** su tope de evidencia es III

#### Scenario: Mezcla de tipos toma el mejor
- **WHEN** una fuente verificada tiene los tipos `Multicenter Study` y `Randomized Controlled Trial`
- **THEN** su tope de evidencia es I

#### Scenario: Publicación retractada anula cualquier otro tipo
- **WHEN** una fuente verificada tiene los tipos `Randomized Controlled Trial` y `Retracted Publication`
- **THEN** su tope de evidencia es III

### Requirement: Nivel de evidencia efectivo de la hipótesis
El sistema SHALL asignar a cada hipótesis un **nivel efectivo** igual al nivel que declaró el
agente, limitado por el mejor tope entre sus fuentes verificadas. El nivel efectivo MUST NOT
ser mejor que el nivel declarado: la verificación solo puede bajar el nivel, nunca subirlo.

Si la hipótesis no tiene ninguna fuente con veredicto `verificada`, su nivel efectivo MUST ser
III, cualquiera sea el nivel declarado.

#### Scenario: Nivel declarado respaldado por un RCT verificado se conserva
- **WHEN** una hipótesis declara nivel I y una de sus fuentes verificadas es un `Randomized Controlled Trial`
- **THEN** su nivel efectivo es I

#### Scenario: Nivel declarado mayor que el tope se baja
- **WHEN** una hipótesis declara nivel I y su única fuente verificada tiene tope II
- **THEN** su nivel efectivo es II

#### Scenario: El tope no sube un nivel declarado conservador
- **WHEN** una hipótesis declara nivel III y una de sus fuentes verificadas es un `Meta-Analysis`
- **THEN** su nivel efectivo es III

#### Scenario: Se usa la mejor fuente verificada de la hipótesis
- **WHEN** una hipótesis declara nivel I y tiene una fuente verificada con tope III y otra con tope I
- **THEN** su nivel efectivo es I

#### Scenario: Sin fuentes verificadas el nivel es III
- **WHEN** una hipótesis declara nivel I y todas sus fuentes resultaron `discordante`, `inexistente` o `sin_pmid`
- **THEN** su nivel efectivo es III

#### Scenario: Hipótesis sin fuentes
- **WHEN** una hipótesis declara nivel II y no cita ninguna fuente
- **THEN** su nivel efectivo es III

### Requirement: Estado bibliográfico de la hipótesis
El sistema SHALL asignar a cada hipótesis exactamente uno de estos estados, derivado de los
veredictos de verificación de sus fuentes:

- `respaldada`: al menos una fuente tiene veredicto `verificada`.
- `pendiente`: ninguna fuente está `verificada` y al menos una fuente con PMID quedó sin
  veredicto concluyente (veredicto `no_verificable` o sin veredicto porque la verificación no
  se ejecutó).
- `especulativa`: en cualquier otro caso, incluida la hipótesis sin fuentes.

El sistema MUST NOT descartar ni omitir hipótesis por su estado: toda hipótesis generada
aparece en el reporte. No existe un estado "descartada".

#### Scenario: Una fuente verificada alcanza para quedar respaldada
- **WHEN** una hipótesis tiene una fuente `verificada` y otra `discordante`
- **THEN** su estado es `respaldada`

#### Scenario: PMID alucinado deja la hipótesis especulativa
- **WHEN** la única fuente de una hipótesis resultó `discordante`
- **THEN** su estado es `especulativa` y la hipótesis sigue presente en el reporte

#### Scenario: Caída de PubMed deja la hipótesis pendiente
- **WHEN** la consulta a PubMed falla y la única fuente con PMID de una hipótesis queda `no_verificable`
- **THEN** su estado es `pendiente` y su nivel efectivo es III

#### Scenario: Reporte armado sin verificación
- **WHEN** el reporte se construye sin veredictos de verificación y una hipótesis cita una fuente con PMID
- **THEN** su estado es `pendiente`

#### Scenario: Fuente sin PMID no deja pendiente
- **WHEN** la única fuente de una hipótesis no declara PMID
- **THEN** su estado es `especulativa`

### Requirement: Solo cuentan los veredictos de la verificación
La clasificación de nivel y estado MUST basarse exclusivamente en los veredictos producidos
por la verificación bibliográfica contra PubMed. Cualquier dato de verificación o tipo de
publicación que aparezca en las fuentes tal como las emitió un agente (por ejemplo
`verified: true` o una lista de tipos escrita por el LLM) MUST ser ignorado para clasificar y
MUST NOT aparecer en el reporte exportado como si fuera resultado de la verificación.

#### Scenario: El LLM declara su fuente como verificada
- **WHEN** un agente emite una fuente con `verified: true` y la verificación no produjo veredicto `verificada` para ella
- **THEN** la hipótesis no queda `respaldada` por esa fuente y la fuente exportada no figura como verificada

#### Scenario: El LLM inventa tipos de publicación
- **WHEN** un agente emite una fuente con tipos de publicación `Meta-Analysis`, la verificación la da por `verificada` y PubMed indexa ese PMID solo como `Case Reports`
- **THEN** el tope usado para esa fuente es III

### Requirement: Clasificación determinista y sin costo de red adicional
Dado el mismo conjunto de hipótesis y de veredictos de verificación, la clasificación SHALL
producir siempre el mismo nivel efectivo, estado, explicación y orden. La clasificación MUST
NOT invocar modelos de lenguaje ni realizar llamadas de red: los tipos de publicación MUST
obtenerse en la misma consulta a PubMed que ya realiza la verificación bibliográfica, sin
agregar consultas.

La clasificación SHALL poder invocarse por separado del armado del reporte, para que otros
componentes del pipeline (el Árbitro Verificador y el Sintetizador) apliquen las mismas reglas.

#### Scenario: Misma entrada, misma salida
- **WHEN** se clasifica dos veces el mismo conjunto de hipótesis con los mismos veredictos
- **THEN** ambos resultados son idénticos, incluido el orden

#### Scenario: Una sola consulta a PubMed
- **WHEN** se verifica y clasifica un reporte con varias fuentes con PMID
- **THEN** el sistema realiza una única consulta de metadatos a PubMed para todas ellas

### Requirement: Orden de las hipótesis en el reporte
El sistema SHALL ordenar las hipótesis del reporte con estos criterios, en este orden de
precedencia:

1. Estado: `respaldada`, luego `pendiente`, luego `especulativa`.
2. Nivel efectivo: I, luego II, luego III.
3. Prioridad declarada: HIGH, luego MEDIUM, luego LOW.
4. Cantidad de fuentes verificadas, de mayor a menor.
5. Orden original en que el pipeline entregó las hipótesis.

El campo `rank` SHALL numerar las hipótesis de forma consecutiva desde 1 según ese orden, de
modo que las hipótesis de un mismo estado queden contiguas.

#### Scenario: El nivel de evidencia pesa más que la prioridad
- **WHEN** una hipótesis respaldada tiene nivel efectivo II y prioridad LOW, y otra respaldada tiene nivel efectivo III y prioridad HIGH
- **THEN** la de nivel II aparece primero

#### Scenario: Una respaldada precede a una especulativa
- **WHEN** una hipótesis respaldada tiene nivel efectivo III y prioridad LOW, y una especulativa tiene prioridad HIGH
- **THEN** la respaldada aparece primero

#### Scenario: Desempate por prioridad
- **WHEN** dos hipótesis tienen el mismo estado y el mismo nivel efectivo, y una tiene prioridad HIGH y la otra MEDIUM
- **THEN** la de prioridad HIGH aparece primero

#### Scenario: Desempate estable
- **WHEN** dos hipótesis coinciden en estado, nivel efectivo, prioridad y cantidad de fuentes verificadas
- **THEN** conservan el orden en que las entregó el pipeline

### Requirement: Trazabilidad del nivel asignado
Cada hipótesis exportada SHALL incluir el nivel que declaró el agente y una explicación en
español de por qué quedó con su nivel efectivo, que mencione si hubo tope y qué lo motivó (la
mejor fuente verificada y su tipo de publicación, la ausencia de fuentes verificadas o la
verificación no disponible).

#### Scenario: Nivel topeado
- **WHEN** una hipótesis declaró nivel I y quedó en II por un estudio observacional verificado
- **THEN** la hipótesis exportada informa nivel declarado I, nivel efectivo II y una explicación que menciona el tope y el tipo de publicación

#### Scenario: Nivel sin cambios
- **WHEN** una hipótesis declaró nivel II y su mejor fuente verificada tiene tope I
- **THEN** la hipótesis exportada informa nivel declarado II, nivel efectivo II y una explicación que indica que el nivel declarado es compatible con la evidencia verificada

#### Scenario: Verificación no disponible
- **WHEN** una hipótesis quedó `pendiente`
- **THEN** su explicación indica que el nivel queda en III hasta poder confirmar las fuentes

### Requirement: Contrato de exportación aditivo
Los cambios al reporte exportado (`StructuredReport`) MUST ser aditivos: ningún campo existente
se elimina ni cambia de tipo, y todo campo nuevo tiene un valor por defecto, de modo que un
reporte generado antes de este cambio siga siendo aceptado por `POST /api/report/pdf`. El
reporte SHALL exponer:

- En cada hipótesis: `evidence_level` con el nivel **efectivo**, `declared_evidence_level` con
  el nivel declarado, `evidence_note` con la explicación y `status` con uno de `respaldada`,
  `pendiente` o `especulativa`.
- En cada fuente verificada: `publication_types` con los tipos de publicación que indexa
  PubMed. Las fuentes no verificadas MUST exportar esa lista vacía.
- En el resumen de verificación: `hipotesis_respaldadas`, `hipotesis_pendientes`,
  `hipotesis_especulativas` (que suman el total de hipótesis) y `hipotesis_topeadas` (cantidad
  de hipótesis cuyo nivel efectivo quedó por debajo del declarado).

#### Scenario: Reporte previo sigue siendo válido
- **WHEN** se envía a `POST /api/report/pdf` un reporte sin `declared_evidence_level`, `evidence_note`, `publication_types`, `hipotesis_pendientes` ni `hipotesis_topeadas`
- **THEN** el sistema lo acepta y genera el PDF

#### Scenario: Los conteos de estado suman el total
- **WHEN** un reporte tiene 2 hipótesis respaldadas, 1 pendiente y 3 especulativas
- **THEN** el resumen informa `hipotesis_respaldadas` 2, `hipotesis_pendientes` 1, `hipotesis_especulativas` 3

#### Scenario: Conteo de hipótesis topeadas
- **WHEN** de 4 hipótesis, 2 quedaron con nivel efectivo por debajo del declarado
- **THEN** el resumen informa `hipotesis_topeadas` 2

### Requirement: Presentación separada por estado
La vista de reporte y el PDF exportado SHALL presentar las hipótesis agrupadas por estado, con
un encabezado por grupo (respaldadas, pendientes de verificación, especulativas) y omitiendo los
grupos vacíos. Cuando el nivel efectivo de una hipótesis sea menor que el declarado, SHALL
mostrarse ambos niveles.

#### Scenario: Reporte con hipótesis respaldadas y especulativas
- **WHEN** el reporte tiene hipótesis respaldadas y especulativas y ninguna pendiente
- **THEN** la vista y el PDF muestran un grupo de respaldadas seguido de uno de especulativas, sin grupo de pendientes

#### Scenario: Nivel topeado visible
- **WHEN** una hipótesis declaró nivel I y quedó con nivel efectivo II
- **THEN** la vista y el PDF muestran el nivel efectivo II e indican que el agente había declarado I
