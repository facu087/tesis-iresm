# La landing y la cuenta reconocen la sesión y el rol

Rama: `feature/s4-sesion-en-landing`, sale de `feature/s4-landing-skill-prueba`
(PR #58). Tercer PR de la cadena.

## Objetivo

Que un usuario con sesión iniciada lo vea en la landing, y que un admin llegue a
la revisión de cuentas sin escribir la dirección a mano.

## Problema

- La barra de la landing no consulta la sesión: con sesión iniciada sigue
  mostrando "Ingresar" y "Solicitar acceso", y parece que la sesión se cerró.
  Comprobado el 2026-10-09: la sesión sigue viva al volver a `/cuenta`.
- Ninguna pantalla enlaza a `/admin/pendientes`.
- `/cuenta` no mira el rol: a un admin le muestra "Cuenta verificada" y el botón
  "Analizar un caso", pero el backend exige rol `medico`
  (`backend/auth/deps.py`, `requerir_medico_verificado`) y responde 403.

## Alcance

Solo frontend. No se toca el backend ni `frontend/src/lib/api.ts`.

## Restricciones

- Sin JavaScript la landing se ve como hoy: "Ingresar" y "Solicitar acceso".
- Si el backend no responde, la landing se comporta como sin sesión.
- El nombre del usuario no se guarda en `localStorage` ni en `sessionStorage`.
- Textos de interfaz en el mismo registro que el resto de las pantallas.
- Se respeta `prefers-reduced-motion`.
- La guarda del frontend es una capa de experiencia, no de seguridad.

## Decisiones

- La sesión se consulta una vez por montaje de la landing, en un proveedor de
  contexto cliente; no hay caché de módulo, para no mostrar una sesión vieja
  después de cerrar sesión.
- La consulta tiene un tope de 4 s; vencido, se trata como sin sesión.
- El enlace de cuenta de la barra queda oculto mientras la consulta está en
  curso, solo con JavaScript activo, para que no se vea "Ingresar" y salte al
  nombre. El botón principal del hero no se oculta: cambia al resolver.
- Acción principal según la cuenta:
  - sin sesión: "Solicitar acceso" → `/registro`, con la aclaración de matrícula;
  - médico verificado: "Analizar un caso" → `/analizar`;
  - médico pendiente o rechazado: "Ver mi cuenta" → `/cuenta`;
  - admin: "Cuentas pendientes" → `/admin/pendientes`.
- El ingreso de un admin lleva a `/admin/pendientes`.

## TDD

El frontend no tiene corredor de tests. Se verifica con tipos, lint, build y un
recorrido en navegador sin interfaz contra el backend real en modo grabado.

## Tareas

- [x] **T1 — La landing reconoce la sesión.** Ruta: delegada (más de dos
  archivos no triviales). Proveedor de sesión, barra (escritorio y menú móvil),
  botón principal del hero y del cierre.
- [x] **T2 — El admin llega a la revisión de cuentas.** Ruta: delegada, con T1.
  `/cuenta` según el rol, ingreso del admin, guarda de `/analizar`.
- [x] **T3 — Recorrido en navegador contra el backend real.** Ruta: en línea.

## Criterios de aceptación

- Sin sesión, la landing no cambia respecto de hoy.
- Con sesión de médico verificado: nombre en la barra con enlace a `/cuenta`,
  "Analizar un caso" en la barra, el hero y el cierre, sin la aclaración de
  matrícula.
- Con sesión de admin: "Cuentas pendientes" en la barra, el hero, el cierre y
  `/cuenta`; no se le ofrece analizar.
- Tras cerrar sesión, la landing vuelve a mostrar "Ingresar".

## Entrega

Estrategia: `ask-on-risk`. Pronóstico: menos de 400 líneas. Un solo PR, apilado
sobre el #58.

## Verificación

- `npx tsc --noEmit`, `npm run lint` y `npm run build`: sin errores (reportados
  por el escritor y repetidos por el padre).
- Recorrido en navegador sin interfaz contra el backend real en modo grabado:
  24 de 24. Cubre sin sesión, sin JavaScript, backend caído, backend colgado
  (oculto mientras carga, visible a los 4 s), médica verificada (barra, hero,
  cierre, menú móvil), médico pendiente, admin (ingreso, barra, hero,
  `/cuenta`, `/analizar`) y cierre de sesión.

## Cambios aceptados después de delegar

- Cuando un enlace de cuenta ya lleva al mismo destino que la acción principal
  (admin, médico no verificado), la acción no se repite al lado: la barra no
  muestra el botón y el menú móvil no muestra el botón grande. El escritor lo
  había señalado como duplicado.
- Para un admin, `/cuenta` muestra solo la tarjeta de administrador.

## Revisión nativa

Commit `0e742bc`: riesgo medio, consentida, **aprobada y acusada**
(linaje `review-46232e28d7fc4f3d`). Hallazgos, ninguno bloqueante:

- Corregido: vencido el tope de 4 s la sesión quedaba fija como anónima y una
  respuesta tardía se descartaba. Ahora el tope solo corta la espera y la
  respuesta tardía se aplica. Comprobado con el backend demorado 6 s: "Ingresar"
  a los 4,8 s y el nombre al llegar la respuesta.
- Corregido: con JavaScript habilitado pero sin ejecutarse (un script que no
  carga), "Ingresar" quedaba oculto para siempre. Se agregó un respaldo en CSS
  que lo muestra a los 6 s, también con movimiento reducido. Comprobado
  bloqueando todos los scripts.
- Corregido: la acción "Analizar un caso" exige rol `medico` además de estado
  `verificado`, igual que la guarda de `/analizar`.
- Abierto: no hay pruebas repetibles; el recorrido de navegador no está en el
  repositorio porque el frontend no tiene corredor de tests.

Después de los arreglos: recorrido 24 de 24, tipos, lint y build sin errores.
El commit de los arreglos no pasó por revisión nativa.

## Pendientes

- La sesión se consulta al montar: una página restaurada desde la caché de
  ida y vuelta del navegador después de cerrar sesión puede mostrar la sesión
  vieja hasta recargar.
- Un visitante sin sesión genera un 401 de `/api/cuenta` en la consola en cada
  visita a la landing.
- El nombre se muestra entero ("Juan Carlos"), recortado por ancho.
- El admin sigue sin listado de cuentas aprobadas, historial de decisiones ni
  baja de cuentas: no hay pantalla para eso.

## Progreso

- 2026-10-09: rama y documento creados.
- 2026-10-09: T1, T2 y T3 hechas en un commit.
