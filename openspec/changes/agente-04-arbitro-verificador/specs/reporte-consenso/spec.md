## Purpose

Define cómo el consenso del Árbitro, las contradicciones entre agentes y el resumen del
arbitraje llegan al reporte exportado, al frontend y al PDF, sin romper el contrato JSON
que ya consumen los clientes ni prometer al médico más certeza de la que el sistema
produjo.

## ADDED Requirements

### Requirement: El reporte expone el consenso

Las hipótesis del reporte exportado SHALL ser las hipótesis de consenso del Árbitro, no
la concatenación de las hipótesis de cada agente.

Cada hipótesis del reporte SHALL exponer los agentes que la respaldan, los agentes que
la refutan, las contradicciones documentadas y el veredicto del Árbitro, además de los
campos que ya expone hoy.

#### Scenario: Hipótesis sostenida por tres agentes
- **WHEN** tres agentes sostuvieron la misma hipótesis y el Árbitro las agrupó
- **THEN** el reporte muestra una sola entrada con los tres agentes como respaldo

#### Scenario: Agentes de respaldo reales
- **WHEN** el reporte lista los agentes que respaldan una hipótesis
- **THEN** esa lista proviene del agrupamiento del Árbitro y no de una coincidencia exacta de texto

### Requirement: Resumen del arbitraje en el reporte

El reporte SHALL incluir un resumen del arbitraje con la cantidad de hipótesis que
entregó el debate, la cantidad de hipótesis de consenso resultantes, la cantidad de
contradicciones documentadas, el resultado de la recitación y el solapamiento entre la
literatura recuperada y las fuentes citadas.

#### Scenario: Resumen presente
- **WHEN** el arbitraje se ejecutó correctamente
- **THEN** el reporte incluye el resumen con las hipótesis de entrada, las de consenso y las métricas de recitación y solapamiento

#### Scenario: Arbitraje degradado
- **WHEN** el arbitraje falló y el consenso se construyó en modo degradado
- **THEN** el resumen lo informa explícitamente

### Requirement: Contrato de exportación aditivo

Los campos que este cambio agrega al reporte SHALL ser opcionales o tener valor por
defecto, de modo que un reporte generado antes de la existencia del Árbitro siga siendo
válido y un cliente que ignore los campos nuevos siga funcionando.

#### Scenario: Reporte previo al Árbitro
- **WHEN** se valida un reporte generado antes de este cambio, sin resumen de arbitraje
- **THEN** el reporte valida correctamente y el resumen de arbitraje queda nulo

#### Scenario: Cliente que ignora los campos nuevos
- **WHEN** un cliente lee el reporte usando sólo los campos previos a este cambio
- **THEN** obtiene la misma información que antes, sobre las hipótesis de consenso

### Requirement: Los conteos del resumen son consistentes

La cantidad de hipótesis de consenso SHALL ser menor o igual a la cantidad de hipótesis
que entregó el debate, y la cantidad de hipótesis que mejoraron por la recitación SHALL
ser menor o igual a la cantidad de hipótesis recitadas.

#### Scenario: Consolidación efectiva
- **WHEN** el debate entregó nueve hipótesis y el Árbitro las agrupó en cuatro
- **THEN** el resumen informa nueve de entrada y cuatro de consenso

#### Scenario: Sin agrupamiento posible
- **WHEN** ninguna hipótesis del debate es equivalente a otra
- **THEN** la cantidad de hipótesis de consenso es igual a la de entrada

### Requirement: Presentación del consenso al médico

El frontend y el PDF SHALL mostrar, para cada hipótesis, qué agentes la respaldan, qué
agentes la refutan y las contradicciones documentadas, junto con el veredicto del
Árbitro.

La presentación SHALL aclarar que el consenso es entre agentes de inteligencia
artificial y no constituye un diagnóstico ni una recomendación clínica.

#### Scenario: Hipótesis con contradicción abierta
- **WHEN** una hipótesis del reporte tiene una contradicción documentada
- **THEN** el frontend y el PDF la muestran junto a la hipótesis, con el agente que la planteó

#### Scenario: Aclaración visible
- **WHEN** el médico abre el reporte o su PDF
- **THEN** encuentra la aclaración de que el consenso es entre agentes de IA y no es un diagnóstico

#### Scenario: Hipótesis recitada
- **WHEN** una hipótesis pasó por la ronda de recitación
- **THEN** el reporte lo indica, junto con si la recitación le consiguió respaldo o no

### Requirement: El consenso alimenta la navegación de ensayos

La búsqueda de ensayos clínicos SHALL partir de las hipótesis de consenso del Árbitro y
no de las hipótesis crudas del debate.

#### Scenario: Búsqueda sobre el consenso
- **WHEN** el Árbitro agrupó nueve hipótesis del debate en cuatro de consenso
- **THEN** la navegación de ensayos planifica sus términos sobre esas cuatro

#### Scenario: Consenso degradado
- **WHEN** el arbitraje falló y el consenso quedó en modo degradado
- **THEN** la navegación de ensayos se ejecuta igual, sobre las hipótesis sin agrupar
