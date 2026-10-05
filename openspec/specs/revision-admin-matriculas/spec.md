# revision-admin-matriculas Specification

## Purpose
Permite que un rol administrador dentro de la aplicación revise las cuentas de
médicos pendientes contra los buscadores públicos de matrícula, decida aprobar o
rechazar cada una dejando constancia auditable de la decisión, y que exista una
forma segura de dar de alta al primer administrador.

## Requirements

### Requirement: Acceso restringido a administradores
Las funciones de revisión de cuentas pendientes SHALL estar restringidas a
cuentas con rol `admin`. El sistema SHALL rechazar el acceso de una cuenta con rol
`medico`.

#### Scenario: Médico intenta acceder a la revisión de pendientes
- **WHEN** una cuenta con rol `medico` intenta acceder a la pantalla o función de
  revisión de cuentas pendientes
- **THEN** el sistema rechaza el acceso

#### Scenario: Admin accede a la revisión de pendientes
- **WHEN** una cuenta con rol `admin` accede a la función de revisión de cuentas
  pendientes
- **THEN** el sistema le muestra la lista de cuentas en estado `pendiente`

### Requirement: Listado de cuentas pendientes
El sistema SHALL listar, para un administrador, todas las cuentas de médico en
estado `pendiente` junto con los datos de registro relevantes para verificarlas
(nombre, apellido, DNI, matrícula, jurisdicción, profesión/especialidad si se
informó, email institucional).

#### Scenario: Listado incluye los datos de registro
- **WHEN** un administrador abre la lista de cuentas pendientes
- **THEN** cada cuenta listada muestra sus datos de registro relevantes para la
  verificación

### Requirement: Enlaces a los buscadores públicos de matrícula
Cada cuenta pendiente SHALL exponer al administrador un enlace directo al Buscador
Nacional de Profesionales de la Salud (REFEPS). El enlace al buscador de la
jurisdicción provincial correspondiente SHALL ser configurable y SHALL permitir
quedar sin definir sin que la pantalla deje de funcionar.

#### Scenario: Enlace al Buscador Nacional REFEPS
- **WHEN** un administrador revisa una cuenta pendiente
- **THEN** el sistema le ofrece un enlace directo al Buscador Nacional REFEPS

#### Scenario: Enlace provincial no configurado
- **WHEN** el enlace del buscador provincial no está configurado para la
  jurisdicción de una cuenta pendiente
- **THEN** el sistema sigue mostrando el resto de la revisión de esa cuenta sin
  error

### Requirement: Aprobación de una cuenta pendiente
Un administrador SHALL poder aprobar una cuenta en estado `pendiente`, y el
sistema SHALL registrar qué fuente dice el administrador haber consultado. Al
aprobarla, la cuenta SHALL pasar a estado `verificado`.

#### Scenario: Aprobación de una cuenta pendiente
- **WHEN** un administrador aprueba una cuenta en estado `pendiente` indicando la
  fuente consultada
- **THEN** la cuenta pasa a estado `verificado`

### Requirement: Rechazo con motivo obligatorio
Un administrador SHALL poder rechazar una cuenta en estado `pendiente`, pero el
sistema SHALL exigir un motivo no vacío para el rechazo y SHALL rechazar el
intento si no se provee ninguno. La cuenta rechazada SHALL pasar a estado
`rechazado` y el motivo SHALL quedar visible para el médico dueño de la cuenta.

#### Scenario: Intento de rechazo sin motivo
- **WHEN** un administrador intenta rechazar una cuenta pendiente sin indicar un
  motivo
- **THEN** el sistema rechaza la operación y la cuenta permanece en `pendiente`

#### Scenario: Rechazo con motivo
- **WHEN** un administrador rechaza una cuenta pendiente indicando un motivo
- **THEN** la cuenta pasa a estado `rechazado` y ese motivo queda visible para el
  médico

### Requirement: Auditoría de cada decisión
Toda aprobación o rechazo SHALL generar un registro de auditoría inmutable con,
como mínimo: qué administrador decidió, cuándo, qué decisión tomó, el motivo (en
un rechazo) o la nota (en una aprobación), y qué fuente dice haber consultado. El
sistema SHALL NOT permitir aprobar o rechazar una cuenta sin generar ese registro.

#### Scenario: Auditoría de una aprobación
- **WHEN** un administrador aprueba una cuenta pendiente
- **THEN** el sistema genera un registro de auditoría con el administrador, la
  fecha y hora, la decisión y la fuente consultada

#### Scenario: Auditoría de un rechazo
- **WHEN** un administrador rechaza una cuenta pendiente con un motivo
- **THEN** el sistema genera un registro de auditoría con el administrador, la
  fecha y hora, la decisión y el motivo

### Requirement: Alta del primer administrador
El sistema SHALL proveer un comando de línea de comandos de uso único para crear
la primera cuenta administradora cuando todavía no existe ninguna. El sistema
SHALL NOT incluir ninguna cuenta administradora predefinida ni contraseña por
defecto.

#### Scenario: Creación del primer administrador
- **WHEN** se ejecuta el comando de alta de administrador y todavía no existe
  ninguna cuenta con rol `admin`
- **THEN** el sistema crea la cuenta administradora con las credenciales provistas
  en ese momento

#### Scenario: Sin cuenta administradora por defecto
- **WHEN** se inspecciona una instalación recién desplegada sin haber ejecutado el
  comando de alta de administrador
- **THEN** no existe ninguna cuenta con rol `admin`

### Requirement: Validación de origen en aprobar y rechazar
Las operaciones de aprobar y rechazar una cuenta pendiente SHALL validar el
encabezado `Origin` de la solicitud (con `Referer` como respaldo si `Origin` no
está presente) contra la lista de orígenes permitidos configurada, y SHALL
rechazar con 403 toda solicitud cuyo origen falte o no coincida, incluso con una
sesión de administrador válida.

#### Scenario: Aprobación o rechazo con origen ajeno
- **WHEN** un administrador con sesión válida envía una aprobación o un rechazo
  con un encabezado `Origin` que no pertenece a la lista de orígenes permitidos
- **THEN** el sistema rechaza la operación con 403 y no cambia el estado de la
  cuenta ni genera un registro de auditoría
