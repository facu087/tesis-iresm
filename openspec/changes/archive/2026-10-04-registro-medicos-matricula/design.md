## Context

Hoy no existe ninguna capa de cuentas, sesión ni persistencia relacional en NEXUS:
`backend/main.py` monta un único router (`backend/api/router.py`) con dos
endpoints públicos (`POST /api/analyze`, `POST /api/report/pdf`) y `GET /health`.
No hay usuarios, no hay base de datos, y `frontend/src/lib/api.ts` llama al
backend con `fetch` sin `credentials: "include"`. `.env.example` ya declara
`SECRET_KEY` y `SESSION_TTL_MINUTES` sin ningún consumidor — quedaron anticipadas
para esto.

El proyecto tiene tres restricciones que enmarcan todo lo que sigue (`.claude/CLAUDE.md`,
`.claude/stack.md`):
- Tipado estático y Pydantic para todo modelo de datos.
- Nunca persistir datos clínicos más allá de la sesión de análisis — esta cuenta
  nueva es de **médicos**, no de pacientes, y debe mantenerse así.
- API keys y secretos solo desde `.env`.

Ver `proposal.md` — Why para la justificación de por qué la verificación es
semi-automática y no contra un padrón oficial.

## Goals / Non-Goals

**Goals:**
- Cerrar `POST /api/analyze` (y `POST /api/report/pdf`) detrás de una sesión de
  médico verificado, controlado en el backend.
- Dar de alta médicos con un flujo de revisión humana auditable, sin agregar
  dependencias pesadas (sin navegador headless, sin credenciales de una API que
  hoy no está disponible para el proyecto).
- Dejar la puerta abierta a una verificación automática futura sin comprometerse a
  construirla ahora.

**Non-Goals:**
- Verificación automática contra SISA/REFEPS, Orphanet-de-profesionales o
  cualquier padrón oficial. Queda como trabajo futuro (ver Decisión D6).
- Carga de un archivo/credencial de la matrícula como evidencia adicional. El
  formulario de registro define en `proposal.md` no incluye ese campo; el único
  dato del lado del médico es el que declara al registrarse.
- Verificación de la propiedad del email institucional por correo (activation
  link vía SMTP). **Diferido a un cambio posterior (decisión del usuario,
  2026-09-25)**: no se implementa el envío en este cambio, pero el modelo de
  cuenta (`CuentaMedico`, D1) SHALL dejar lugar para agregarlo después sin
  romper el esquema — un campo `email_verificado: bool` (default `False`, sin
  ningún flujo que lo ponga en `True` todavía) alcanza para eso.
- Multi-tenancy, recuperación de contraseña por email, 2FA. Ninguno lo pidió la
  propuesta; agregarlos ahora sería inventar alcance.
- Cualquier cambio al pipeline de análisis en sí (agentes, RAG, arbitraje,
  navegación de ensayos).

## Decisions

### D1 — Persistencia: SQLite vía SQLModel, `create_all()` en el arranque
**Elegido:** SQLModel (Pydantic + SQLAlchemy 2.0) sobre un archivo SQLite cuya ruta
viene de `.env` (`NEXUS_DB_PATH`, default `./data/nexus.db`, `.gitignore`d como
`chroma_db/`). El esquema se crea con `SQLModel.metadata.create_all()` al levantar
la app — sin Alembic todavía.

**Por qué:** el proyecto ya es Pydantic-first (`Pydantic para todos los modelos de
datos`, `.claude/CLAUDE.md`); SQLModel define la tabla y el modelo de validación
en una sola clase, en vez de mantener un modelo ORM y un esquema Pydantic
duplicados a mano. SQLite no necesita un servidor aparte, lo que encaja con el
deploy de prototipo en Railway.app (`.claude/stack.md`) y con que esta es una
tesis, no un sistema con carga concurrente real. El esquema de esta primera
versión es chico (cuentas, sesiones, auditoría) y no va a iterar varias veces
antes del cierre de la tesis, así que una migration tool agrega complejidad sin
beneficio inmediato — si el esquema crece después, Alembic es el camino
recomendado y no exige reescribir los modelos.

