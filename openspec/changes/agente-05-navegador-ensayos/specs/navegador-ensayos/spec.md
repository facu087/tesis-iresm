## Purpose

Agente 05 (Navegador de Ensayos): encuentra ensayos clínicos activos relacionados con
las hipótesis del caso y estima, de forma orientativa y nunca diagnóstica, su
compatibilidad con el perfil del paciente para que el médico responsable decida qué
revisar.

## ADDED Requirements

### Requirement: Entrada independiente del origen de las hipótesis
El Agente 05 SHALL recibir las hipótesis a explorar como una lista de candidatas con
texto, prioridad, nivel de evidencia y un estado opcional, más los datos del caso
necesarios para buscar (condición en inglés, genes, anticuerpos y fármacos INN) y el
perfil clínico estructurado de la síntesis PICO. El agente MUST NOT depender de si las
hipótesis provienen del reporte final del debate o del consenso del Árbitro (Agente 04).
Las candidatas con estado `descartada` MUST excluirse. De las restantes, el agente SHALL
tomar como máximo 3, ordenadas por prioridad (HIGH, MEDIUM, LOW) y luego por nivel de
evidencia (I, II, III), sin repetir textos idénticos.

#### Scenario: Hipótesis del debate sin estado
- **WHEN** el pipeline entrega las 5 hipótesis del reporte final del debate, ninguna con estado
- **THEN** el agente considera las 3 primeras según prioridad y nivel de evidencia

#### Scenario: Consenso del Árbitro con una hipótesis descartada
- **WHEN** la entrada trae 3 hipótesis y una tiene estado `descartada`
- **THEN** el agente explora solo las 2 restantes y no emite consultas por la descartada

#### Scenario: Sin hipótesis elegibles
- **WHEN** todas las candidatas están descartadas o la lista está vacía
- **THEN** el agente omite la planificación, informa `planificacion: "sin_candidatas"` y ejecuta igual la búsqueda base

### Requirement: Búsqueda base sin regresión
El Agente 05 SHALL ejecutar siempre una búsqueda base de ensayos equivalente a la vigente
antes de este cambio: condición en inglés (`condition_en`) como condición y hasta 5 términos
de biomarcadores (genes, anticuerpos, fármacos) como palabras clave, reintentando solo con la
condición si la combinación no devuelve resultados. La búsqueda base MUST NOT usar el motivo
de consulta en español como condición de reemplazo.

#### Scenario: Caso con condición en inglés y genes
- **WHEN** el caso trae `condition_en = "axonal sensorimotor polyneuropathy"` y el gen `TTR`
- **THEN** la búsqueda base consulta esa condición con `TTR` como palabra clave

#### Scenario: Caso sin condición en inglés ni biomarcadores
- **WHEN** `condition_en` está vacío y no hay biomarcadores válidos
- **THEN** el agente no ejecuta la búsqueda base y no envía el motivo de consulta en español a ClinicalTrials.gov

### Requirement: Estados de reclutamiento consultados
Todas las consultas a ClinicalTrials.gov, la base y las de cada hipótesis, SHALL pedir los
ensayos en estado `RECRUITING` y `NOT_YET_RECRUITING`. Cada ensayo MUST conservar su estado
de reclutamiento para que el reporte pueda distinguirlos. Los ensayos que aún no reclutan
MUST NOT excluirse ni penalizarse en la evaluación de compatibilidad.

#### Scenario: Ensayo que todavía no abrió
- **WHEN** una consulta devuelve un ensayo en estado `NOT_YET_RECRUITING`
- **THEN** el ensayo se incluye en el resultado con su estado, disponible para que la vista y el PDF lo etiqueten

#### Scenario: Estados no solicitados
- **WHEN** ClinicalTrials.gov tiene ensayos `COMPLETED` o `SUSPENDED` para la misma condición
- **THEN** esos ensayos no se consultan ni ocupan lugar en el resultado

### Requirement: Planificación de términos por hipótesis
El Agente 05 SHALL pedir al LLM, una única vez por análisis, un término de condición en
inglés médico y hasta 2 sinónimos por cada hipótesis candidata. Cada término MUST pasar la
regla de saneamiento antes de usarse. Por cada candidata con término válido, el agente SHALL
consultar ensayos con el término principal y, si no hay resultados, con cada
sinónimo en orden hasta obtener alguno. Si la llamada al LLM falla o no produce ningún
término válido, el agente SHALL continuar solo con la búsqueda base e informar
`planificacion: "fallback"`.

#### Scenario: Planificación exitosa
- **WHEN** el LLM traduce "Amiloidosis hereditaria por transtiretina" a `hereditary transthyretin amyloidosis` con el sinónimo `hereditary ATTR amyloidosis`
- **THEN** el agente consulta ClinicalTrials.gov con el término principal y reporta `planificacion: "ok"`

