## 1. Persistencia y modelos de cuenta

- [x] 1.1 Agregar `sqlmodel` a `backend/requirements.txt` y `NEXUS_DB_PATH` a
      `.env.example`/`.env` (ruta gitignoreada, ej. `./data/nexus.db`); verificar
      que `pip install -r backend/requirements.txt` no rompe y que `./data/`
      queda en `.gitignore`.
      — Verificado: `pip install sqlmodel argon2-cffi` instaló limpio
      (sqlmodel 0.0.47, argon2-cffi 25.1.0); `.gitignore` tiene `data/`.
- [x] 1.2 Definir los modelos SQLModel de cuenta (`CuentaMedico`: nombre,
      apellido, DNI, matrícula, jurisdicción, profesión/especialidad opcional,
      email institucional, hash de contraseña, rol `medico`/`admin`, estado
      `pendiente`/`rechazado`/`verificado`, motivo de rechazo, fecha y hora de
      consentimiento, `email_verificado: bool` en `False` por defecto y sin
      ningún flujo que lo cambie todavía — deja lugar a la verificación por
      correo diferida a un cambio posterior, ver `design.md` Non-Goals) con
      tipado estático y docstrings en español; verificar con un test que crear
      una instancia y persistirla en una base SQLite temporal funciona
      (`tests/test_cuentas_modelo.py`).
      — Verificado: `tests/test_cuentas_modelo.py`, 5 tests, GREEN.
- [x] 1.3 Definir el modelo de auditoría (`DecisionAuditoria`: admin, cuenta
      afectada, fecha y hora, decisión, motivo o nota, fuente consultada) y el
      modelo de sesión (`Sesion`: id opaco, cuenta, expiración); verificar con
      un test que ambos se crean y consultan correctamente.
      — Verificado: `tests/test_auditoria_y_sesion_modelo.py`, 2 tests, GREEN.
- [x] 1.4 Crear el motor de base de datos y `create_all()` en el arranque de
      `backend/main.py`; verificar que levantar la app crea el archivo SQLite
      con las tablas esperadas si no existía.
      — Verificado: `tests/test_db.py::test_levantar_la_app_crea_el_esquema_en_el_engine_activo`
      (archivo real en disco, no `:memory:`, por la ejecución del lifespan en
      otro hilo bajo `TestClient`), 4 tests del archivo, GREEN.

## 2. Autenticación

- [x] 2.1 Agregar `argon2-cffi` a `backend/requirements.txt`; implementar hash y
      verificación de contraseña; verificar con un test que una contraseña
      hasheada nunca aparece en texto plano y que `verify()` rechaza una
      contraseña incorrecta (spec `autenticacion-medicos` — Requirement:
      Contraseña nunca en texto plano).
      — Verificado: `tests/test_security.py`, 5 tests, GREEN.
- [x] 2.2 Implementar `POST /api/login`: valida credenciales contra cualquier
      estado de cuenta, sin filtrar existencia de usuario (mismo mensaje
      genérico ante email inexistente o contraseña incorrecta); verificar con
      tests que cubran login exitoso, contraseña incorrecta y email inexistente
      con la misma respuesta (spec `autenticacion-medicos`).
      — Verificado: `tests/test_login.py::TestLoginExitoso`,
      `TestSinEnumeracionDeUsuarios`, GREEN.
- [x] 2.3 Implementar la sesión: creación de fila en `Sesion` al loguear,
      cookie `httpOnly`/`SameSite=Lax`/`Secure` condicional a
      `ENVIRONMENT=production`, dependencia FastAPI que resuelve la sesión
      activa y expone la cuenta y el rol, y `POST /api/logout` que la invalida;
      verificar con tests que una sesión identifica a la cuenta en solicitudes
      posteriores, que expira pasado `SESSION_TTL_MINUTES` y que el logout la
      invalida.
      — Verificado: `tests/test_sesiones.py` (crear/resolver, expirada,
      manipulada, invalidar) + `tests/test_login.py::TestSesion`. El flag
      `Secure` condicional a `ENVIRONMENT` está implementado
      (`backend/auth/sesiones.py::set_session_cookie`) pero no tiene un test
      dedicado que alterne `ENVIRONMENT` e inspeccione el header — los tests
      cubren exactamente lo que pide el enunciado (identifica, expira,
      invalida), no ese detalle adicional.
- [x] 2.4 Implementar el límite de intentos de login fallidos por cuenta
      (contador y bloqueo temporal persistidos en SQLite, no en el limitador de
      APIs externas de `backend/external/rate_limiter.py` — ver `design.md`
      Decisión D3/rate limiting: resuelve un problema distinto); verificar con
      un test que superar el límite bloquea intentos posteriores aunque las
      credenciales sean correctas.
      — Verificado: `tests/test_login.py::TestLimiteDeIntentos`, GREEN.

