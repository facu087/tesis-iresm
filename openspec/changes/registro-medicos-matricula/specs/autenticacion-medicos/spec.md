## Purpose

Permite que médicos y administradores inicien sesión con sus credenciales y
mantiene una sesión autenticada que las funciones protegidas puedan usar para
identificar a quién llama y con qué rol, sin filtrar información a quien no tiene
una cuenta.

## ADDED Requirements

### Requirement: Login con email institucional y contraseña
El sistema SHALL autenticar a una cuenta existente (médico o admin) mediante su
email institucional y contraseña, sin importar el estado de la cuenta de médico
(`pendiente`, `rechazado` o `verificado`): el login solo depende de que las
credenciales sean correctas.

#### Scenario: Login exitoso
- **WHEN** se envían el email institucional y la contraseña correctos de una
  cuenta existente
- **THEN** el sistema inicia sesión para esa cuenta

#### Scenario: Médico pendiente puede iniciar sesión para ver su estado
- **WHEN** un médico con cuenta en estado `pendiente` envía sus credenciales
  correctas
- **THEN** el sistema inicia sesión, aunque esa sesión no tenga acceso a las
  funciones clínicas protegidas

### Requirement: Sin enumeración de usuarios
El sistema SHALL devolver el mismo mensaje de error genérico tanto si el email no
corresponde a ninguna cuenta como si corresponde a una cuenta pero la contraseña es
incorrecta.

#### Scenario: Email inexistente
- **WHEN** se intenta iniciar sesión con un email que no pertenece a ninguna cuenta
- **THEN** el sistema devuelve el mismo mensaje de error genérico que usaría para
  una contraseña incorrecta

#### Scenario: Contraseña incorrecta
- **WHEN** se intenta iniciar sesión con un email existente y una contraseña
  incorrecta
- **THEN** el sistema devuelve el mismo mensaje de error genérico que usaría para
  un email inexistente

### Requirement: Sesión tras login exitoso
Tras un login exitoso, el sistema SHALL emitir una sesión (cookie de servidor
httpOnly o token firmado) asociada a esa cuenta, de forma que las solicitudes
posteriores dentro de esa sesión se identifiquen sin reenviar la contraseña.

#### Scenario: Solicitudes posteriores usan la sesión activa
- **WHEN** una cuenta ya inició sesión y hace una nueva solicitud dentro de esa
  sesión
- **THEN** el sistema la identifica sin pedir la contraseña de nuevo

#### Scenario: Cierre de sesión
- **WHEN** una cuenta con sesión activa cierra sesión
- **THEN** esa sesión deja de ser válida para solicitudes posteriores

### Requirement: Expiración de la sesión
Toda sesión SHALL expirar tras un tiempo configurable de vida. Una sesión expirada
SHALL NOT identificar a ninguna cuenta.

#### Scenario: Solicitud con sesión expirada
- **WHEN** se hace una solicitud usando una sesión cuyo tiempo de vida ya venció
- **THEN** el sistema la trata como si no hubiera sesión

### Requirement: Límite de intentos de login
El sistema SHALL limitar los intentos de login fallidos consecutivos sobre una
misma cuenta o origen, y SHALL bloquear temporalmente nuevos intentos al superar
ese límite.

#### Scenario: Bloqueo tras intentos fallidos repetidos
- **WHEN** se superan los intentos de login fallidos permitidos sobre una misma
  cuenta en un período corto
- **THEN** el sistema rechaza nuevos intentos de login sobre esa cuenta durante un
  período de bloqueo, aunque las credenciales sean correctas

### Requirement: Rol de la cuenta
Toda cuenta SHALL tener exactamente un rol, `medico` o `admin`, y ese rol SHALL
quedar disponible para las funciones que autorizan el acceso.

#### Scenario: Sesión de una cuenta admin
- **WHEN** inicia sesión una cuenta con rol `admin`
- **THEN** la sesión queda identificada con rol `admin`

#### Scenario: Sesión de una cuenta médico
- **WHEN** inicia sesión una cuenta con rol `medico`
- **THEN** la sesión queda identificada con rol `medico`