**Alternativas consideradas:**
- *SQLAlchemy 2.0 ORM puro*: más maduro y sin la capa extra de SQLModel, pero
  duplica la definición de cada entidad (modelo ORM + schema Pydantic para la
  API), lo que va contra la convención Pydantic-first del proyecto y multiplica
  el lugar donde un campo puede quedar desincronizado.
- *Un archivo JSON / TinyDB*: se descartó — sin garantías transaccionales reales,
  con el riesgo concreto de que una escritura del admin (aprobar/rechazar) y un
  registro nuevo lleguen al mismo tiempo y se pisen. Una cuenta de médico y una
  decisión de auditoría son justo el tipo de dato que necesita atomicidad.

### D2 — Hash de contraseña: `argon2-cffi` directo
**Elegido:** `argon2-cffi`, invocado directo (sin `passlib` de por medio).

**Por qué:** Argon2id es la recomendación vigente de OWASP para hash de
contraseñas por sobre bcrypt/PBKDF2. `argon2-cffi` es el binding de referencia,
mantenido, sin capas intermedias. Se evita `passlib`: su desarrollo está
efectivamente discontinuado y sumar una dependencia sin mantenimiento activo para
algo tan sensible como el hash de contraseñas no se justifica cuando la librería
de base ya expone una API simple (`PasswordHasher().hash()` / `.verify()`).

**Alternativas consideradas:**
- *bcrypt*: bien establecido, pero más débil que Argon2id frente a ataques con
  GPU/ASIC a igual costo configurado.
- *pwdlib*: envoltorio moderno sobre argon2-cffi/bcrypt; se descartó por ahora
  para no sumar una dependencia extra cuando `argon2-cffi` solo ya cubre lo que
  este cambio necesita.

### D3 — Sesión: registro server-side en SQLite + cookie httpOnly, no JWT
**Elegido:** al hacer login, se crea una fila en una tabla `sesiones` (id opaco
aleatorio, cuenta, expiración = `SESSION_TTL_MINUTES` desde `.env`) y se entrega
al navegador en una cookie `httpOnly`, `SameSite=Lax`, `Secure` cuando
`ENVIRONMENT=production`. Cerrar sesión borra esa fila. `SECRET_KEY` (ya
declarada en `.env.example`) firma el valor de la cookie para que no sea un ID
adivinable ni manipulable, pero la fuente de verdad de si la sesión es válida es
la tabla, no la firma.

**Por qué:** con SQLite ya elegido para D1, una tabla de sesiones es gratis y da
algo que un JWT stateless no da sin trabajo extra: revocación inmediata (logout,
o un admin forzando el cierre de sesión de una cuenta) sin mantener una
denylist aparte. Para el tamaño de este proyecto, la sesión server-side es más
simple de razonar y de auditar que un token autocontenido.

**CSRF — corregido.** Una versión anterior de esta decisión asumía que
`POST /api/analyze` viaja como JSON y que eso obliga a un preflight CORS que
frenaría a un sitio malicioso. Es falso: `backend/api/router.py:119-122` recibe
`file: UploadFile = File(...)` y `text: str = Form(...)`, y
`frontend/src/lib/api.ts:25,48` arma el pedido con `FormData` —
`multipart/form-data` es una solicitud "simple" para CORS, **no dispara
preflight**, y un `<form>` HTML común hospedado en cualquier sitio puede
enviarla directo contra el backend. CORS nunca protegió este endpoint.

Tampoco alcanza con apoyarse en que "son orígenes distintos": `SameSite` opera
por **sitio** (dominio registrable), no por origen — el puerto no cuenta.
`localhost:3000` y `localhost:8000` son el mismo sitio en desarrollo, y en
producción el frontend y el backend también lo serían si comparten dominio
registrable (p. ej. `app.nexus.com` / `api.nexus.com`). Razonar sobre "orígenes
distintos" fue el error de fondo; `SameSite=Lax` por sí solo no es una defensa
suficiente para el endpoint más importante del sistema.

