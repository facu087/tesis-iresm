## Purpose

Garantiza que el pipeline de generación de hipótesis clínicas y la exportación de
sus resultados solo sean alcanzables por médicos autenticados y verificados,
controlado por el backend y sin depender de que el frontend oculte el acceso.

## ADDED Requirements

### Requirement: Sesión autenticada obligatoria para analizar
`POST /api/analyze` SHALL rechazar cualquier solicitud que no incluya una sesión
autenticada válida.

#### Scenario: Solicitud sin sesión
- **WHEN** se llama a `POST /api/analyze` sin una sesión autenticada
- **THEN** el sistema rechaza la solicitud sin ejecutar el pipeline

### Requirement: Solo médicos verificados pueden analizar
`POST /api/analyze` SHALL rechazar una sesión autenticada cuya cuenta no sea un
médico en estado `verificado`. Esto incluye una cuenta médico en estado
`pendiente` o `rechazado`, y una cuenta con rol `admin` que no tenga además una
cuenta de médico verificada.

#### Scenario: Médico pendiente intenta analizar
- **WHEN** un médico con cuenta en estado `pendiente` llama a `POST /api/analyze`
  con una sesión autenticada
- **THEN** el sistema rechaza la solicitud sin ejecutar el pipeline

#### Scenario: Médico verificado analiza un caso
- **WHEN** un médico con cuenta en estado `verificado` llama a `POST /api/analyze`
  con una sesión autenticada
- **THEN** el sistema ejecuta el pipeline y devuelve el reporte

#### Scenario: Cuenta admin sin verificación de médico intenta analizar
- **WHEN** una sesión con rol `admin` sin una cuenta de médico `verificado` llama a
  `POST /api/analyze`
- **THEN** el sistema rechaza la solicitud sin ejecutar el pipeline

### Requirement: Misma exigencia sobre la exportación a PDF
`POST /api/report/pdf` SHALL exigir la misma sesión autenticada de un médico
`verificado` que `POST /api/analyze`, para mantener un único límite de acceso
sobre los datos clínicos del reporte en lugar de dejar un endpoint sin proteger.

#### Scenario: Exportación a PDF sin sesión
- **WHEN** se llama a `POST /api/report/pdf` sin una sesión autenticada
- **THEN** el sistema rechaza la solicitud sin generar el PDF

### Requirement: Validación de origen en el análisis y la exportación
`POST /api/analyze` y `POST /api/report/pdf` SHALL validar el encabezado
`Origin` de la solicitud (usando `Referer` como respaldo si `Origin` no está
presente) contra la lista de orígenes permitidos configurada, y SHALL rechazar
con 403 toda solicitud cuyo origen falte o no coincida con esa lista, incluso si
trae una cookie de sesión válida. Esta validación SHALL aplicarse
independientemente del tipo de contenido de la solicitud (`multipart/form-data`
incluido), porque una solicitud `multipart/form-data` no dispara verificación de
origen por parte de CORS.

#### Scenario: Solicitud multipart con origen ajeno y sesión válida
- **WHEN** se envía un `POST /api/analyze` con datos `multipart/form-data`, una
  cookie de sesión válida de un médico verificado, y un encabezado `Origin` que no
  pertenece a la lista de orígenes permitidos
- **THEN** el sistema rechaza la solicitud con 403 sin ejecutar el pipeline

#### Scenario: Solicitud con origen permitido continúa la verificación normal
- **WHEN** se envía un `POST /api/analyze` con un encabezado `Origin` que sí
  pertenece a la lista de orígenes permitidos
- **THEN** el sistema continúa con las verificaciones de sesión y estado de la
  cuenta descriptas en los demás requisitos de este capability

#### Scenario: Exportación a PDF con origen ajeno
- **WHEN** se envía un `POST /api/report/pdf` con un encabezado `Origin` que no
  pertenece a la lista de orígenes permitidos
- **THEN** el sistema rechaza la solicitud con 403 sin generar el PDF

### Requirement: La aplicación no es el límite de seguridad
El sistema SHALL aplicar estas exigencias de forma independiente de cualquier
comportamiento del frontend. Ocultar un botón o una ruta en la interfaz SHALL NOT
sustituir el control del backend.

#### Scenario: Acceso directo a la API sin pasar por el frontend
- **WHEN** se llama directamente a `POST /api/analyze` sin usar la interfaz web,
  sin una sesión autenticada de un médico verificado
- **THEN** el sistema rechaza la solicitud igual que si se hubiera intentado desde
  el frontend