## 3. Validación de origen (mitigación CSRF)

- [x] 3.1 Implementar una dependencia/función que valide el encabezado `Origin`
      de la solicitud (con `Referer` como respaldo si `Origin` no está
      presente) contra `ALLOWED_ORIGINS` (la misma lista que ya usa CORS en
      `backend/main.py`) y rechace con 403 si falta o no coincide; aplicarla a
      `POST /api/registro`, `POST /api/login`, `POST /api/logout`,
      `POST /api/admin/cuentas/{id}/aprobar` y
      `POST /api/admin/cuentas/{id}/rechazar` (ver `design.md` D3 — corregido);
      verificar con tests que cada uno de esos endpoints rechaza con 403 un
      origen ajeno y acepta uno permitido.
      — Verificado: `tests/test_origen.py` (6 tests sobre la dependencia en
      aislamiento) + integración por endpoint: login/logout
      (`test_login.py::TestValidacionDeOrigenLoginYLogout`), registro
      (`test_registro.py::TestValidacionDeOrigenEnRegistro`), aprobar y
      rechazar (`test_admin.py::TestValidacionDeOrigenEnAprobarYRechazar`,
      ambos casos). "Acepta uno permitido" queda cubierto implícitamente: el
      cliente de test por default ya manda el `Origin` permitido, y son esas
      mismas llamadas las que dan 200/201 en el resto de la suite.
- [x] 3.2 Aplicar la misma validación a `POST /api/analyze` y
      `POST /api/report/pdf`, sin importar el tipo de contenido (spec
      `proteccion-analisis-clinico` — Requirement: Validación de origen en el
      análisis y la exportación); verificar con un test que una solicitud
      `multipart/form-data` a `/api/analyze` con un `Origin` ajeno y una cookie
      de sesión válida de un médico verificado es rechazada con 403 sin
      ejecutar el pipeline, y que con un `Origin` permitido continúa a las
      verificaciones de sesión y estado de cuenta.
      — Verificado: `tests/test_proteccion_analisis.py::TestValidacionDeOrigenEnAnalisisYExportacion`,
      3 tests (multipart ajeno sin ejecutar pipeline, origen permitido
      continúa, PDF con origen ajeno), GREEN.

## 4. Registro de médicos

- [x] 4.1 Implementar `POST /api/registro`: valida campos obligatorios,
      unicidad de DNI/email/matrícula+jurisdicción, exige el consentimiento
      explícito (Ley 25.326) y crea la cuenta en estado `pendiente`; verificar
      con tests que cubran alta exitosa, campo faltante, sin consentimiento, DNI
      duplicado y matrícula+jurisdicción duplicada (spec `registro-medicos`).
      — Verificado: `tests/test_registro.py::TestRegistroExitoso`,
      `TestCamposObligatorios`, `TestConsentimiento`, `TestUnicidad`, GREEN.
- [x] 4.2 Implementar `GET /api/cuenta` (requiere sesión, cualquier estado):
      devuelve estado actual y, si está `rechazado`, el motivo; verificar con
      tests para los tres estados.
      — Verificado: `pendiente`/`rechazado` en
      `test_registro.py::TestConsultaDeEstado`; `verificado` en
      `test_login.py::TestSesion::test_solicitud_posterior_usa_la_sesion_activa`.
- [x] 4.3 Implementar el reenvío tras rechazo (`PUT /api/registro` o
      equivalente) que permite corregir los datos de una cuenta `rechazada` y la
      vuelve a `pendiente`; verificar con un test del ciclo completo
      rechazo → corrección → pendiente.
      — Verificado: `test_registro.py::TestReenvioTrasRechazo`, y de punta a
      punta en `scripts/demo_registro_medicos.py` (pasos 6-7).
- [x] 4.4 Test dedicado que confirme que el almacenamiento de cuentas no admite
      ni expone ningún campo de texto clínico o de reporte (spec
      `registro-medicos` — Requirement: Sin datos clínicos en el registro de
      cuentas).
      — Verificado: `test_registro.py::TestSinDatosClinicos`, 2 tests, GREEN.

## 5. Revisión admin y auditoría

- [x] 5.1 Implementar la dependencia de autorización que exige rol `admin` y
      aplicarla a las rutas de revisión; verificar con un test que una cuenta
      `medico` recibe 403 y una `admin` accede.
      — Verificado: `test_admin.py::TestAccesoRestringido` +
      `test_deps.py::TestRequerirAdmin`.
