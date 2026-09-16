## Purpose

Aportar al debate multi-agente la perspectiva genómica del caso (etiologías hereditarias, variantes y
farmacogenómica) como hipótesis de investigación, sin emitir diagnósticos y sin atribuirle al paciente
hallazgos genéticos que el documento clínico no reporta.

## ADDED Requirements

### Requirement: Identidad del agente y acceso al LLM
El sistema SHALL incorporar el Agente 02 con identificador `"02"` y nombre `"Especialista Genómica"`. El
agente MUST acceder al LLM exclusivamente a través del punto único de acceso al proveedor que comparten
todos los agentes, y MUST NOT instanciar un cliente de proveedor propio. En el prototipo SHALL usar el
modelo principal de Groq (`openai/gpt-oss-120b`).

#### Scenario: Cambio de proveedor centralizado
- **WHEN** se cambia el proveedor de LLM en el punto único de acceso compartido por los agentes
- **THEN** el Agente 02 usa el nuevo proveedor sin modificar su propio código

#### Scenario: Identidad en el output
- **WHEN** el Agente 02 completa un análisis
- **THEN** su output lleva `agent_id` `"02"` y `agent_name` `"Especialista Genómica"`

### Requirement: Formato de respuesta del Agente 02
El Agente 02 SHALL devolver entre 1 y 4 hipótesis con el mismo formato que los demás agentes (`text`,
`priority`, `evidence_level`, `rationale`, `sources`). Cada hipótesis SHALL declarar además la lista de
hallazgos genéticos del caso en los que se apoya (vacía si no usa ninguno). Si el agente no conoce con
certeza un PMID, MUST dejarlo en `null` y MUST NOT inventarlo. Una respuesta sin JSON válido o sin
hipótesis SHALL tratarse como falla del agente. Si el LLM devuelve más de 4 hipótesis, el agente SHALL
conservar las 4 primeras en el orden recibido.

#### Scenario: Respuesta válida
- **WHEN** el LLM responde con un JSON de 3 hipótesis bien formadas
- **THEN** el Agente 02 devuelve un output con esas 3 hipótesis validadas

#### Scenario: Exceso de hipótesis
- **WHEN** el LLM responde con 6 hipótesis bien formadas
- **THEN** el Agente 02 devuelve un output con las 4 primeras

#### Scenario: Respuesta malformada
- **WHEN** el LLM responde con texto sin JSON válido
- **THEN** el Agente 02 falla con un error de parseo y la Ronda 1 continúa con los demás agentes

### Requirement: Reglas clínicas del Agente 02
Las instrucciones del Agente 02 MUST prohibir emitir diagnósticos y recomendar tratamientos o dosis, y MUST
exigir que toda hipótesis se formule como hipótesis de investigación para el médico responsable. Las
instrucciones MUST pedir que el agente considere el patrón de herencia sugerido por los antecedentes
familiares y la cobertura de los estudios genéticos negativos (qué genes o tipos de alteración no detecta
un estudio negativo).

#### Scenario: Instrucciones del agente
- **WHEN** se inspeccionan las instrucciones con las que el Agente 02 llama al LLM
- **THEN** incluyen la prohibición de diagnósticos y de tratamientos, y la consigna sobre patrón de herencia
  y cobertura de estudios negativos

### Requirement: Modo con hallazgos genómicos
Cuando el perfil genómico del caso está en modo con hallazgos, el Agente 02 SHALL recibir el bloque de
contexto genómico con los hallazgos reportados y las anotaciones farmacogenómicas, y SHALL poder apoyar sus
hipótesis en esos hallazgos declarándolos en la lista de hallazgos del caso.

#### Scenario: Caso con TTR p.Val30Met
- **WHEN** el Agente 02 analiza un caso cuyo perfil reporta `TTR` y `p.Val30Met`
- **THEN** la instrucción enviada al LLM contiene el bloque genómico con `p.Val30Met` como hallazgo reportado
  y el estado de la fuente PharmGKB

### Requirement: Modo orientación sin hallazgos genómicos
Cuando el perfil genómico del caso está en modo sin hallazgos, el Agente 02 SHALL ejecutarse igual (no se
omite) y SHALL formular sus hipótesis como etiologías hereditarias o estudios genéticos a considerar. En
este modo el agente MUST NOT afirmar ni sugerir que el paciente porta una variante, MUST NOT mencionar
variantes concretas (notación `c.`, `p.`, `g.` o `rs`) en el texto de las hipótesis, y la lista de hallazgos
del caso de cada hipótesis MUST quedar vacía.

#### Scenario: Caso base de la tesis
- **WHEN** el Agente 02 analiza el caso de neuropatía axonal sensitivomotora (hombre de 42 años, panel CMT de
  40 genes negativo, padre con problemas de equilibrio, sin variantes)
- **THEN** el agente hace una única llamada al LLM, no hace consultas externas, y la instrucción enviada
  afirma explícitamente que el caso no reporta variantes ni hallazgos genéticos positivos

### Requirement: Guarda contra hallazgos genéticos inventados
El sistema SHALL verificar de forma determinista cada hipótesis del Agente 02, en la Ronda 1 y en cada
revisión del debate. Una hipótesis MUST considerarse sospechosa si:
- declara como hallazgo del caso algo que no figura entre los hallazgos reportados ni los genes del perfil
  (comparación sin distinguir mayúsculas, espacios ni los prefijos `c.`/`p.`/`g.`), o
