## 1. Persistencia y modelos de cuenta

- [ ] 1.1 Agregar `sqlmodel` a `backend/requirements.txt` y `NEXUS_DB_PATH` a
      `.env.example`/`.env` (ruta gitignoreada, ej. `./data/nexus.db`); verificar
      que `pip install -r backend/requirements.txt` no rompe y que `./data/`
      queda en `.gitignore`.
- [ ] 1.2 Definir los modelos SQLModel de cuenta (`CuentaMedico`: nombre,
      apellido, DNI, matrícula, jurisdicción, profesión/especialidad opcional,
      email institucional, hash de contraseña, rol `medico`/`admin`, estado
      `pendiente`/`rechazado`/`verificado`, motivo de rechazo, fecha y hora de
      consentimiento, `email_verificado: bool` en `False` por defecto y sin
      ningún flujo que lo cambie todavía — deja lugar a la verificación por
      correo diferida a un cambio posterior, ver `design.md` Non-Goals) con
      tipado estático y docstrings en español; verificar con un test que crear
      una instancia y persistirla en una base SQLite temporal funciona
      (`tests/test_cuentas_modelo.py`).
- [ ] 1.3 Definir el modelo de auditoría (`DecisionAuditoria`: admin, cuenta
      afectada, fecha y hora, decisión, motivo o nota, fuente consultada) y el
      modelo de sesión (`Sesion`: id opaco, cuenta, expiración); verificar con
      un test que ambos se crean y consultan correctamente.
- [ ] 1.4 Crear el motor de base de datos y `create_all()` en el arranque de
      `backend/main.py`; verificar que levantar la app crea el archivo SQLite
      con las tablas esperadas si no existía.

## 2. Autenticación

- [ ] 2.1 Agregar `argon2-cffi` a `backend/requirements.txt`; implementar hash y
      verificación de contraseña; verificar con un test que una contraseña
      hasheada nunca aparece en texto plano y que `verify()` rechaza una
      contraseña incorrecta (spec `autenticacion-medicos` — Requirement:
      Contraseña nunca en texto plano).
- [ ] 2.2 Implementar `POST /api/login`: valida credenciales contra cualquier
      estado de cuenta, sin filtrar existencia de usuario (mismo mensaje
      genérico ante email inexistente o contraseña incorrecta); verificar con
      tests que cubran login exitoso, contraseña incorrecta y email inexistente
      con la misma respuesta (spec `autenticacion-medicos`).
- [ ] 2.3 Implementar la sesión: creación de fila en `Sesion` al loguear,
      cookie `httpOnly`/`SameSite=Lax`/`Secure` condicional a
      `ENVIRONMENT=production`, dependencia FastAPI que resuelve la sesión
      activa y expone la cuenta y el rol, y `POST /api/logout` que la invalida;
      verificar con tests que una sesión identifica a la cuenta en solicitudes
      posteriores, que expira pasado `SESSION_TTL_MINUTES` y que el logout la
      invalida.
- [ ] 2.4 Implementar el límite de intentos de login fallidos por cuenta
      (contador y bloqueo temporal persistidos en SQLite, no en el limitador de
      APIs externas de `backend/external/rate_limiter.py` — ver `design.md`
      Decisión D3/rate limiting: resuelve un problema distinto); verificar con
      un test que superar el límite bloquea intentos posteriores aunque las
      credenciales sean correctas.

## 3. Validación de origen (mitigación CSRF)

- [ ] 3.1 Implementar una dependencia/función que valide el encabezado `Origin`
      de la solicitud (con `Referer` como respaldo si `Origin` no está
      presente) contra `ALLOWED_ORIGINS` (la misma lista que ya usa CORS en
      `backend/main.py`) y rechace con 403 si falta o no coincide; aplicarla a
      `POST /api/registro`, `POST /api/login`, `POST /api/logout`,
      `POST /api/admin/cuentas/{id}/aprobar` y
      `POST /api/admin/cuentas/{id}/rechazar` (ver `design.md` D3 — corregido);
      verificar con tests que cada uno de esos endpoints rechaza con 403 un
      origen ajeno y acepta uno permitido.
- [ ] 3.2 Aplicar la misma validación a `POST /api/analyze` y
      `POST /api/report/pdf`, sin importar el tipo de contenido (spec
      `proteccion-analisis-clinico` — Requirement: Validación de origen en el
      análisis y la exportación); verificar con un test que una solicitud
      `multipart/form-data` a `/api/analyze` con un `Origin` ajeno y una cookie
      de sesión válida de un médico verificado es rechazada con 403 sin
      ejecutar el pipeline, y que con un `Origin` permitido continúa a las
      verificaciones de sesión y estado de cuenta.

## 4. Registro de médicos

- [ ] 4.1 Implementar `POST /api/registro`: valida campos obligatorios,
      unicidad de DNI/email/matrícula+jurisdicción, exige el consentimiento
      explícito (Ley 25.326) y crea la cuenta en estado `pendiente`; verificar
      con tests que cubran alta exitosa, campo faltante, sin consentimiento, DNI
      duplicado y matrícula+jurisdicción duplicada (spec `registro-medicos`).
- [ ] 4.2 Implementar `GET /api/cuenta` (requiere sesión, cualquier estado):
      devuelve estado actual y, si está `rechazado`, el motivo; verificar con
      tests para los tres estados.
- [ ] 4.3 Implementar el reenvío tras rechazo (`PUT /api/registro` o
      equivalente) que permite corregir los datos de una cuenta `rechazada` y la
      vuelve a `pendiente`; verificar con un test del ciclo completo
      rechazo → corrección → pendiente.
