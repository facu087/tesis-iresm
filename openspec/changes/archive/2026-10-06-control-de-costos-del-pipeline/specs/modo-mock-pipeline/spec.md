## Purpose

Permite ejercitar el pipeline completo durante el desarrollo sin gastar cuota de
LLM ni tocar la red, con la garantía de que un reporte producido en este modo
nunca pueda confundirse con uno real.

## ADDED Requirements

### Requirement: El pipeline corre sin llamar al modelo

En modo mock, `POST /api/analyze` SHALL completar el flujo y devolver un reporte
sin realizar ninguna llamada al proveedor del modelo ni a las APIs externas.

#### Scenario: Análisis en modo mock
- **WHEN** se ejecuta un análisis con el modo mock activo
- **THEN** el endpoint devuelve un reporte completo y no se hace ninguna llamada de red

#### Scenario: Sin credenciales
- **WHEN** se ejecuta un análisis en modo mock sin ninguna clave de API configurada
- **THEN** el análisis se completa igual

### Requirement: El reporte del modo mock es reconocible

Un reporte producido en modo mock MUST ser distinguible de uno real sin
inspeccionar el código ni los logs.

El sistema MUST NOT permitir que un reporte de modo mock se presente como
resultado de un análisis efectivo: es la diferencia entre una demo y una
afirmación sobre un paciente.

#### Scenario: Marca en el reporte
- **WHEN** se genera un reporte en modo mock
- **THEN** el reporte indica explícitamente que sus hipótesis no fueron producidas por un análisis real

#### Scenario: Visible para quien lo lee
- **WHEN** se abre en la interfaz o se exporta a PDF un reporte de modo mock
- **THEN** la advertencia es visible sin tener que buscarla

### Requirement: Activación explícita

El modo mock SHALL activarse por configuración explícita y estar **desactivado
por defecto**.

El sistema MUST NOT activarlo por inferencia —por ejemplo, porque falte una
clave de API—: un fallo de configuración tiene que fallar, no producir en
silencio un reporte inventado.

#### Scenario: Default
- **WHEN** no se configura nada
- **THEN** el pipeline funciona en modo real

#### Scenario: Falta la clave del proveedor
- **WHEN** no hay clave de API configurada y el modo mock no está activo
- **THEN** el análisis falla con un error claro, en lugar de caer a respuestas grabadas

#### Scenario: Activación deliberada
- **WHEN** se activa el modo mock por configuración
- **THEN** el pipeline usa las respuestas grabadas y lo informa al arrancar

### Requirement: Resultado determinista

En modo mock, dos análisis del mismo texto clínico SHALL producir el mismo
resultado, para que sirva de base de comparación mientras se itera.

#### Scenario: Dos corridas iguales
- **WHEN** se analiza dos veces el mismo texto en modo mock
- **THEN** las hipótesis, el consenso y los ensayos son los mismos

### Requirement: El modo mock ejercita el flujo real

Las respuestas grabadas SHALL atravesar el mismo parseo, las mismas validaciones
y los mismos fallbacks que una respuesta real del modelo.

Un modo mock que devuelva el reporte final ya armado no sirve para el propósito:
no ejercita el código que se está modificando.

#### Scenario: Parseo real
- **WHEN** corre el pipeline en modo mock
- **THEN** las respuestas grabadas pasan por el mismo parseo y las mismas validaciones que las reales

#### Scenario: Un cambio que rompe el parseo se detecta
- **WHEN** se introduce un defecto en el parseo de la respuesta del modelo y se corre en modo mock
- **THEN** el modo mock lo manifiesta, en vez de devolver un reporte correcto
