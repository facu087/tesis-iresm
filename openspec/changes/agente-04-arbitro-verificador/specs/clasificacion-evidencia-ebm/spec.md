## MODIFIED Requirements

### Requirement: Solo cuentan los veredictos de la verificación
La clasificación de nivel y estado MUST basarse exclusivamente en los veredictos producidos
por la verificación bibliográfica contra PubMed. Cualquier dato de verificación o tipo de
publicación que aparezca en las fuentes tal como las emitió un agente (por ejemplo
`verified: true` o una lista de tipos escrita por el LLM) MUST ser ignorado para clasificar y
MUST NOT aparecer en el reporte exportado como si fuera resultado de la verificación.

Además, esos campos MUST descartarse al construir la fuente a partir de la respuesta del
agente, y no sólo al clasificar: el estado de verificación, el título real y los tipos de
publicación son salida de la verificación bibliográfica y nunca entrada del modelo. Una
fuente recién parseada de la respuesta de un agente SHALL quedar sin estado de
verificación, cualquiera sea lo que el modelo haya declarado.

#### Scenario: El LLM declara su fuente como verificada
- **WHEN** un agente emite una fuente con `verified: true` y la verificación no produjo veredicto `verificada` para ella
- **THEN** la hipótesis no queda `respaldada` por esa fuente y la fuente exportada no figura como verificada

#### Scenario: El LLM inventa tipos de publicación
- **WHEN** un agente emite una fuente con tipos de publicación `Meta-Analysis`, la verificación la da por `verificada` y PubMed indexa ese PMID solo como `Case Reports`
- **THEN** el tope usado para esa fuente es III

#### Scenario: Los campos de verificación se descartan al parsear
- **WHEN** un agente emite una fuente que declara estado de verificación, título real o tipos de publicación
- **THEN** la fuente construida a partir de esa respuesta no conserva ninguno de esos valores

#### Scenario: El dato sucio no viaja en el reporte interno
- **WHEN** se inspecciona una hipótesis antes de que corra la verificación bibliográfica
- **THEN** ninguna de sus fuentes tiene estado de verificación asignado

### Requirement: Orden de las hipótesis en el reporte
El sistema SHALL ordenar las hipótesis del reporte con estos criterios, en este orden de
precedencia:

1. Estado: `respaldada`, luego `pendiente`, luego `especulativa`.
2. Nivel efectivo: I, luego II, luego III.
3. Cantidad de agentes que respaldan la hipótesis en el consenso, de mayor a menor.
4. Prioridad declarada: HIGH, luego MEDIUM, luego LOW.
5. Cantidad de fuentes verificadas, de mayor a menor.
6. Orden original en que el pipeline entregó las hipótesis.

El respaldo del consenso pesa más que la prioridad declarada porque la prioridad la
autodeclara un único agente, mientras que la cantidad de agentes que sostienen una
hipótesis es una señal producida por el debate. Cuando el reporte se arma sin arbitraje,
toda hipótesis cuenta con un solo agente de respaldo y el criterio no altera el orden.

El campo `rank` SHALL numerar las hipótesis de forma consecutiva desde 1 según ese orden, de
modo que las hipótesis de un mismo estado queden contiguas.

#### Scenario: El nivel de evidencia pesa más que la prioridad
- **WHEN** una hipótesis respaldada tiene nivel efectivo II y prioridad LOW, y otra respaldada tiene nivel efectivo III y prioridad HIGH
- **THEN** la de nivel II aparece primero

#### Scenario: Una respaldada precede a una especulativa
- **WHEN** una hipótesis respaldada tiene nivel efectivo III y prioridad LOW, y una especulativa tiene prioridad HIGH
- **THEN** la respaldada aparece primero

#### Scenario: El respaldo del consenso pesa más que la prioridad
- **WHEN** dos hipótesis coinciden en estado y nivel efectivo, una la sostienen tres agentes con prioridad MEDIUM y la otra un solo agente con prioridad HIGH
- **THEN** la que sostienen tres agentes aparece primero

#### Scenario: Desempate por prioridad
- **WHEN** dos hipótesis tienen el mismo estado, el mismo nivel efectivo y la misma cantidad de agentes de respaldo, y una tiene prioridad HIGH y la otra MEDIUM
- **THEN** la de prioridad HIGH aparece primero

#### Scenario: Reporte armado sin arbitraje
- **WHEN** el reporte se arma sin consenso del Árbitro y todas las hipótesis tienen un solo agente de respaldo
- **THEN** el orden resultante es el mismo que antes de incorporar este criterio

#### Scenario: Desempate estable
- **WHEN** dos hipótesis coinciden en estado, nivel efectivo, agentes de respaldo, prioridad y cantidad de fuentes verificadas
- **THEN** conservan el orden en que las entregó el pipeline
