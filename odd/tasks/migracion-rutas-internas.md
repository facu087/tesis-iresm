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
  `frontend/src/lib/pipelineSteps.ts` (9 pasos, la que usan la landing y
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

- [ ] **T1 — `/admin/pendientes` en el sistema nuevo.** Ruta: delegada (lectura
  que prepara la escritura; puede tocar el marco compartido).
- [ ] **T2 — `/analyzing` en el sistema nuevo, con los pasos de
  `pipelineSteps.ts`.** Ruta: delegada.
- [ ] **T3 — `/report` en el sistema nuevo.** Ruta: delegada (archivo de 1.112
  líneas).
- [ ] **T4 — Retirar lo que quedó sin uso y actualizar la documentación.**
  Ruta: delegada. `ThemeScope`, fuentes y tokens anteriores, y la sección
  "Identidad visual del frontend" de `.claude/CLAUDE.md`.
- [ ] **T5 — Recorrido completo en navegador.** Ruta: en línea. Flujo de punta
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
los #57 a #59 del mismo día. Límites de cada PR: se registran acá al cerrar
cada tarea.

## Verificación

Pendiente.

## Progreso

- 2026-10-09: rama y documento creados.
