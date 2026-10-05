# registro-medicos Specification

## Purpose
Permite que un médico se registre en NEXUS con sus datos de identidad y matrícula,
deje constancia de su consentimiento y quede en un estado de cuenta que refleje si
ya puede usar el pipeline clínico o todavía está bajo revisión.

## Requirements

### Requirement: Datos obligatorios del registro
El sistema SHALL exigir nombre, apellido, DNI, número de matrícula, jurisdicción de
matriculación, email institucional y contraseña para crear una cuenta de médico.
Profesión/especialidad es opcional. El sistema SHALL rechazar el registro si falta
alguno de los campos obligatorios.

#### Scenario: Registro con todos los campos obligatorios
- **WHEN** un visitante envía el formulario de registro con nombre, apellido, DNI,
  matrícula, jurisdicción, email institucional y contraseña completos
- **THEN** el sistema crea la cuenta en estado `pendiente`

#### Scenario: Registro con un campo obligatorio faltante
- **WHEN** un visitante envía el formulario de registro sin la matrícula
- **THEN** el sistema rechaza la solicitud y no crea ninguna cuenta

### Requirement: Consentimiento explícito (Ley 25.326)
El sistema SHALL exigir una aceptación explícita y afirmativa del tratamiento de
datos personales, con referencia a la finalidad (verificación profesional y uso del
pipeline), antes de crear la cuenta. El sistema SHALL registrar que el
consentimiento fue dado y en qué momento.

#### Scenario: Registro sin consentimiento marcado
- **WHEN** un visitante envía el formulario de registro sin marcar la aceptación
  del tratamiento de datos
- **THEN** el sistema rechaza la solicitud y no crea ninguna cuenta

#### Scenario: Consentimiento registrado junto con el alta
- **WHEN** un visitante envía el formulario de registro con la aceptación marcada
- **THEN** el sistema crea la cuenta y deja constancia de la fecha y hora del
  consentimiento junto con los demás datos de la cuenta

### Requirement: Unicidad de identidad
El sistema SHALL rechazar un registro cuyo DNI o email institucional ya pertenezcan
a otra cuenta existente, y SHALL rechazar un registro cuya combinación de matrícula
y jurisdicción ya pertenezca a otra cuenta existente.

#### Scenario: Registro con DNI ya utilizado
- **WHEN** se envía un registro con un DNI que ya pertenece a otra cuenta
- **THEN** el sistema rechaza la solicitud sin crear una segunda cuenta

#### Scenario: Registro con la misma matrícula y jurisdicción
- **WHEN** se envía un registro cuya matrícula y jurisdicción ya pertenecen a otra
  cuenta existente
- **THEN** el sistema rechaza la solicitud sin crear una segunda cuenta

### Requirement: Estado inicial de la cuenta
Toda cuenta de médico SHALL nacer en estado `pendiente` y SHALL permanecer sin
acceso a las funciones clínicas protegidas hasta que un administrador la apruebe.

#### Scenario: Cuenta recién creada no tiene acceso clínico
- **WHEN** un médico con una cuenta recién creada en estado `pendiente` intenta usar
  una función clínica protegida
- **THEN** el sistema le niega el acceso

### Requirement: Contraseña nunca en texto plano
El sistema SHALL almacenar la contraseña únicamente mediante un hash criptográfico
de un solo sentido con sal, y SHALL rechazar cualquier intento de autenticación con
una contraseña incorrecta, sin importar cómo esté representada internamente.

#### Scenario: Autenticación con contraseña incorrecta
- **WHEN** se intenta autenticar con el email correcto y una contraseña distinta a
  la registrada
- **THEN** el sistema rechaza la autenticación

### Requirement: Consulta del estado de la cuenta
Un médico autenticado SHALL poder consultar el estado actual de su propia cuenta:
`pendiente`, `rechazado` (con el motivo) o `verificado`.

#### Scenario: Médico pendiente consulta su estado
- **WHEN** un médico con cuenta en estado `pendiente` consulta su estado de cuenta
- **THEN** el sistema le muestra `pendiente`

#### Scenario: Médico rechazado ve el motivo del rechazo
- **WHEN** un médico con cuenta en estado `rechazado` consulta su estado de cuenta
- **THEN** el sistema le muestra el estado `rechazado` junto con el motivo que
  registró el administrador

### Requirement: Corrección y reenvío tras un rechazo
Un médico con la cuenta en estado `rechazado` SHALL poder corregir sus datos de
registro y reenviar la solicitud, y el sistema SHALL volver a dejar la cuenta en
estado `pendiente` para una nueva revisión.

#### Scenario: Reenvío tras un rechazo
- **WHEN** un médico con cuenta `rechazada` corrige sus datos y reenvía la
  solicitud
- **THEN** el sistema actualiza los datos de la cuenta y la vuelve a dejar en
  estado `pendiente`

### Requirement: Sin datos clínicos en el registro de cuentas
El almacenamiento de cuentas de médicos SHALL contener únicamente datos de
identidad, matrícula, credenciales y estado de la cuenta. El sistema SHALL NOT
persistir texto clínico, casos de pacientes ni reportes generados por el pipeline
en ese almacenamiento.

#### Scenario: El registro de cuentas no incluye datos clínicos
- **WHEN** se inspecciona el almacenamiento de cuentas de médicos
- **THEN** no contiene texto clínico de pacientes ni reportes del pipeline

### Requirement: Validación de origen en el registro
`POST /api/registro` (alta y reenvío tras un rechazo) SHALL validar el
encabezado `Origin` de la solicitud (con `Referer` como respaldo si `Origin` no
está presente) contra la lista de orígenes permitidos configurada, y SHALL
rechazar con 403 toda solicitud cuyo origen falte o no coincida.

#### Scenario: Registro con origen ajeno
- **WHEN** se envía un `POST /api/registro` con un encabezado `Origin` que no
  pertenece a la lista de orígenes permitidos
- **THEN** el sistema rechaza la solicitud con 403 sin crear ni modificar
  ninguna cuenta