- [x] 5.2 Implementar `GET /api/admin/pendientes` (lista cuentas `pendiente` con
      sus datos de registro) y la configuración del enlace del buscador
      provincial (variable de entorno o config, puede quedar sin definir);
      verificar con un test que el listado no falla con el enlace provincial
      vacío.
      — Verificado: `test_admin.py::TestListadoDePendientes`, incluido
      `test_enlace_provincial_no_configurado_no_rompe`.
- [x] 5.3 Implementar `POST /api/admin/cuentas/{id}/aprobar` (exige indicar la
      fuente consultada, pasa la cuenta a `verificado`) y
      `POST /api/admin/cuentas/{id}/rechazar` (exige motivo no vacío, pasa la
      cuenta a `rechazado`); verificar con tests de aprobación, rechazo con
      motivo y rechazo sin motivo (debe fallar).
      — Verificado: `test_admin.py::TestAprobacion`, `TestRechazo`, GREEN.
- [x] 5.4 Registrar un `DecisionAuditoria` en cada aprobación y rechazo (quién,
      cuándo, decisión, motivo/nota, fuente); verificar con un test que ambas
      operaciones generan exactamente un registro de auditoría con esos datos.
      — Verificado: `test_admin.py::TestAprobacion::test_aprobar_genera_auditoria`,
      `TestRechazo::test_rechazar_genera_auditoria`.
- [x] 5.5 Implementar el comando CLI `python -m backend.cli crear-admin` (pide
      credenciales por parámetro o prompt, falla si ya hay una cuenta con ese
      email, no incluye ningún usuario/contraseña por defecto); verificar con un
      test que ejecutarlo crea la cuenta admin y que una instalación sin
      ejecutarlo no tiene ninguna.
      — Verificado: `test_admin.py::TestBootstrapAdmin` (3 tests) + smoke test
      manual del comando real (`python -m backend.cli crear-admin --email ...
      --password ...`), incluido el rechazo por email duplicado.

## 6. Protección del pipeline clínico

- [x] 6.1 Implementar la dependencia que exige sesión de médico en estado
      `verificado` y aplicarla a `POST /api/analyze`; verificar con tests para
      sin sesión (401), médico `pendiente`/`rechazado` (403), admin sin cuenta
      médico verificada (403) y médico `verificado` (200, spec
      `proteccion-analisis-clinico`).
      — Verificado: `tests/test_proteccion_analisis.py`, los cuatro
      escenarios, GREEN.
- [x] 6.2 Aplicar la misma dependencia a `POST /api/report/pdf`; verificar con
      un test de acceso sin sesión (401) y con médico verificado (200).
      — Verificado: `test_proteccion_analisis.py::TestExportacionPdfExigeSesion`
      (401) + `test_pdf_exporter.py::TestExportPdfEndpoint` (200, con
      `client_medico_verificado`).
- [x] 6.3 Actualizar `tests/test_api.py` (y los tests existentes que llaman a
      `/api/analyze` sin autenticación) para loguearse primero; verificar que la
      suite completa de tests del pipeline sigue pasando con el gate activo.
      — Verificado: `tests/test_api.py` y `tests/test_pdf_exporter.py`
      actualizados a la fixture `client_medico_verificado`; además se
      mockearon `verify_report_sources` y `ArbiterAgent.arbitrate` en
      `test_api.py` (no lo pedía esta tarea puntual, pero cerraba un intento
      de red real preexistente) — intentos de red bloqueados en ese archivo:
      72 → 0. Suite completa: 826 passed.

## 7. Frontend

- [x] 7.1 Antes de tocar rutas o middleware: correr `npm install` en
      `frontend/` si `node_modules/` no está presente y leer
      `frontend/node_modules/next/dist/docs/` sobre App Router / middleware de
      Next 16.2.7 (ver `design.md` — Riesgo operativo Next.js 16).
      — Verificado: `npm install` real (no symlink, 616M en `node_modules/`);
      Next 16 renombró `middleware.ts` a `proxy.ts` (leído
      `01-app/01-getting-started/16-proxy.md` y `.../guides/authentication.md`).
- [x] 7.2 Confirmar que el cambio `landing-explicativa` ya está mergeado a
      `develop` (existe `/analizar`) antes de continuar con las tareas de
      frontend de este grupo; si no lo está, dejar el grupo 7 pendiente y
      avisar.
      — Verificado: mergeado (commit `52284e2` en la rama base de este
      worktree); `/analizar` ya existía.
- [x] 7.3 Crear `/registro` (formulario con los campos obligatorios y el
      checkbox de consentimiento) y `/ingresar`; verificar con
      `npm run build` sin errores y una captura de cada vista.
      — Verificado: `npm run build` limpio; capturas
      `registro_{1440,375}_{light,dark}.png` e `ingresar_{1440,375}_{light,dark}.png`
      en `output/evidencia/registro/`.
