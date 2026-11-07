# Spec Delta

## MODIFIED Requirements

### Requirement: Datos registrados por llamada

Cada llamada registrada SHALL incluir el paso o agente que la originó, el
proveedor y el modelo usados, los tokens de entrada, los tokens de salida y la
latencia, y si la llamada fue un respaldo en Groq y por qué motivo.

Cuando el proveedor no informe el consumo, la llamada SHALL registrarse igual,
marcada como sin datos de consumo, en lugar de omitirse: omitirla haría parecer
que el análisis costó menos de lo que costó.

#### Scenario: Llamada normal
- **WHEN** el modelo responde e informa su consumo
- **THEN** el registro tiene el agente, el proveedor, el modelo, tokens de entrada, tokens de salida y latencia

#### Scenario: El proveedor no informa el consumo
- **WHEN** el modelo responde sin datos de consumo
- **THEN** la llamada igual queda registrada, marcada como sin datos, y el resumen informa cuántas llamadas quedaron así

#### Scenario: Llamada fallida
- **WHEN** una llamada al modelo falla y el paso cae a su fallback
- **THEN** el intento queda registrado como fallido, para que el costo de los reintentos también sea visible

#### Scenario: Llamada de respaldo
- **WHEN** la llamada a un proveedor de destino falla y se repite en Groq
- **THEN** quedan registrados el intento fallido con su proveedor y la llamada en Groq marcada como respaldo por falla

### Requirement: Estimación de costo con tarifas configurables

El sistema SHALL convertir el consumo a costo usando una tabla de tarifas por
modelo, configurable sin tocar el código. La tabla SHALL incluir las tarifas
vigentes de los modelos de la arquitectura de destino.

Un modelo sin tarifa configurada SHALL reportarse con costo cero y quedar
señalado como sin tarifa, en lugar de omitirse del total o de interrumpir el
análisis.

#### Scenario: Modelo gratuito
- **WHEN** todas las llamadas usan un modelo con tarifa cero
- **THEN** el costo estimado es cero y el resumen lo informa como tal

#### Scenario: Modelo sin tarifa configurada
- **WHEN** una llamada usa un modelo que no figura en la tabla de tarifas
- **THEN** el análisis termina normalmente y el resumen señala que ese modelo no tiene tarifa

#### Scenario: Estimar el costo con otro proveedor
- **WHEN** se configura la tarifa de un modelo de pago y se recalcula sobre un registro existente
- **THEN** se obtiene el costo que habría tenido ese mismo análisis con ese modelo

#### Scenario: Costo real de la arquitectura de destino
- **WHEN** termina un análisis con la arquitectura de destino activa
- **THEN** el resumen informa el costo estimado con las tarifas de cada proveedor que respondió