**Elegido:** todo endpoint que cambia estado (`POST /api/analyze`,
`POST /api/report/pdf`, `POST /api/login`, `POST /api/logout`,
`POST /api/registro`, aprobar/rechazar de `revision-admin-matriculas`) valida el
encabezado `Origin` de la solicitud (con `Referer` como respaldo si `Origin` no
está presente) contra la misma lista blanca de orígenes que ya usa CORS
(`ALLOWED_ORIGINS` en `.env`), y responde 403 si falta o no coincide — sin
importar el tipo de contenido, así que cubre `multipart/form-data` igual que
JSON. Es una validación barata (una comparación de string contra una lista) y no
depende de que el navegador decida no disparar preflight. `SameSite=Lax` +
`httpOnly` se mantienen como defensa en profundidad — siguen acotando el robo o
reenvío pasivo de la cookie entre sitios genuinamente distintos —, y un token
CSRF de doble envío queda documentado como endurecimiento opcional si el sistema
sale del contexto de tesis; no es necesario para este alcance porque la
validación de `Origin`/`Referer` ya cubre el vector real (formulario/solicitud
disparada desde un sitio ajeno con la cookie de sesión puesta por el navegador).

**Alternativas consideradas:**
- *JWT / cookie firmada stateless (`itsdangerous`)*: evita la tabla de sesiones,
  pero revocar una sesión (logout, o que un admin corte el acceso de una cuenta)
  exige una denylist igual — es la misma complejidad con un paso extra.

### D4 — Autorización: dependencias de FastAPI por rol y por estado de cuenta
**Elegido:** dependencias de FastAPI (`Depends(...)`) que resuelven la sesión
desde la cookie y exponen la cuenta autenticada; una dependencia adicional exige
rol `admin` para las rutas de revisión, y otra exige rol `medico` + estado
`verificado` para `POST /api/analyze` y `POST /api/report/pdf`. Se aplican por
endpoint, no por middleware global, porque el registro y el login deben quedar
alcanzables sin sesión.

**Por qué:** es el patrón nativo de FastAPI para autorización condicional por
ruta, y mantiene cada endpoint explícito sobre qué exige, en vez de una lista de
exclusiones sobre un middleware global.

### D5 — `POST /api/report/pdf` también queda protegido
Inspeccionado `backend/api/router.py:209-230`: `export_pdf` no llama a ningún
agente ni al LLM — solo recibe un `StructuredReport` ya armado y lo formatea a
PDF con `generate_pdf()`. Estrictamente, no "ejecuta análisis" en el sentido de
correr el pipeline.

**Elegido igual:** aplicar la misma exigencia de sesión de médico verificado que
a `/api/analyze`, en vez de dejarlo público.

**Por qué:** el endpoint acepta como cuerpo un `StructuredReport` completo
—incluye la narrativa clínica del caso— sin ningún chequeo de que quien lo manda
es dueño de ese reporte. Dejarlo público permitiría que cualquiera con acceso de
red genere un PDF con membrete de NEXUS a partir de cualquier `StructuredReport`
que arme o intercepte, sin necesitar cuenta. Mantener dos criterios de acceso
distintos entre los dos únicos endpoints de negocio de la API agrega superficie
de error sin ningún beneficio a cambio; el costo de proteger también este
endpoint es una línea de `Depends(...)`.

### D6 — Punto de extensión para verificación automática futura
**Elegido:** una interfaz angosta, algo como
`LicenseVerificationProvider.check(matricula, jurisdiccion) -> LicenseCheckResult | None`,
sin ninguna implementación concreta en este cambio — la revisión del admin es el
único "provider" activo. El flujo de aprobación (D4, y el capability
`revision-admin-matriculas`) no depende de que exista un provider automático: solo
consulta uno si está configurado, y si no, se comporta exactamente como el resto
de este diseño.

**Por qué:** `proposal.md` — Why documenta que SISA/REFEPS `WS020` es el único
servicio con matrícula/profesión/jurisdicción por código, pero exige el
Formulario A1 y aprobación discrecional orientada al sistema público — no hay
ninguna garantía de que esa aprobación llegue dentro del plazo de la tesis. Dejar
el puerto declarado (sin implementarlo) evita que ese futuro provider obligue a
rediseñar el flujo de aprobación; no implementarlo ahora evita construir contra
una API a la que hoy no hay acceso garantizado.

## Risks / Trade-offs