#### Scenario: Término principal sin resultados
- **WHEN** la consulta con el término principal devuelve 0 ensayos
- **THEN** el agente consulta con el primer sinónimo y, si también devuelve 0, con el segundo

#### Scenario: Falla del LLM en la planificación
- **WHEN** la llamada al LLM lanza una excepción o devuelve JSON inválido
- **THEN** el agente devuelve los ensayos de la búsqueda base con `planificacion: "fallback"` sin interrumpir el pipeline

#### Scenario: Referencia a una candidata inexistente
- **WHEN** el LLM devuelve términos para una candidata con índice fuera de rango
- **THEN** esos términos se ignoran y no generan consultas

### Requirement: Saneamiento de términos enviados a APIs externas
Todo término que el Agente 05 envíe a ClinicalTrials.gov u Orphanet (condición, sinónimos,
genes, anticuerpos, fármacos) SHALL cumplir: solo caracteres ASCII imprimibles de un conjunto
acotado (letras, dígitos, espacio, guion, paréntesis, coma, apóstrofo, barra y signo más),
entre 2 y 80 caracteres, como máximo 8 palabras y sin palabras que describan al paciente
(edad, sexo o la palabra "patient"). Los términos que no cumplan MUST descartarse, nunca
corregirse ni truncarse.

#### Scenario: Término con datos demográficos
- **WHEN** el LLM propone `42-year-old male neuropathy`
- **THEN** el término se descarta y no se envía a ninguna API

#### Scenario: Biomarcador en español con tildes
- **WHEN** los biomarcadores del caso incluyen `anti-gangliósido GM1`
- **THEN** ese término se descarta y los genes ASCII como `TTR` se siguen usando

### Requirement: Deduplicación y trazabilidad de ensayos
El Agente 05 SHALL unificar los ensayos por NCT ID. Cada ensayo MUST registrar en
`matched_terms` los términos que lo encontraron y en `related_hypotheses` los textos de las
hipótesis candidatas cuyas consultas lo devolvieron (vacío si solo lo trajo la búsqueda base).
El resultado SHALL contener como máximo 10 ensayos, priorizando el orden de descubrimiento:
primero la búsqueda base y luego las candidatas en su orden.

#### Scenario: Ensayo encontrado por dos consultas
- **WHEN** `NCT04000001` aparece en la búsqueda base y en la consulta de la hipótesis de amiloidosis
- **THEN** el resultado lo incluye una sola vez, con ambos términos en `matched_terms` y la hipótesis en `related_hypotheses`

#### Scenario: Más de 10 ensayos únicos
- **WHEN** las consultas suman 17 ensayos únicos tras los filtros
- **THEN** el resultado conserva los 10 primeros según el orden de descubrimiento

### Requirement: Filtros duros deterministas por edad y sexo
El Agente 05 SHALL obtener la edad en años y el sexo del paciente del perfil de la síntesis
PICO sin usar el LLM. Un ensayo MUST excluirse solo cuando el dato del paciente y el criterio
del ensayo se conocen y son incompatibles: edad fuera del rango `min_age`–`max_age`, o sexo
del ensayo `MALE`/`FEMALE` distinto del sexo del paciente. Si alguno de los dos datos falta o
no se puede interpretar, el ensayo MUST conservarse. El agente SHALL contar las exclusiones
por motivo. La edad y el sexo MUST NOT enviarse a ninguna API externa.

#### Scenario: Paciente fuera del rango etario
- **WHEN** el paciente tiene 42 años y el ensayo admite de `18 Years` a `40 Years`
- **THEN** el ensayo se excluye y `excluidos_por_edad` aumenta en 1

#### Scenario: Ensayo sin edad máxima
- **WHEN** el ensayo declara `min_age = "18 Years"` y no declara `max_age`
- **THEN** el ensayo se conserva para un paciente de 42 años

#### Scenario: Sexo incompatible
- **WHEN** el perfil dice "Paciente masculino" y el ensayo declara `sex = "FEMALE"`
- **THEN** el ensayo se excluye y `excluidos_por_sexo` aumenta en 1

#### Scenario: Perfil sin sexo identificable
- **WHEN** el perfil PICO no menciona el sexo del paciente
- **THEN** ningún ensayo se excluye por sexo

### Requirement: Evaluación orientativa de compatibilidad
El Agente 05 SHALL pedir al LLM, en una única llamada, que evalúe los ensayos que pasaron los
filtros contra el perfil clínico estructurado (no el texto original del documento). Cada
ensayo SHALL recibir `compatibility` con uno de `alta`, `media`, `baja` o `sin_evaluar`, un
fundamento breve en español y una lista de criterios que el médico debe verificar. La
evaluación MUST NOT afirmar que el paciente es elegible, recomendar la inscripción ni emitir
diagnósticos. El LLM MUST NOT excluir ensayos: una compatibilidad `baja` conserva el ensayo.
Las evaluaciones cuyo NCT ID no esté entre los enviados MUST descartarse y contarse en
`evaluaciones_descartadas`; una etiqueta fuera del conjunto permitido MUST tratarse como
`sin_evaluar`.