- el perfil está en modo sin hallazgos y el texto de la hipótesis contiene una variante concreta (notación
  `c.`, `p.`, `g.` o `rs`).

Una hipótesis sospechosa MUST NOT descartarse: SHALL conservarse con prioridad `LOW` y con una advertencia
visible al inicio del `rationale` que indique qué hallazgo no figura en el caso. El registro de la guarda
MUST limitarse a la cantidad de hipótesis marcadas, sin texto clínico. Si una hipótesis omite la lista de
hallazgos del caso, la primera verificación SHALL tratarla como lista vacía.

#### Scenario: Variante inventada en el caso base
- **WHEN** en el caso base el Agente 02 devuelve una hipótesis que declara `p.Val30Met` como hallazgo del caso
- **THEN** la hipótesis se conserva con prioridad `LOW` y su `rationale` empieza con una advertencia que
  nombra `p.Val30Met` como hallazgo no reportado

#### Scenario: Variante concreta en modo orientación
- **WHEN** el perfil está en modo sin hallazgos y una hipótesis dice "paciente portador de c.148G>A en TTR"
- **THEN** la hipótesis se conserva con prioridad `LOW` y con la advertencia al inicio del `rationale`

#### Scenario: Hallazgo presente en el caso
- **WHEN** el perfil reporta `p.Val30Met` y una hipótesis declara `Val30Met` como hallazgo del caso
- **THEN** la hipótesis conserva su prioridad y su `rationale` sin advertencias

#### Scenario: Orientación válida
- **WHEN** el perfil está en modo sin hallazgos y una hipótesis propone "amiloidosis hereditaria por TTR no
  cubierta por el panel CMT; considerar secuenciación de TTR" con la lista de hallazgos vacía
- **THEN** la hipótesis conserva su prioridad y su `rationale` sin advertencias

### Requirement: Participación en la Ronda 1
El orquestador SHALL ejecutar el Agente 02 en paralelo con los Agentes 01 y 03 sobre el mismo contexto
clínico, agregándole al Agente 02 su bloque de contexto genómico. La construcción y el enriquecimiento del
perfil genómico SHALL ejecutarse en paralelo con el enriquecimiento bibliográfico del contexto, y el perfil
resultante SHALL quedar asociado al caso para reutilizarse en el debate. Si el Agente 02 falla, la Ronda 1
MUST continuar con los agentes restantes. La vista de progreso del frontend SHALL indicar que la Ronda 1
corre los Agentes 01, 02 y 03.

#### Scenario: Tres agentes en paralelo
- **WHEN** se ejecuta la Ronda 1 y los tres agentes responden
- **THEN** el reporte de Ronda 1 contiene tres outputs, con `agent_id` `"01"`, `"02"` y `"03"`

#### Scenario: Falla del Agente 02
- **WHEN** el Agente 02 lanza una excepción en la Ronda 1
- **THEN** el reporte de Ronda 1 contiene los outputs de 01 y 03 y la falla queda registrada en stderr

#### Scenario: Vista de progreso
- **WHEN** el usuario ve el paso "Análisis paralelo — Ronda 1" en la vista de pipeline
- **THEN** el paso indica "Agentes 01, 02 y 03 en simultáneo"

### Requirement: Participación en el debate
En las Rondas 2 a 4 el Agente 02 SHALL criticar las hipótesis de los demás agentes y revisar las propias con
su bloque de contexto genómico agregado al contexto del debate. El debate MUST reutilizar el perfil genómico
de la Ronda 1 y MUST NOT volver a consultar fuentes genómicas externas. Cada agente SHALL criticar a todos
los demás en una sola llamada al LLM por ronda.

#### Scenario: Ronda 2 con tres agentes
- **WHEN** se ejecuta la Ronda 2 con los Agentes 01, 02 y 03
- **THEN** se hacen tres llamadas al LLM, cada una con las hipótesis de los otros dos agentes

#### Scenario: Revisión con guarda
- **WHEN** en la Ronda 3 el Agente 02 revisa sus hipótesis y declara un hallazgo que no figura en el caso
- **THEN** la hipótesis revisada queda con prioridad `LOW` y advertencia, igual que en la Ronda 1

#### Scenario: Sin consultas externas en el debate
- **WHEN** se ejecutan las Rondas 2 a 4 sobre un caso con el gen `TTR`
- **THEN** no se realiza ninguna solicitud a PharmGKB durante el debate

### Requirement: Debate con agentes ausentes en la Ronda 1
El debate SHALL incluir solo a los agentes que tienen output de la Ronda 1. La ausencia de un agente MUST NOT
interrumpir el debate.

#### Scenario: Agente 02 caído en la Ronda 1
- **WHEN** el reporte de Ronda 1 trae outputs solo de los Agentes 01 y 03
- **THEN** el debate completa las Rondas 2, 3 y 4 con esos dos agentes, sin error

### Requirement: Atribución de las hipótesis del Agente 02
Las hipótesis del Agente 02 SHALL aparecer en el reporte exportado con `"Especialista Genómica"` entre sus
agentes de respaldo, sin cambios en el contrato JSON del reporte.

#### Scenario: Hipótesis genómica en el reporte
- **WHEN** el reporte final incluye una hipótesis propuesta por el Agente 02 en la Ronda 4
- **THEN** la hipótesis exportada lista `"Especialista Genómica"` en `supporting_agents`