**[Riesgo de seguridad — hallazgo central, documentado como limitación de la
tesis]** Consultar el padrón público (REFEPS o el de una jurisdicción provincial)
solo prueba que "existe una matrícula con ese número, a nombre de esa persona" —
el buscador público expone nombre, DNI y matrícula de cualquier profesional
habilitado, así que **cualquiera puede registrarse en NEXUS declarando los datos
reales de un médico existente**, y ese chequeo por sí solo no lo detecta. Este
diseño no resuelve ese problema de raíz — lo delega al criterio del
administrador humano, con dos señales, ninguna concluyente por sí sola: (a) que
el email de registro sea de un dominio institucional plausible para esa
jurisdicción/institución, y (b) que los datos declarados coincidan con lo que
devuelve el buscador público para esa matrícula. → **Mitigación parcial, no
solución**: la auditoría (D del capability `revision-admin-matriculas`) deja
registro de qué fuente dijo haber consultado el admin, así que un error de
aprobación es rastreable después de los hechos, aunque no se prevenga antes. La
tesis debe documentar esta limitación explícitamente, no presentarla como
verificación de identidad resuelta.

**[Riesgo] Un solo administrador humano es un cuello de botella y un punto único
de fallo para el acceso de todos los médicos.** → Mitigación: el bootstrap CLI
(D del capability `revision-admin-matriculas`) permite dar de alta más de una
cuenta admin ejecutándolo más de una vez o (una vez que exista un admin) que un
admin cree a otro por la misma pantalla de administración — este diseño no
restringe la cantidad de admins, solo cómo nace el primero.

**[Riesgo] SQLite con escrituras concurrentes (un admin aprobando mientras otro
médico se registra) puede bloquear brevemente.** → Para el volumen esperado de un
prototipo de tesis (decenas de cuentas, no miles concurrentes) el modo WAL de
SQLite alcanza; si el proyecto escala en cantidad de escrituras simultáneas,
migrar a Postgres es el camino y SQLModel no ata el código a SQLite.

**[Riesgo] La validación de `Origin`/`Referer` (D3) depende de que el navegador
mande alguno de los dos encabezados; un cliente que no sea un navegador (un
script hecho a medida) podría omitirlos.** → Por eso el rechazo es *fail-closed*:
falta el encabezado → 403, igual que si no coincidiera. Un cliente legítimo
(el frontend de NEXUS) siempre manda `Origin` en una solicitud de este tipo. Un
token CSRF de doble envío queda documentado como endurecimiento opcional si el
sistema sale del contexto de esta tesis; no es necesario para este alcance
porque ya cubre el vector real (ver D3).

**[Riesgo operativo] Next.js 16 (`frontend/package.json` fija `"next": "16.2.7"`)
cambió cómo se maneja middleware/route protection entre versiones mayores, y
`frontend/node_modules/` no está presente en este worktree para confirmar la API
vigente.** → No se resuelve en esta propuesta: `tasks.md` debe incluir leer
`frontend/node_modules/next/dist/docs/` (una vez que `node_modules` exista, tras
`npm install` en la fase de `apply`) antes de escribir el middleware o los
guards de `/registro`, `/ingresar`, `/cuenta`, `/admin/pendientes` y la
protección de `/analizar`.

## Migration Plan

- Sin datos existentes que migrar: la base de cuentas es enteramente nueva y no
  toca ningún modelo del pipeline (`ClinicalCase`, `Report`, `StructuredReport`,
  etc.).
- Orden de despliegue: (1) aplicar este cambio agrega el esquema nuevo y lo crea
  automáticamente al arrancar el backend (`create_all()`); (2) inmediatamente
  después del primer deploy, correr el comando de bootstrap para dar de alta el
  primer admin; (3) recién entonces `POST /api/analyze` empieza a exigir sesión
  — antes de eso, aplicar el cambio completo en un entorno sin ningún admin
  dejaría el pipeline inalcanzable para todos.
- **Dependencia de secuencia con `landing-explicativa`** (todavía sin mergear):
  ese cambio mueve la carga de casos de `/` a `/analizar` y deja un lugar en la
  navegación para "Ingresar". Esta propuesta no depende de él para existir, pero
  su fase de `apply` sí — las rutas y el guard de `/analizar` asumen que esa
  ruta ya existe. `apply` de este cambio debe esperar a que `landing-explicativa`
  esté mergeado a `develop`.
- Rollback: revertir el merge de la rama de este cambio. El archivo SQLite nuevo
  es aislado (no hay tablas existentes que haya alterado), así que no hay un paso
  de rollback de esquema más allá de descartar ese archivo.
