## Purpose

Que las hipótesis del reporte citen solo literatura que el sistema recuperó de PubMed y le ofreció a los agentes, para que una cita sea siempre trazable a un artículo real y no a la memoria del modelo.

## ADDED Requirements

### Requirement: Solo se aceptan citas de la literatura ofrecida

Al cerrar el debate (después de la Ronda 4 y antes de la verificación bibliográfica), el sistema SHALL descartar de cada hipótesis toda fuente cuyo PMID no esté entre los artículos que el RAG ofreció en ese análisis. La fuente descartada MUST NOT consultarse en PubMed. Una fuente repetida dentro de la misma hipótesis queda una sola vez.

Ninguna hipótesis MUST descartarse por este filtro: una hipótesis que se queda sin fuentes sigue en el reporte, con estado especulativo, y es candidata a la recitación de la Ronda 5.

#### Scenario: Cita de memoria
- **WHEN** una hipótesis cita el PMID 31234567 y el RAG ofreció otros cinco artículos
- **THEN** esa fuente se descarta, no se consulta en PubMed y la hipótesis sigue en el reporte

#### Scenario: Cita de un artículo ofrecido
- **WHEN** una hipótesis cita un PMID que el RAG ofreció
- **THEN** la fuente se conserva y pasa a la verificación bibliográfica

#### Scenario: Hipótesis que se queda sin fuentes
- **WHEN** todas las fuentes con PMID de una hipótesis se descartan
- **THEN** la hipótesis queda especulativa y entra en la recitación de la Ronda 5 con la literatura ofrecida

### Requirement: Fuentes sin PMID

Una fuente sin PMID (por ejemplo, una guía clínica citada por sociedad y año) SHALL conservarse sin cambios. Como hoy, MUST NOT contar como fuente verificada.

#### Scenario: Guía clínica sin PMID
- **WHEN** una hipótesis cita una guía clínica sin PMID
- **THEN** la fuente se conserva y queda como `sin_pmid` en la verificación

### Requirement: Sin literatura recuperada

Si el RAG no ofreció ningún artículo en el análisis (por ejemplo, porque la base local no respondió), el sistema SHALL descartar todas las fuentes con PMID. No hay excepción a la regla.

#### Scenario: RAG caído
- **WHEN** el RAG no ofrece artículos y los agentes citan 12 PMIDs
- **THEN** se descartan las 12 fuentes con PMID y el reporte informa 12 citas descartadas

### Requirement: Registro de las citas descartadas

El reporte SHALL informar, en el resumen de la verificación bibliográfica, cuántas fuentes se descartaron por no venir de la literatura ofrecida. El dato es aditivo: un reporte generado antes de este cambio, sin ese campo, MUST seguir leyéndose y MUST NOT interpretarse como cero descartadas.

Las citas descartadas MUST NOT aparecer en el reporte ni en la bibliografía.

#### Scenario: Conteo en el reporte
- **WHEN** el filtro descarta 23 fuentes en un análisis
- **THEN** el resumen de la verificación informa 23 citas fuera de la literatura ofrecida y ninguna de esas 23 aparece en el reporte

#### Scenario: Reporte anterior
- **WHEN** se lee un reporte guardado antes de este cambio
- **THEN** el conteo de citas descartadas aparece como no informado

### Requirement: Cantidad de literatura ofrecida

El RAG SHALL ofrecer a los agentes hasta 10 artículos por análisis, todos por encima del umbral de relevancia vigente (`NEXUS_RAG_MIN_SCORE`). Si menos artículos superan el umbral, se ofrecen solo esos.

#### Scenario: Más de 10 artículos relevantes
- **WHEN** 14 artículos indexados superan el umbral de relevancia
- **THEN** se ofrecen los 10 más relevantes

### Requirement: El debate ve la literatura ofrecida

Los pedidos de revisión de las Rondas 3 y 4 SHALL incluir la lista de artículos que el RAG ofreció en la Ronda 1, cada uno con su PMID, título y año, para que un agente pueda reemplazar una cita por un artículo ofrecido. La lista MUST NOT incluir el resumen de cada artículo (el costo en tokens se multiplica por cada revisión). Si el RAG no ofreció artículos, la lista dice que no hay literatura disponible.

#### Scenario: Revisión con literatura
- **WHEN** el RAG ofreció 8 artículos y se arma el pedido de revisión de la Ronda 3
- **THEN** el pedido lista los 8 PMIDs con su título y año, sin resúmenes

#### Scenario: Revisión sin literatura
- **WHEN** el RAG no ofreció artículos
- **THEN** el pedido de revisión dice que no hay literatura disponible para citar

### Requirement: Instrucciones a los agentes

Las instrucciones de los Agentes 01, 02 y 03, tanto al generar hipótesis como al revisarlas en el debate, SHALL indicar que solo pueden citar PMIDs que figuren en el bloque de literatura del contexto, y que una hipótesis sin un artículo de ese bloque que la respalde va sin fuentes y con nivel III. El ejemplo de formato de respuesta MUST NOT mostrar un PMID de relleno. El bloque de literatura MUST cerrar con esa misma regla como obligación, no como recomendación.

#### Scenario: Instrucción de generación
- **WHEN** se arma el pedido de hipótesis de cualquiera de los Agentes 01, 02 o 03
- **THEN** las instrucciones dicen que solo se citan PMIDs del bloque de literatura y el ejemplo de formato no trae un PMID numérico

#### Scenario: Instrucción de revisión
- **WHEN** se arma el pedido de revisión de las Rondas 3 o 4
- **THEN** las instrucciones repiten que solo se citan PMIDs del bloque de literatura
