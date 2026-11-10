# Spec Delta

## MODIFIED Requirements

### Requirement: Modelo por tarea

El sistema SHALL permitir que cada llamada use un modelo distinto según la
naturaleza de la tarea, no un único modelo por agente.

Una tarea SHALL poder usar el modelo rápido **solo si** cumple las dos
condiciones: su salida es acotada y estructurada, y esa salida **ya se valida
deterministicamente por código**, de modo que una respuesta peor caiga en una
validación existente y no en un resultado incorrecto que nadie detecte.

Con la arquitectura de destino activa (capacidad `proveedor-por-agente`), el
modelo de una llamada SHALL resolverse por la tarea **y** por el agente que llama:
las llamadas de un agente con proveedor asignado usan el modelo de ese proveedor,
con el techo de su tarea ajustado a lo que ese modelo necesita para no truncar.

#### Scenario: Tarea con salida validada por código
- **WHEN** una tarea devuelve una estructura que el código valida antes de usarla
- **THEN** esa tarea puede usar el modelo rápido

#### Scenario: Tarea de razonamiento clínico
- **WHEN** una tarea produce hipótesis, críticas, revisiones, veredictos o la síntesis del caso
- **THEN** esa tarea usa el modelo principal

#### Scenario: Salida degradada del modelo rápido
- **WHEN** el modelo rápido devuelve una estructura inválida en una tarea que bajó de modelo
- **THEN** cae en la validación que ya existía para esa tarea y el análisis continúa con su fallback

#### Scenario: Misma tarea, distinto agente
- **WHEN** la arquitectura de destino está activa y los Agentes 01 y 02 escriben su crítica en la Ronda 2
- **THEN** la del Agente 01 usa el modelo de Anthropic y la del Agente 02 el de OpenAI, cada una con un techo que no la trunca

### Requirement: La configuración de modelos queda en un solo lugar

La asignación de modelo y techo por tarea SHALL poder revisarse sin leer el
cuerpo de cada agente. La asignación de proveedor y modelo por agente SHALL
revisarse en ese mismo lugar.

El **proveedor** MUST seguir eligiéndose en un único punto del sistema: elegir el
modelo de una tarea MUST NOT implicar que el módulo hable con el proveedor por
su cuenta.

#### Scenario: Revisar qué usa cada tarea
- **WHEN** alguien quiere saber qué modelo y qué techo usa cada llamada
- **THEN** lo encuentra en un solo lugar, sin recorrer todos los agentes

#### Scenario: Revisar qué proveedor usa cada agente
- **WHEN** alguien quiere saber qué proveedor y qué modelo usa cada agente con la arquitectura de destino activa
- **THEN** lo encuentra en el mismo lugar que la asignación por tarea

#### Scenario: Swap de proveedor
- **WHEN** se cambie el proveedor del modelo
- **THEN** el cambio se hace en un único punto, y ningún módulo lo instancia por su cuenta
