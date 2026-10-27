# Las rutas internas pasan al sistema visual de la landing

Rama: `feature/s4-migracion-rutas-internas`, sale de `develop` (`51b7c1e`).

## Objetivo

Que `/admin/pendientes`, `/analyzing` y `/report` se vean como el resto del
producto: el sistema visual de la landing (`.landing`), con tema claro y oscuro.

## Problema

Auditoría del 2026-10-09 (claro y oscuro, 1440 px):

- `/admin/pendientes` usa la identidad anterior: títulos en Newsreader, cuerpo
  en Atkinson, barra recta, botones de 8 px. Tiene logo, selector de tema y
  modo oscuro.
- `/analyzing` no tiene la barra compartida, ni logo, ni selector de tema; usa
  emojis como iconos, queda siempre en claro y no muestra el aviso "NEXUS no
  emite diagnósticos". Además lleva su propia lista de 8 pasos, distinta de
  `frontend/src/lib/pipelineSteps.ts` (8 pasos, la que usan la landing y
  `/analizar`): le falta la navegación de ensayos y le atribuye el reporte al
  Agente 05 en vez del Sintetizador (06).
- `/report` no tiene la barra compartida, ni logo, ni selector de tema; usa
  emojis y símbolos como marcadores y queda siempre en claro.

## Alcance

Solo frontend, solo presentación. No se toca el backend, ni
`frontend/src/lib/api.ts`, ni los tipos del reporte, ni lo que cada pantalla
pide, guarda o redirige.

## Restricciones

- El aviso "NEXUS no emite diagnósticos" queda visible en las tres pantallas.
- En `/report` se conservan, con la misma visibilidad que hoy, la advertencia
  del consenso de IA, la marca de modo grabado, el estado de verificación de
  hipótesis y fuentes, las cinco pestañas y la exportación a PDF.
- Nada de datos, cifras ni textos inventados: el contenido es el que hay.
- Iconos Phosphor (`@phosphor-icons/react`), sin emojis.
- Geist como única tipografía; Geist Mono solo para datos (PMID, NCT).
- Toda regla de estilo nueva va dentro de `.landing` en `globals.css`.
- Se respeta `prefers-reduced-motion`.
- Textos de interfaz en español, en el registro de las pantallas ya migradas.
- Los datos clínicos no se loggean ni se guardan fuera de la sesión.

## Decisiones

- Las tres pantallas usan el mismo marco que las ya migradas: píldora flotante
  con el logo a `/`, una acción y el selector de tema. Si el marco de dos
  columnas de `AuthShell` no sirve (el reporte necesita ancho completo), la
  píldora se extrae a una pieza compartida en vez de copiarla.
- `/analyzing` toma los pasos de `lib/pipelineSteps.ts`; no queda una segunda
  lista.
- Al tener modo oscuro, `/analyzing` y `/report` salen de `ThemeScope`. Cuando
  ya no quede ninguna ruta de colores fijos, `ThemeScope` se elimina.
- Lo que la migración deje sin uso (fuentes Newsreader y Atkinson, tokens
  globales de la identidad anterior, componentes huérfanos) se retira en una
  tarea aparte, al final, solo si se comprueba que nadie más lo usa.

## TDD

El frontend no tiene corredor de tests: no hay RED ejecutable. Cada tarea se
verifica con tipos, lint, build y un recorrido en navegador sin interfaz contra
el backend real en modo grabado, en claro y oscuro, a 1440 px y 375 px.

## Tareas

- [x] **T1 — `/admin/pendientes` en el sistema nuevo.** Ruta: delegada (lectura
  que prepara la escritura; puede tocar el marco compartido). Commit `716f52b`.
  El marco se extrajo a `ShellFrame` y el aviso a `DiagnosticNotice`.
- [x] **T2 — `/analyzing` en el sistema nuevo, con los pasos de
  `pipelineSteps.ts`.** Ruta: delegada. Commit `79f1874`.
- [x] **T3 — `/report` en el sistema nuevo.** Ruta: delegada (archivo de 1.112
  líneas). Commit `6daf123`; arreglo posterior a la revisión en `ac19ea2`.
- [x] **T4 — Retirar lo que quedó sin uso y actualizar la documentación.**
  Ruta: delegada. `ThemeScope`, fuentes y tokens anteriores, y la sección
  "Identidad visual del frontend" de `.claude/CLAUDE.md`. Commits `edc4ee3`
  y `dc2dd48`.
- [x] **T5 — Recorrido completo en navegador.** Ruta: en línea. Flujo de punta
  a punta y recorrido de sesión y rol, más capturas de las tres pantallas.

## Criterios de aceptación

- Las tres pantallas muestran la píldora flotante con logo y selector de tema,
  títulos en Geist y botones en píldora, en claro y en oscuro.
- Ningún emoji en las tres pantallas.
- `/analyzing` muestra los mismos pasos que `/analizar` y la landing.
- El flujo completo (registro, revisión, análisis, reporte, PDF) sigue pasando.
- Sin desbordes horizontales a 375 px.

## Entrega

