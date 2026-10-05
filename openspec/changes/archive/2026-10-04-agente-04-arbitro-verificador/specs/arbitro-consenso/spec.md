## Purpose

Define cómo el Árbitro Verificador convierte las hipótesis sueltas que dejan los tres
agentes del debate en un consenso legible para el médico: agrupa las equivalentes,
deja constancia de quién respalda y quién refuta cada una, documenta las
contradicciones y emite un veredicto por hipótesis apoyado en la verificación
bibliográfica y el nivel de evidencia efectivo.

## ADDED Requirements

### Requirement: Consolidación en hipótesis de consenso

El sistema SHALL agrupar las hipótesis finales del debate que afirman lo mismo en una
única hipótesis de consenso, en lugar de exponer la concatenación de las hipótesis de
cada agente.

Cada hipótesis de consenso SHALL exponer un texto representativo, el fundamento
consolidado, los agentes que la respaldan, los agentes que la refutan, las fuentes de
todas las hipótesis agrupadas y el veredicto del Árbitro.

#### Scenario: Tres agentes proponen la misma hipótesis con distinta redacción
- **WHEN** los agentes 01, 02 y 03 proponen cada uno una hipótesis que afirma lo mismo con otras palabras
- **THEN** el consenso contiene una sola hipótesis para las tres, y sus agentes de respaldo son 01, 02 y 03

#### Scenario: Hipótesis que ningún otro agente propuso
- **WHEN** un solo agente propone una hipótesis que ningún otro sostiene
- **THEN** el consenso la conserva como hipótesis propia con un único agente de respaldo

#### Scenario: Las fuentes de las agrupadas se conservan
- **WHEN** dos hipótesis se agrupan y cada una citaba fuentes distintas
- **THEN** la hipótesis de consenso cita las fuentes de ambas, sin duplicar las que compartían PMID

### Requirement: Agrupar nunca descarta

Toda hipótesis entregada por el debate SHALL quedar incluida en exactamente un grupo
del consenso. El sistema MUST NOT eliminar, omitir ni fusionar hipótesis que afirmen
cosas distintas, cualquiera sea su nivel de evidencia, su estado bibliográfico o la
cantidad de agentes que la sostengan.

#### Scenario: Hipótesis especulativa sin respaldo bibliográfico
- **WHEN** una hipótesis no tiene ninguna fuente que resista la verificación
- **THEN** igualmente aparece en el consenso, etiquetada como especulativa

#### Scenario: Conservación total
- **WHEN** el debate entrega N hipótesis
- **THEN** la suma de las hipótesis agrupadas en todos los grupos del consenso es exactamente N

#### Scenario: El agrupamiento propuesto omite una hipótesis
- **WHEN** la propuesta de agrupamiento del modelo no menciona alguna de las hipótesis recibidas
- **THEN** esa hipótesis se incorpora al consenso como grupo propio y no se pierde

### Requirement: Registro de refutaciones y contradicciones

El sistema SHALL registrar, para cada hipótesis de consenso, qué agentes la
contradijeron durante el debate y con qué argumento, tomando como base las críticas
emitidas en la ronda de crítica cruzada.

Una contradicción SHALL quedar documentada aunque no se resuelva. El sistema MUST NOT
presentar como consenso unánime una hipótesis que recibió críticas de severidad alta
que el agente criticado no incorporó.

#### Scenario: Hipótesis respaldada por dos agentes y refutada por un tercero
- **WHEN** los agentes 01 y 02 sostienen una hipótesis y el agente 03 la criticó con severidad HIGH y mantuvo su objeción
- **THEN** la hipótesis de consenso lista a 01 y 02 como respaldo, a 03 como refutación, y expone el texto de la objeción

#### Scenario: Contradicción irresoluble
- **WHEN** dos agentes sostienen hipótesis incompatibles entre sí y ninguno cedió en las rondas de revisión
- **THEN** ambas aparecen en el consenso y cada una documenta la contradicción con la otra

#### Scenario: Crítica incorporada por el agente criticado
- **WHEN** un agente recibió una crítica HIGH y modificó su hipótesis en consecuencia
- **THEN** esa crítica no se reporta como contradicción abierta

