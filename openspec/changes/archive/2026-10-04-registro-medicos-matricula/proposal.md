## Why

Hoy `POST /api/analyze` no pide ninguna credencial: cualquiera que llegue al backend
puede correr el pipeline completo con datos clínicos reales. Para un sistema de
soporte investigativo clínico eso es inaceptable aunque sea un prototipo de tesis —
el pipeline debe quedar reservado a médicos habilitados.

La verificación automática contra un padrón oficial no es viable ahora: el único
servicio con matrícula, profesión y jurisdicción por código (SISA/REFEPS `WS020`)
exige el Formulario A1 y aprobación discrecional de la Dirección Nacional de
Gobernanza e Integración de los Sistemas de Salud, está orientado al sistema
público, y no hay ninguna garantía de aprobación en el plazo de la tesis. Scrapear
los buscadores públicos (Buscador Nacional REFEPS, autogestión del Consejo de
Médicos de Córdoba) se evaluó y se descartó: es frágil (la URL provincial
`/validar-matricula` ya no existe), no hay ToS que autorice automatizarlo, agrega
una dependencia pesada (navegador headless) y, sobre todo, **no resuelve el problema
real**: el buscador público expone nombre, DNI y matrícula de cualquier
profesional, así que "la matrícula existe" nunca prueba "quien se registra es esa
persona".

Por eso la verificación queda **semi-automática**: el médico se registra, la cuenta
nace `pendiente`, y un administrador de la aplicación la revisa a mano con enlaces
directos a los buscadores públicos antes de aprobarla o rechazarla con motivo. Esto
cierra el acceso al pipeline ya, deja auditoría de cada decisión, y no cierra la
puerta a automatizar la consulta a SISA/REFEPS el día que la aprobación esté
disponible.

## What Changes

- **Registro de médicos**: formulario con nombre, apellido, DNI, matrícula,
  jurisdicción, profesión/especialidad (opcional), email institucional, contraseña
  y consentimiento explícito (Ley 25.326) para el tratamiento de esos datos. La
  cuenta nace en estado `pendiente`.
- **Ciclo de vida de la cuenta**: `pendiente` → el admin aprueba (`verificado`) o
  rechaza **con motivo obligatorio**; el médico rechazado ve el motivo, puede
  corregir sus datos y reenviar la solicitud. Solo `verificado` puede usar el
  pipeline.
- **Revisión admin en la aplicación**: pantalla de cuentas pendientes con enlaces
  directos al Buscador Nacional REFEPS y al buscador provincial que corresponda
  (configurable — el del Consejo de Médicos de Córdoba está roto hoy). El admin
  decide a mano; el sistema no consulta ningún padrón por su cuenta en este cambio.
- **Auditoría**: cada aprobación o rechazo queda registrado — quién, cuándo, qué
  decidió, el motivo y qué fuente dice haber consultado. Sin excepciones.
- **Autenticación**: login con contraseña, sesión de servidor, roles `medico` /
  `admin`, límite de intentos de login y mensajes de error genéricos (sin filtrar
  si el email existe).
- **Alta del primer admin**: comando CLI de una sola vez (`python -m backend.cli
  crear-admin`), nunca un usuario o contraseña hardcodeados.
- **BREAKING**: `POST /api/analyze` deja de ser público. Exige una sesión
  autenticada de un médico en estado `verificado`, controlado en el backend (no
  alcanza con ocultar el botón en el frontend). Si `POST /api/report/pdf` expone
  capacidad de análisis (no solo re-renderiza un `StructuredReport` ya generado),
  aplica la misma exigencia.
- **Punto de extensión, sin implementarlo**: la verificación queda detrás de una
  interfaz angosta para que, el día que SISA/REFEPS apruebe el Formulario A1, un
  chequeo automático se pueda enchufar sin rediseñar el flujo de aprobación.

## Capabilities

### New Capabilities
- `registro-medicos`: alta de médicos — campos requeridos, consentimiento Ley
  25.326, estados de la cuenta (`pendiente` / `rechazado` con motivo /
  `verificado`), y el reenvío tras un rechazo.
- `autenticacion-medicos`: login, sesión, roles `medico`/`admin`, límite de
  intentos y no filtrado de existencia de usuario (no user enumeration).
- `revision-admin-matriculas`: pantalla de pendientes, aprobación/rechazo con
  motivo obligatorio, enlaces a los buscadores públicos, auditoría de cada
  decisión, y el alta del primer admin por CLI.
- `proteccion-analisis-clinico`: exigencia de sesión autenticada y médico
  `verificado` para `POST /api/analyze` (y `POST /api/report/pdf` si corresponde),
  controlada en el backend.

### Modified Capabilities
<!-- Ninguna. `clasificacion-evidencia-ebm` es la única spec vigente y no cambia:
     este trabajo es previo al pipeline, no altera cómo se clasifican hipótesis. -->

## Impact

- **Backend nuevo**: capa de persistencia (usuarios, estado de cuenta, auditoría —
  a definir en `design.md`), módulo de autenticación (hash de contraseña, sesión),
  dependencias FastAPI de autorización por rol, endpoints de registro/login/estado
  de cuenta/revisión admin, comando CLI de bootstrap.
- **`backend/api/router.py` y `backend/main.py`**: `POST /api/analyze` y
  potencialmente `POST /api/report/pdf` pasan a requerir la dependencia de
  autorización; se registran los routers nuevos.
- **`backend/requirements.txt`**: dependencias nuevas para persistencia, hash de
  contraseña y manejo de sesión (a decidir y justificar en `design.md`).
- **`.env` / `.env.example`**: nuevas variables (ruta de la base de datos, enlace
  configurable del buscador provincial); `SECRET_KEY` y `SESSION_TTL_MINUTES` ya
  están declaradas en `.env.example` sin uso — este cambio las activa.
- **Frontend**: rutas nuevas `/registro`, `/ingresar`, `/cuenta`,
  `/admin/pendientes`; `frontend/src/lib/api.ts` pasa a mandar credenciales en los
  `fetch` protegidos. Depende de que el cambio `landing-explicativa` (aún sin
  mergear, mueve la carga de casos de `/` a `/analizar`) esté mergeado antes de
  aplicar este cambio — no lo reemplaza ni lo bloquea, pero el `apply` de este
  cambio asume que `/analizar` ya existe.
- **Tests y evidencia**: `tests/` nuevos para registro, login, autorización por
  rol, auditoría, CLI de bootstrap y no enumeración de usuarios;
  `scripts/demo_registro_medicos.py` mostrando el flujo completo contra una base
  temporal, sin llamadas a ningún LLM.
- **No afecta** el pipeline de análisis en sí (agentes, RAG, verificación,
  arbitraje, navegación de ensayos): este cambio es una puerta de acceso previa.