#### Scenario: Evaluación válida
- **WHEN** el LLM evalúa `NCT04000001` como `alta` con dos criterios a verificar
- **THEN** el ensayo queda entre los de compatibilidad `alta`, con su fundamento y sus criterios en el resultado

#### Scenario: NCT ID inventado por el LLM
- **WHEN** la respuesta incluye una evaluación para `NCT99999999`, que no se envió
- **THEN** esa evaluación se descarta, `evaluaciones_descartadas` vale 1 y ningún ensayo nuevo aparece

#### Scenario: Falla del LLM en la evaluación
- **WHEN** la llamada de evaluación falla o devuelve JSON inválido
- **THEN** todos los ensayos quedan `sin_evaluar`, con `evaluacion: "fallback"`

#### Scenario: Ensayo omitido por el LLM
- **WHEN** el LLM evalúa 4 de 5 ensayos enviados
- **THEN** el ensayo omitido queda `sin_evaluar` y se conserva

### Requirement: Orden del resultado
Los ensayos SHALL ordenarse por compatibilidad (`alta`, `media`, `baja`, `sin_evaluar`) y,
a igualdad de compatibilidad, primero los que tienen una sede en Argentina, después los que
ya están reclutando y por último el orden de descubrimiento. La sede y el estado de
reclutamiento ordenan y MUST NOT excluir ningún ensayo. La ubicación del paciente MUST NOT
usarse como criterio: la preferencia por Argentina es del despliegue, no un dato del caso.

#### Scenario: Ensayo local menos compatible
- **WHEN** un ensayo con sede en Argentina tiene compatibilidad `media` y otro del exterior la tiene `alta`
- **THEN** el ensayo del exterior aparece primero

#### Scenario: Desempate por sede
- **WHEN** dos ensayos tienen compatibilidad `alta` y solo uno tiene sede en Argentina
- **THEN** el que tiene sede en Argentina aparece primero

#### Scenario: Desempate por estado de reclutamiento
- **WHEN** dos ensayos tienen la misma compatibilidad, ninguno tiene sede en Argentina y uno está `NOT_YET_RECRUITING`
- **THEN** el que ya está reclutando aparece primero

### Requirement: Resultado disponible ante fallas externas
El Agente 05 SHALL devolver siempre un resultado, aunque fallen ClinicalTrials.gov, Orphanet o
el LLM. Cada falla SHALL reflejarse en el estado de la búsqueda (`estado_clinicaltrials`,
`estado_orphanet`, `planificacion`, `evaluacion`) para que el reporte distinga "no hay ensayos"
de "no se pudo consultar". Una falla en una consulta MUST NOT cancelar las consultas restantes.

#### Scenario: ClinicalTrials.gov caído
- **WHEN** todas las consultas a ClinicalTrials.gov fallan por timeout
- **THEN** el agente devuelve 0 ensayos con `estado_clinicaltrials: "no_disponible"` y el pipeline responde HTTP 200

#### Scenario: Falla parcial
- **WHEN** la búsqueda base responde y la consulta de una hipótesis devuelve HTTP 500
- **THEN** el resultado incluye los ensayos de la búsqueda base con `estado_clinicaltrials: "parcial"`

#### Scenario: Error inesperado dentro del agente
- **WHEN** el agente lanza una excepción no prevista durante el análisis
- **THEN** el pipeline usa un resultado vacío con `estado_clinicaltrials: "no_disponible"` y continúa con el reporte

### Requirement: Privacidad de los datos clínicos
El Agente 05 MUST NOT enviar a ClinicalTrials.gov ni a Orphanet el texto del documento, la
narrativa clínica, el perfil del paciente, la edad ni el sexo: solo términos saneados. El
perfil clínico estructurado SHALL enviarse únicamente al LLM configurado en el pipeline. Los
mensajes de log del agente MUST limitarse al nombre del agente, el tipo de excepción y
conteos; MUST NOT incluir el mensaje de la excepción, respuestas del LLM, hipótesis ni
fragmentos del perfil. El agente MUST NOT persistir datos del caso fuera de la respuesta.

#### Scenario: Consultas externas sin texto clínico
- **WHEN** el agente procesa el caso base (paciente masculino de 42 años con neuropatía axonal)
- **THEN** ningún parámetro enviado a ClinicalTrials.gov u Orphanet contiene "42", "masculino" ni fragmentos de la narrativa

#### Scenario: Falla de parseo con eco del perfil
- **WHEN** el LLM devuelve texto no JSON que repite el perfil del paciente y el parseo falla
- **THEN** el log registra solo el tipo de excepción y el texto de la respuesta no aparece en stderr