Estrategia: `ask-on-risk`. Pronóstico: más de 400 líneas (las tres páginas
suman unas 1.600). Cadena: PRs apilados hacia `develop`, uno por pantalla, como
los #57 a #59 del mismo día. Límites de cada PR:

- #61 `feature/s4-migracion-admin-pendientes`: `51b7c1e..35692e3` (T1).
- #62 `feature/s4-migracion-analyzing`: `35692e3..0732291` (T2).
- #63 `feature/s4-migracion-rutas-internas`: `0732291..` (T3, T4 y cierre).

## Verificación

- T1: `npx tsc --noEmit`, `npm run lint` y `npm run build` sin errores
  (reportados por el escritor). Recorrido en navegador sin interfaz contra el
  backend real en modo grabado: 18 de 18, a 1440 px y 375 px, en claro y
  oscuro (marco, Geist, botones en píldora, sin desborde, aviso, sin emojis,
  rechazo sin motivo no avanza, sin errores de consola). No se ejercitó la
  aprobación ni el rechazo efectivos: quedan para el recorrido de T5.
- T2: tipos, lint y build sin errores (reportados por el escritor). Recorrido
  en navegador: 20 de 20 (1440 px claro hasta abrir el reporte, 375 px oscuro
  con movimiento reducido, error de red, visita directa sin caso). Un envío
  manda un solo `POST /api/analyze` en desarrollo (medido).
- T3: tipos, lint y build sin errores (reportados por el escritor). Recorrido
  en navegador: 22 de 22 (1440 px claro y 375 px oscuro): marco, cinco
  pestañas con contenido y sin desborde, marca de modo grabado, advertencia
  del consenso, aviso, sin emojis, flechas del teclado, pestañas fijas al
  bajar y descarga del PDF.
- T4: tipos, lint y build sin errores (reportados por el escritor; tipos
  repetidos por el padre).
- T5, con base y caché de desarrollo nuevas: flujo completo 20 de 20
  (registro, rechazo con motivo, reenvío, aprobación, análisis, reporte, PDF,
  cierre de sesión) y recorrido de sesión y rol 24 de 24.

## Revisión nativa

- T1 (`51b7c1e..35692e3`): riesgo medio, consentida, **aprobada y acusada**
  (linaje `review-6fdb589d9a38713c`). Tres avisos informativos, ninguno
  bloqueante: la verificación figuraba pendiente en este documento (ya
  registrada arriba); el error de decisión pasa por `FormError` (comprobado:
  conserva `role="alert"` y el `id`); la clase `landing-skeleton` (comprobado:
  existe en `globals.css`).
- T2 (`35692e3..0732291`): riesgo medio, consentida, **aprobada y acusada**
  (linaje `review-f87e092a1b97285e`). Sin bloqueantes. Avisos: no hay prueba
  automática de la máquina de estados del cierre (sin corredor de tests); el
  mapa de iconos y tiempos por id cae en silencio a un valor por defecto si la
  lista compartida cambia; la cancelación comparte una sola referencia entre
  ejecuciones del efecto (ya estaba en la base).
- T3 (`0732291..4dbe5b3`): riesgo medio, consentida, **aprobada y acusada**
  (linaje `review-bc3a3e527f5d18bd`). Sin bloqueantes. Corregido en `ac19ea2`:
  un ensayo con un valor de compatibilidad fuera de los cuatro conocidos
  rompía toda la vista (la tabla de insignias no tenía valor por defecto).
  Abierto: el manejo de teclado de las pestañas no tiene prueba automática.

## Cambios aceptados después de delegar

- `/analyzing`: el último paso queda "en curso" hasta que responde el backend.
  Antes la lista mostraba 100 % y "Completado" con el análisis todavía
  corriendo.
- `/analyzing`: se agregó la aclaración de que el avance es orientativo, porque
  el backend responde una sola vez con el reporte terminado y no manda eventos.
- `/analyzing`: el botón del error pasó de "Volver al inicio" a "Volver a
  cargar el caso"; el destino (`/analizar`) no cambió.
- `/report`: las pestañas son una lista de pestañas accesible (flechas,
  Inicio, Fin); "Nuevo análisis" es un enlace en la píldora; el botón del PDF
  dejó de estar en una barra fija y queda junto al título; los colores de
  estado siguen la landing (especulativa en borde punteado, prioridad en
  ocre).
- La lista compartida tiene 8 pasos, no 9 como decía la auditoría.

## Pendientes

- El error de red de `/analyzing` muestra el mensaje crudo del navegador
  ("Failed to fetch"). Ya era así antes de la migración.
- La visita directa a `/analyzing` sin caso redirige a `/` y no a `/analizar`.
- En `/report`, la etiqueta "En PubMed este PMID es:" sale en rojo también en
  las fuentes verificadas. Ya era así antes de la migración.
- `body` en `layout.tsx` conserva `bg-gray-50 text-gray-900`, que la regla
  global de `body` pisa: está muerto y no se ve.
- Los recorridos de navegador siguen fuera del repositorio.

## Progreso

- 2026-10-09: rama y documento creados.
- 2026-10-09: T1 y T2 hechas, revisadas y acusadas. T3 delegada.
- 2026-10-09: T3, T4 y T5 hechas. PRs #61, #62 y #63 abiertos, sin mergear.
