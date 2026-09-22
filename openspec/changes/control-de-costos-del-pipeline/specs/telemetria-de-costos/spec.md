## Purpose

Permite saber cuántos tokens consume cada agente y cada caso analizado, para no
volver a agotar la cuota sin verlo venir, para poder estimar qué costaría el
sistema con los modelos de pago de la arquitectura de destino, y para sostener
con datos propios el capítulo de viabilidad económica de la tesis.

## ADDED Requirements

### Requirement: Toda llamada al LLM queda contabilizada

El sistema SHALL registrar el consumo de **todas** las llamadas al modelo de
lenguaje que produce un análisis, sin excepción: las de los agentes del debate,
las del Árbitro, las del Navegador de Ensayos, la síntesis PICO y la extracción
de biomarcadores.

Un módulo que llame al proveedor por fuera del punto instrumentado MUST
considerarse un defecto, porque su consumo quedaría invisible y el total
reportado sería falso.

#### Scenario: El total cubre el análisis completo
- **WHEN** termina un análisis
- **THEN** la cantidad de llamadas registradas coincide con la cantidad de llamadas que el pipeline realmente hizo al modelo

#### Scenario: La síntesis PICO se contabiliza
- **WHEN** se ejecuta un análisis que construye la síntesis PICO con el modelo
- **THEN** esa llamada figura en el registro con su agente o paso de origen

#### Scenario: La extracción de biomarcadores se contabiliza
- **WHEN** se ejecuta un análisis que extrae biomarcadores con el modelo
- **THEN** esa llamada figura en el registro

### Requirement: Datos registrados por llamada

Cada llamada registrada SHALL incluir el paso o agente que la originó, el modelo
usado, los tokens de entrada, los tokens de salida y la latencia.

Cuando el proveedor no informe el consumo, la llamada SHALL registrarse igual,
marcada como sin datos de consumo, en lugar de omitirse: omitirla haría parecer
que el análisis costó menos de lo que costó.

#### Scenario: Llamada normal
- **WHEN** el modelo responde e informa su consumo
- **THEN** el registro tiene el agente, el modelo, tokens de entrada, tokens de salida y latencia

#### Scenario: El proveedor no informa el consumo
- **WHEN** el modelo responde sin datos de consumo
- **THEN** la llamada igual queda registrada, marcada como sin datos, y el resumen informa cuántas llamadas quedaron así

#### Scenario: Llamada fallida
- **WHEN** una llamada al modelo falla y el paso cae a su fallback
- **THEN** el intento queda registrado como fallido, para que el costo de los reintentos también sea visible

### Requirement: La telemetría no contiene datos clínicos

El registro MUST limitarse a conteos, identificadores de agente, nombres de
modelo y marcas de tiempo. MUST NOT contener el prompt enviado, la respuesta del
modelo, el texto del caso, hipótesis, ni ningún fragmento de información clínica.

El identificador de un análisis SHALL ser un valor aleatorio generado por
corrida. MUST NOT derivarse del contenido del caso, de modo que dos análisis del
mismo paciente no puedan vincularse a través del registro.

#### Scenario: Inspección del registro
- **WHEN** se revisa el archivo de telemetría de un análisis del caso de prueba
- **THEN** no aparece ninguna palabra del texto clínico, ni del prompt, ni de la respuesta del modelo

#### Scenario: Dos análisis del mismo caso
- **WHEN** se analiza dos veces exactamente el mismo texto clínico
- **THEN** los dos registros tienen identificadores distintos

### Requirement: Resumen por caso

Al terminar cada análisis el sistema SHALL escribir un resumen con el total de
llamadas, el total de tokens de entrada y salida, el desglose por agente y el
costo estimado.

El resumen SHALL quedar en un archivo local, en un formato que permita acumular
varias corridas y promediarlas sin procesamiento manual.

El sistema SHALL emitir además una línea legible al terminar, para que quien
corre el pipeline vea el consumo sin abrir el archivo.

#### Scenario: Un análisis completo
- **WHEN** termina un análisis
- **THEN** se agrega un registro con el total de llamadas, los tokens de entrada y salida, el desglose por agente y el costo estimado

#### Scenario: Varias corridas
- **WHEN** se corrieron cinco análisis
- **THEN** el archivo contiene cinco registros y se pueden promediar sin editarlos a mano

#### Scenario: Aviso al terminar
- **WHEN** termina un análisis
- **THEN** se informa por consola la cantidad de llamadas, el total de tokens y el costo estimado

### Requirement: Estimación de costo con tarifas configurables

El sistema SHALL convertir el consumo a costo usando una tabla de tarifas por
modelo, configurable sin tocar el código.

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

### Requirement: La telemetría no altera el análisis

Registrar el consumo MUST NOT cambiar el resultado del análisis ni hacerlo
fallar. Si el registro no se puede escribir —permisos, disco lleno, ruta
inexistente—, el análisis SHALL completarse igual y dejar constancia del fallo.

La telemetría MUST NOT viajar en el reporte exportado: es un dato de
infraestructura y el reporte es un documento clínico.

#### Scenario: No se puede escribir el archivo
- **WHEN** el destino del registro no es escribible
- **THEN** `POST /api/analyze` responde normalmente con su reporte y se avisa del fallo por consola

#### Scenario: El reporte no cambia
- **WHEN** se compara el reporte exportado con y sin telemetría activa
- **THEN** el contenido del reporte es el mismo y no incluye ningún campo de consumo ni de costo
