## Purpose

Que el reporte diga si la verificación bibliográfica contra PubMed corrió y, si no pudo hacerlo, por qué, para que el médico no confunda una verificación caída con referencias que no fueron confirmadas.

## ADDED Requirements

### Requirement: Estado global de la verificación

Todo reporte SHALL indicar el estado global de la verificación bibliográfica, con exactamente uno de estos valores:

- `completa`: cada consulta a PubMed del análisis respondió.
- `parcial`: al menos una consulta respondió y al menos una falló.
- `no_disponible`: todas las consultas a PubMed fallaron.
- `sin_consulta`: no hubo nada que consultar, porque ninguna fuente citada declaró PMID.

Las consultas que cuentan son la verificación inicial de las fuentes del debate y, cuando ocurre, la re-verificación de las fuentes de la Ronda 5. Un PMID que PubMed no encuentra es una respuesta (fuente `inexistente`), no un fallo de la consulta.

#### Scenario: PubMed responde todo
- **WHEN** la verificación inicial y la re-verificación de la Ronda 5 reciben respuesta de PubMed
- **THEN** el estado es `completa` y el reporte no incluye causa

#### Scenario: PubMed no responde
- **WHEN** la verificación inicial falla y no hay re-verificación de la Ronda 5
- **THEN** el estado es `no_disponible`

#### Scenario: Falla solo la re-verificación de la Ronda 5
- **WHEN** la verificación inicial recibe respuesta y la re-verificación de la Ronda 5 falla
- **THEN** el estado es `parcial`

#### Scenario: Ninguna fuente con PMID
- **WHEN** ninguna fuente citada declara PMID
- **THEN** el estado es `sin_consulta` y no se hace ninguna consulta a PubMed

#### Scenario: PMID inexistente
- **WHEN** PubMed responde y uno de los PMIDs consultados no existe
- **THEN** esa fuente queda `inexistente` y el estado no deja de ser `completa` por ese motivo

### Requirement: Causa del fallo en categorías

Cuando el estado es `parcial` o `no_disponible`, el reporte SHALL incluir la causa del fallo con exactamente una de estas categorías:

- `red`: PubMed no respondió (sin conexión, tiempo de espera agotado, conexión rechazada).
- `limite_velocidad`: PubMed rechazó la consulta por exceso de pedidos (HTTP 429).
- `configuracion`: PubMed rechazó la consulta por sus parámetros o credenciales (HTTP 400, 401 o 403); la causa más común es una `PUBMED_API_KEY` mal formada.
- `error_api`: PubMed respondió con un error propio (HTTP 5xx) o con una respuesta que no se pudo interpretar.
- `desconocida`: cualquier otro fallo.

Cuando el estado es `completa` o `sin_consulta`, el reporte MUST NOT incluir causa.

#### Scenario: Sin conexión
- **WHEN** la consulta a PubMed falla por un error de conexión o por tiempo de espera agotado
- **THEN** la causa es `red`

#### Scenario: Límite de velocidad
- **WHEN** PubMed responde HTTP 429 después de agotar los reintentos
- **THEN** la causa es `limite_velocidad`

#### Scenario: Clave mal configurada
- **WHEN** PubMed responde HTTP 400
- **THEN** la causa es `configuracion`

#### Scenario: Error del servicio
- **WHEN** PubMed responde HTTP 503
- **THEN** la causa es `error_api`

#### Scenario: Fallo no previsto
- **WHEN** la consulta falla por un error que no es de red ni una respuesta HTTP de error
- **THEN** la causa es `desconocida`

#### Scenario: Dos fallos con causas distintas
- **WHEN** la verificación inicial falla por `red` y la re-verificación de la Ronda 5 falla por `limite_velocidad`
- **THEN** el reporte informa una sola causa: la de la verificación inicial (`red`)

### Requirement: La causa nunca expone el detalle técnico

El reporte MUST NOT incluir el texto de la excepción, la URL consultada ni ningún parámetro de la consulta (en particular, el valor de `PUBMED_API_KEY`). Solo viaja la categoría.

#### Scenario: Excepción con la URL y la clave
- **WHEN** la consulta falla con un error cuyo texto contiene la URL de E-utilities y el valor de `api_key`
- **THEN** el reporte JSON y el PDF contienen la categoría de la causa y no contienen ni la URL ni el valor de la clave

### Requirement: Aviso visible en el reporte

Cuando el estado es `parcial` o `no_disponible`, `/report` y el PDF SHALL mostrar un aviso que diga que la verificación bibliográfica no corrió completa, cuántas referencias quedaron sin consultar y la causa en lenguaje llano. El aviso SHALL tener la misma visibilidad que el aviso de modo mock: en `/report`, junto a los demás avisos al comienzo del reporte; en el PDF, en la portada.

El aviso de verificación MUST NOT presentarse como un resultado positivo (color de éxito o ícono de confirmado) cuando el estado es `parcial` o `no_disponible`, y MUST NOT atribuir el fallo a una causa distinta de la informada.

#### Scenario: Verificación caída en /report
- **WHEN** se abre en `/report` un reporte con estado `no_disponible` y causa `configuracion`
- **THEN** el aviso dice que la verificación no se pudo hacer, menciona una posible clave de PubMed mal configurada y no usa el color ni el ícono de confirmado

#### Scenario: Verificación caída en el PDF
- **WHEN** se exporta a PDF un reporte con estado `no_disponible` y causa `red`
- **THEN** la portada dice que la verificación no se pudo hacer porque PubMed no respondió

#### Scenario: Verificación parcial
- **WHEN** se abre un reporte con estado `parcial` y 3 referencias sin consultar
- **THEN** el aviso dice que la verificación quedó incompleta y que 3 referencias no se pudieron consultar

#### Scenario: Verificación completa
- **WHEN** se abre un reporte con estado `completa`
- **THEN** no se muestra el aviso de verificación incompleta

### Requirement: Reportes anteriores siguen funcionando

Los campos de estado y causa SHALL ser opcionales en el contrato de exportación. Un reporte sin ellos SHALL leerse, mostrarse en `/report` y exportarse a PDF sin error, sin el aviso nuevo y sin afirmar ninguna causa.

#### Scenario: Reporte guardado antes del cambio
- **WHEN** se envía a `POST /api/report/pdf` o se abre en `/report` un reporte cuya verificación no tiene estado ni causa
- **THEN** se procesa sin error y no se muestra ninguna causa