- [ ] 4.4 Test dedicado que confirme que el almacenamiento de cuentas no admite
      ni expone ningún campo de texto clínico o de reporte (spec
      `registro-medicos` — Requirement: Sin datos clínicos en el registro de
      cuentas).

## 5. Revisión admin y auditoría

- [ ] 5.1 Implementar la dependencia de autorización que exige rol `admin` y
      aplicarla a las rutas de revisión; verificar con un test que una cuenta
      `medico` recibe 403 y una `admin` accede.
- [ ] 5.2 Implementar `GET /api/admin/pendientes` (lista cuentas `pendiente` con
      sus datos de registro) y la configuración del enlace del buscador
      provincial (variable de entorno o config, puede quedar sin definir);
      verificar con un test que el listado no falla con el enlace provincial
      vacío.
- [ ] 5.3 Implementar `POST /api/admin/cuentas/{id}/aprobar` (exige indicar la
      fuente consultada, pasa la cuenta a `verificado`) y
      `POST /api/admin/cuentas/{id}/rechazar` (exige motivo no vacío, pasa la
      cuenta a `rechazado`); verificar con tests de aprobación, rechazo con
      motivo y rechazo sin motivo (debe fallar).
- [ ] 5.4 Registrar un `DecisionAuditoria` en cada aprobación y rechazo (quién,
      cuándo, decisión, motivo/nota, fuente); verificar con un test que ambas
      operaciones generan exactamente un registro de auditoría con esos datos.
- [ ] 5.5 Implementar el comando CLI `python -m backend.cli crear-admin` (pide
      credenciales por parámetro o prompt, falla si ya hay una cuenta con ese
      email, no incluye ningún usuario/contraseña por defecto); verificar con un
      test que ejecutarlo crea la cuenta admin y que una instalación sin
      ejecutarlo no tiene ninguna.

## 6. Protección del pipeline clínico

- [ ] 6.1 Implementar la dependencia que exige sesión de médico en estado
      `verificado` y aplicarla a `POST /api/analyze`; verificar con tests para
      sin sesión (401), médico `pendiente`/`rechazado` (403), admin sin cuenta
      médico verificada (403) y médico `verificado` (200, spec
      `proteccion-analisis-clinico`).
- [ ] 6.2 Aplicar la misma dependencia a `POST /api/report/pdf`; verificar con
      un test de acceso sin sesión (401) y con médico verificado (200).
- [ ] 6.3 Actualizar `tests/test_api.py` (y los tests existentes que llaman a
      `/api/analyze` sin autenticación) para loguearse primero; verificar que la
      suite completa de tests del pipeline sigue pasando con el gate activo.

## 7. Frontend

- [ ] 7.1 Antes de tocar rutas o middleware: correr `npm install` en
      `frontend/` si `node_modules/` no está presente y leer
      `frontend/node_modules/next/dist/docs/` sobre App Router / middleware de
      Next 16.2.7 (ver `design.md` — Riesgo operativo Next.js 16).
- [ ] 7.2 Confirmar que el cambio `landing-explicativa` ya está mergeado a
      `develop` (existe `/analizar`) antes de continuar con las tareas de
      frontend de este grupo; si no lo está, dejar el grupo 7 pendiente y
      avisar.
- [ ] 7.3 Crear `/registro` (formulario con los campos obligatorios y el
      checkbox de consentimiento) y `/ingresar`; verificar con
      `npm run build` sin errores y una captura de cada vista.
- [ ] 7.4 Crear `/cuenta` (muestra `pendiente` / `rechazado` con motivo y opción
      de corregir y reenviar / `verificado`); verificar con `npm run build` y
      capturas de los tres estados.
- [ ] 7.5 Crear `/admin/pendientes` (lista, enlaces a los buscadores públicos,
      aprobar/rechazar con motivo obligatorio); verificar con `npm run build` y
      una captura.
- [ ] 7.6 Proteger `/analizar` en el cliente (redirige si no hay sesión de
      médico verificado) — documentado como capa de UX, no de seguridad (spec
      `proteccion-analisis-clinico` — Requirement: La aplicación no es el
      límite de seguridad); verificar manualmente que redirige sin sesión.
- [ ] 7.7 Actualizar `frontend/src/lib/api.ts`: mandar `credentials: "include"`
      en los `fetch` a endpoints protegidos y agregar los llamados a
      registro/login/logout/estado de cuenta/admin; verificar con
      `npm run build`.

## 8. Evidencia y pruebas de extremo a extremo

- [ ] 8.1 Escribir `scripts/demo_registro_medicos.py`: registro → intento de
      análisis rechazado (pendiente) → aprobación admin con auditoría →
      análisis permitido → rechazo de otra cuenta con motivo → reenvío, todo
      contra una base SQLite temporal y sin ninguna llamada a un LLM; verificar
      que corre con `python3 scripts/demo_registro_medicos.py` y deja artefactos
      en `output/`.
- [ ] 8.2 Verificación integral: correr toda la suite de `tests/` nueva y
      existente y confirmar que pasa completa, incluida la protección de
      `/api/analyze` y `/api/report/pdf` (sesión, estado de cuenta y origen).

## 9. Documentación

- [ ] 9.1 Actualizar `.claude/CLAUDE.md` (estado del Sprint 4, nuevas
      variables de entorno) y `.claude/backlog.md` con el estado de esta
      tarjeta/estas tarjetas de Trello.
- [ ] 9.2 Actualizar `.claude/stack.md` con las decisiones de esta propuesta
      (SQLModel/SQLite, argon2-cffi, sesión server-side, validación de origen)
      siguiendo el mismo formato de justificación que las decisiones
      existentes.
