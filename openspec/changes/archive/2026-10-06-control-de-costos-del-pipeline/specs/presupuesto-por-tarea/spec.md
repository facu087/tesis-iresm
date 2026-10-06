## Purpose

Define cómo se elige el techo de tokens y el modelo de cada llamada según lo que
esa llamada tiene que producir, para dejar de pagar un razonamiento clínico
completo por una respuesta que devuelve tres números, sin degradar las tareas
donde la calidad del modelo sí determina la del análisis.

## ADDED Requirements

### Requirement: Techo de tokens por tarea

Cada llamada al modelo SHALL declarar el máximo de tokens que su salida
necesita, en lugar de usar un único valor para todo el sistema.

El techo SHALL fijarse con holgura sobre la salida esperada: es un límite de
seguridad, no un objetivo de compresión. Una salida truncada por un techo
demasiado bajo es un defecto, no un ahorro.

#### Scenario: Tarea de salida acotada
- **WHEN** una llamada solo puede devolver una lista de índices o un puñado de términos
- **THEN** su techo es acorde a esa salida y no el del razonamiento clínico

#### Scenario: Tarea de razonamiento
- **WHEN** una llamada tiene que producir hipótesis con su fundamento
- **THEN** su techo sigue permitiendo la respuesta completa

#### Scenario: Ninguna salida se trunca
- **WHEN** se corre el análisis del caso de prueba con los techos nuevos
- **THEN** ninguna respuesta del modelo queda cortada por alcanzar su techo

### Requirement: Modelo por tarea

El sistema SHALL permitir que cada llamada use un modelo distinto según la
naturaleza de la tarea, no un único modelo por agente.

Una tarea SHALL poder usar el modelo rápido **solo si** cumple las dos
condiciones: su salida es acotada y estructurada, y esa salida **ya se valida
deterministicamente por código**, de modo que una respuesta peor caiga en una
validación existente y no en un resultado incorrecto que nadie detecte.

#### Scenario: Tarea con salida validada por código
- **WHEN** una tarea devuelve una estructura que el código valida antes de usarla
- **THEN** esa tarea puede usar el modelo rápido

#### Scenario: Tarea de razonamiento clínico
- **WHEN** una tarea produce hipótesis, críticas, revisiones, veredictos o la síntesis del caso
- **THEN** esa tarea usa el modelo principal

#### Scenario: Salida degradada del modelo rápido
- **WHEN** el modelo rápido devuelve una estructura inválida en una tarea que bajó de modelo
- **THEN** cae en la validación que ya existía para esa tarea y el análisis continúa con su fallback

### Requirement: El razonamiento clínico no se degrada

El sistema MUST NOT bajar de modelo las tareas cuya calidad determina la del
análisis: la generación de hipótesis, la crítica cruzada, las revisiones del
debate, los veredictos del Árbitro y la síntesis PICO.

#### Scenario: Inventario de tareas degradadas
- **WHEN** se listan las tareas que usan el modelo rápido
- **THEN** ninguna de ellas produce hipótesis, críticas, revisiones, veredictos ni la síntesis del caso

### Requirement: El cambio de modelo se mide, no se asume

Antes de dar por buena una tarea movida al modelo rápido, el sistema SHALL
permitir comparar su salida contra la del modelo principal sobre el caso de
prueba.

La comparación SHALL registrar, para las tareas movidas, si el resultado
observable cambió y cuántas veces la salida del modelo rápido cayó en una
validación.

#### Scenario: Comparación antes y después
- **WHEN** se corre el caso de prueba con el modelo principal y después con el rápido en las tareas candidatas
- **THEN** se puede comparar el agrupamiento resultante, los términos planificados y las etiquetas de compatibilidad

#### Scenario: Degradación detectada
- **WHEN** la salida del modelo rápido cae en una validación con más frecuencia que la del principal
- **THEN** ese dato queda registrado para poder revertir la decisión sobre esa tarea

### Requirement: La configuración de modelos queda en un solo lugar

La asignación de modelo y techo por tarea SHALL poder revisarse sin leer el
cuerpo de cada agente.

El **proveedor** MUST seguir eligiéndose en un único punto del sistema: elegir el
modelo de una tarea MUST NOT implicar que el módulo hable con el proveedor por
su cuenta.

#### Scenario: Revisar qué usa cada tarea
- **WHEN** alguien quiere saber qué modelo y qué techo usa cada llamada
- **THEN** lo encuentra en un solo lugar, sin recorrer todos los agentes

#### Scenario: Swap de proveedor
- **WHEN** se cambie el proveedor del modelo
- **THEN** el cambio se hace en un único punto, y ningún módulo lo instancia por su cuenta