### Requirement: Veredicto por hipótesis

El Árbitro SHALL emitir para cada hipótesis de consenso un veredicto que explique, en
lenguaje llano, en qué quedó parada la hipótesis después del debate y de la
verificación bibliográfica.

El veredicto SHALL apoyarse en el estado bibliográfico y el nivel de evidencia efectivo
que produce la clasificación EBM, y MUST NOT contradecirlos.

#### Scenario: Veredicto coherente con el estado bibliográfico
- **WHEN** una hipótesis quedó especulativa porque ninguna de sus citas resistió la verificación
- **THEN** su veredicto dice que no tiene respaldo bibliográfico verificable, y no la presenta como respaldada

#### Scenario: Veredicto de una hipótesis con nivel topeado
- **WHEN** el agente declaró nivel I y la clasificación lo topeó en III por el tipo de publicación de su mejor fuente verificada
- **THEN** el veredicto menciona el nivel efectivo III y no el declarado

### Requirement: El Árbitro no vota ni genera hipótesis propias

El Árbitro MUST NOT emitir hipótesis que ningún agente haya propuesto, ni participar de
las rondas de crítica y revisión del debate. Su función es arbitrar sobre lo producido.

#### Scenario: Salida limitada a lo debatido
- **WHEN** el Árbitro produce el consenso
- **THEN** toda hipótesis de consenso se corresponde con al menos una hipótesis emitida por un agente del debate

### Requirement: Límites del modelo en el arbitraje

El sistema SHALL usar el LLM únicamente para agrupar hipótesis equivalentes y redactar
los fundamentos y veredictos en lenguaje natural.

El LLM MUST NOT decidir qué hipótesis se descartan, MUST NOT alterar el nivel de
evidencia efectivo ni el estado bibliográfico que produjo la clasificación
determinista, y MUST NOT introducir fuentes, PMIDs o títulos que no vengan de las
hipótesis que se le entregaron. Toda referencia que aparezca en la salida del modelo y
no estuviera en la entrada SHALL ser descartada.

#### Scenario: El modelo inventa una fuente en el fundamento
- **WHEN** la salida del modelo cita un PMID que no figuraba en ninguna de las hipótesis recibidas
- **THEN** esa referencia se descarta y queda registrada la cantidad de referencias descartadas

#### Scenario: El modelo intenta subir un nivel de evidencia
- **WHEN** la salida del modelo asigna a una hipótesis un nivel mejor que el efectivo calculado por la clasificación EBM
- **THEN** prevalece el nivel efectivo calculado

#### Scenario: El modelo propone descartar una hipótesis
- **WHEN** la salida del modelo marca una hipótesis como que debería eliminarse
- **THEN** la hipótesis se conserva en el consenso

### Requirement: Fallback ante fallo del arbitraje

Si la agrupación asistida por el modelo falla, el análisis SHALL continuar y devolver un
consenso degradado en el que cada hipótesis del debate es su propio grupo, con los
agentes que la propusieron y sin veredicto redactado. `POST /api/analyze` MUST NOT
fallar por un error del Árbitro.

El reporte SHALL dejar constancia de que el arbitraje no pudo completarse.

#### Scenario: El LLM no responde
- **WHEN** la llamada al modelo para agrupar falla o devuelve algo que no se puede parsear
- **THEN** el análisis termina correctamente, el reporte contiene todas las hipótesis sin agrupar y el resumen de arbitraje informa el fallo

#### Scenario: La verificación bibliográfica no está disponible
- **WHEN** PubMed no respondió y ninguna fuente pudo verificarse
- **THEN** el consenso se construye igual y sus hipótesis quedan en estado pendiente

### Requirement: Privacidad en el arbitraje

El sistema MUST NOT registrar en logs el texto clínico del paciente, las hipótesis ni
las respuestas del modelo. Los mensajes de error SHALL limitarse al tipo de excepción y
a conteos agregados.

#### Scenario: Error durante el arbitraje
- **WHEN** el arbitraje falla por una excepción inesperada
- **THEN** el log registra el tipo de excepción y ningún fragmento de texto clínico ni de la respuesta del modelo