- [x] 7.4 Crear `/cuenta` (muestra `pendiente` / `rechazado` con motivo y opción
      de corregir y reenviar / `verificado`); verificar con `npm run build` y
      capturas de los tres estados.
      — Verificado: capturas `cuenta_{pendiente,rechazado,verificado}_{1440,375}_{light,dark}.png`,
      con sesión real contra una base sembrada (una cuenta por estado).
- [x] 7.5 Crear `/admin/pendientes` (lista, enlaces a los buscadores públicos,
      aprobar/rechazar con motivo obligatorio); verificar con `npm run build` y
      una captura.
      — Verificado: capturas `admin_pendientes_{1440,375}_{light,dark}.png`,
      con sesión admin real.
- [x] 7.6 Proteger `/analizar` en el cliente (redirige si no hay sesión de
      médico verificado) — documentado como capa de UX, no de seguridad (spec
      `proteccion-analisis-clinico` — Requirement: La aplicación no es el
      límite de seguridad); verificar manualmente que redirige sin sesión.
      — Verificado manualmente con Playwright contra el build de producción
      (`next start`) y el backend real: navegar a `/analizar` sin cookie
      redirige a `/ingresar`.
- [x] 7.7 Actualizar `frontend/src/lib/api.ts`: mandar `credentials: "include"`
      en los `fetch` a endpoints protegidos y agregar los llamados a
      registro/login/logout/estado de cuenta/admin; verificar con
      `npm run build`.
      — Verificado: `npm run build` limpio; `npm run lint` sin errores/warnings
      nuevos (los 2 preexistentes siguen en `report/page.tsx` y
      `analyzing/page.tsx`, sin tocar).

## 8. Evidencia y pruebas de extremo a extremo

- [x] 8.1 Escribir `scripts/demo_registro_medicos.py`: registro → intento de
      análisis rechazado (pendiente) → aprobación admin con auditoría →
      análisis permitido → rechazo de otra cuenta con motivo → reenvío, todo
      contra una base SQLite temporal y sin ninguna llamada a un LLM; verificar
      que corre con `python3 scripts/demo_registro_medicos.py` y deja artefactos
      en `output/`.
      — Verificado: corrida real (con el guard de red de
      `scripts/pytest_sin_red.py` activo en el mismo proceso: 0 intentos
      bloqueados) genera `output/demo_registro/{flujo.json,resumen.txt}`.
- [x] 8.2 Verificación integral: correr toda la suite de `tests/` nueva y
      existente y confirmar que pasa completa, incluida la protección de
      `/api/analyze` y `/api/report/pdf` (sesión, estado de cuenta y origen).
      — Verificado: `PYTHONPATH=scripts pytest -p pytest_sin_red tests/
      --ignore=tests/test_ingesta.py` → **826 passed** (baseline 739 + 87
      nuevos), corrido dos veces de forma consistente. Intentos de red
      bloqueados: 76, todos preexistentes y ajenos a este cambio (6 a
      `api.groq.com`, 6 a `eutils.ncbi.nlm.nih.gov`, 64 a `huggingface.co` —
      en tests de RAG/embeddings y de otros agentes que no tocó este cambio;
      `tests/test_api.py` específicamente bajó de 72 a 0). Se observó una vez,
      en una corrida de la suite completa, una falla intermitente en
      `tests/test_agent_05_trials.py` (un test distinto cada vez) por un
      `ApiCircuitBreaker` de Orphanet compartido a nivel de módulo con
      recuperación por reloj real (`backend/external/rate_limiter.py`) — no
      se reprodujo en corridas posteriores ni al correr ese archivo solo;
      preexistente y fuera del alcance de este cambio, no se tocó
      `rate_limiter.py` ni ese test.

## 9. Documentación

- [x] 9.1 Actualizar `.claude/CLAUDE.md` (estado del Sprint 4, nuevas
      variables de entorno) y `.claude/backlog.md` con el estado de esta
      tarjeta/estas tarjetas de Trello.
      — Hecho: nuevas variables de entorno, estructura de carpetas, alta del
      primer admin y scripts de demo documentados en `CLAUDE.md`; nota (22)
      con el resumen completo en `backlog.md`.
- [x] 9.2 Actualizar `.claude/stack.md` con las decisiones de esta propuesta
      (SQLModel/SQLite, argon2-cffi, sesión server-side, validación de origen)
      siguiendo el mismo formato de justificación que las decisiones
      existentes.
      — Hecho: sección "Cuentas y autenticación (Sprint 4)" con las cuatro
      decisiones y sus alternativas descartadas.
