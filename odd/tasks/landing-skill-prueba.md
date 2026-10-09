# Prueba de la skill `landing-page-design` sobre la landing, con imágenes de Higgsfield

Rama: `feature/s4-landing-skill-prueba` (base `develop`, `6721eb2`).

## Objetivo

Rehacer la landing (`/`) dándole libertad a la skill externa
`elayadesign/ai-design-skills` → `landing-page-design` (partes A y B), e
incorporar ilustraciones generadas con Higgsfield acordes al proyecto. Es una
prueba en rama: se descarta si no convence.

## Problema

La auditoría de solo lectura del 2026-10-09 encontró en la landing actual:
Agente 06 marcado "En desarrollo" cuando ya corre, sin navegación en móvil, sin
camino a `/registro`, hero sin imagen, sin 404 propio, sin enlace para saltar al
contenido y sin metadatos para compartir.

## Alcance

Solo la ruta `/` y sus componentes, más `not-found.tsx` y los metadatos.
Fuera de alcance: `/analizar`, `/analyzing`, `/report`, `/registro`,
`/ingresar`, `/cuenta`, `/admin`; `lib/pipelineSteps.ts` (lo comparte
`/analizar`); página de política de privacidad (no hay texto legal y no se
inventa); el plugin `scroll-world` (ver Decisiones).

## Restricciones

- La veracidad manda sobre la skill: sin testimonios, logos, clientes, cifras ni
  garantías inventadas. Toda afirmación nueva tiene que salir del texto actual
  de la landing o ser verificable en el código.
- El aviso "NEXUS no emite diagnósticos" se conserva y sigue visible.
- Las ilustraciones generadas van rotuladas como ilustración; nunca se
  presentan como captura del sistema.
- El sistema visual nuevo queda acotado a la landing: las demás pantallas que
  usan los tokens no cambian.
- Se respeta `prefers-reduced-motion` aunque la skill pida animar siempre.
- Next.js 16: leer `frontend/node_modules/next/dist/docs/` antes de escribir.

## Decisiones

- **Tipografía**: una sola, Geist (ya está en el proyecto), más Geist Mono para
  datos. Reemplaza a Newsreader + Atkinson solo en la landing.
- **Color**: se conservan el azul marino y el ocre como colores de marca; los
  fondos del tema oscuro pasan a la lista de la skill.
- **Acción principal**: "Solicitar acceso" → `/registro` (hoy el CTA lleva a
  `/analizar`, que exige sesión). Supuesto del orquestador, a confirmar.
- **Imágenes**: Seedream 5.0 Flash. GPT Image 2.5, GPT Image 2 y Recraft
  rechazan el plan free (`job_minimum_basic_plan_required`). Cuatro
  generaciones, 2 créditos; quedan 8 de 10.
- **`scroll-world`**: no se ejecuta. Necesita una cadena de clips de video
  (2N−1 clips); el más barato en Higgsfield cuesta 7,5 créditos por clip y el
  saldo es de 8; por Monid, unos USD 27 para seis escenas.

## TDD

Excepción: el frontend no tiene corredor de tests (`package.json` solo define
`dev`, `build`, `start`, `lint`). Comprobaciones: `npm run lint`,
`npx tsc --noEmit`, `npm run build`.

## Tareas

- [x] **T0 — Ilustraciones** · ruta: en línea.
  - `frontend/public/landing/{hero,verificacion,debate}.webp` y `og.jpg`
    (1200×630, recorte del hero). Observado: cuatro archivos, 45–102 kB.
- [x] **T1 — Rediseño de la landing según la skill** · ruta: delegada (más de
  dos archivos no triviales).
  - Estructura A2, copy A5, sistema visual B1–B11, navegación móvil, sección
    de tagline, FAQ con respuestas verificables, ilustraciones integradas.
  - Agente 06 deja de figurar como pendiente.
  - 404 propio, enlace para saltar al contenido, `openGraph`/`twitter`.
  - Observado (escritor, 2026-10-09): `npx tsc --noEmit` sale 0; `npm run
    build` sale 0 con 11 páginas estáticas; `npm run lint` **sale 1** por un
    error previo en `src/app/report/page.tsx:33`
    (`react-hooks/set-state-in-effect`), archivo que la rama no toca.
  - Repetido por el orquestador: `tsc` sale 0; `eslint` sobre los archivos
    cambiados sale 0; `report/`, `analyzing/`, `layout.tsx` y `lib/` sin
    diferencias; `globals.css` sin líneas eliminadas. Capturas de escritorio y
    móvil en tema claro revisadas.
  - Sin verificar: tema oscuro, interacción del menú móvil y las animaciones
    (las capturas se tomaron con movimiento reducido).

  - Commit: `665c947`.
  - Revisión nativa (2026-10-09): riesgo medio, consentimiento otorgado, un
    lente (fiabilidad), **aprobada** y acusada (`review-8bb3bc7c188fd81e`).
    Hallazgos no bloqueantes, quedan como trabajo posterior:
    1. `page.tsx:47`: `new URL(NEXT_PUBLIC_SITE_URL ?? …)` lanza si la variable
       está vacía o sin esquema.
    2. `landing/IslandNav.tsx:124-131`: Escape y la trampa de foco del menú
       móvil solo funcionan mientras el foco está dentro del header.
    3. `landing/IslandNav.tsx:75-77`: el observador lee la primera entrada del
       lote y no la última.
    4. El comportamiento interactivo no tiene ninguna comprobación automática.
    - Descartado: el aviso sobre `dark:` sin enlazar a `data-theme`;
      `globals.css:4` ya declara `@custom-variant dark` sobre ese atributo.

- [x] **T2 — Hallazgos 1 a 3 de la revisión** · ruta: en línea (un archivo no
  trivial, `IslandNav.tsx`, más dos ediciones mecánicas).
  - `page.tsx`: `resolveSiteUrl()` cae al origen local si la variable está
    vacía o no es una URL http(s). Observado: `npm run build` termina bien con
    `NEXT_PUBLIC_SITE_URL=` y con `NEXT_PUBLIC_SITE_URL=sin-esquema` (este
    último imprime el aviso).
  - `IslandNav.tsx`: Escape y la trampa de foco se escuchan en `document`
    mientras el menú está abierto; si el foco salió del header, Tab lo devuelve.
  - `IslandNav.tsx` y `TaglineReveal.tsx`: los observadores leen la última
    entrada del lote.
  - Observado: `tsc` sale 0, `eslint` sobre los archivos cambiados sale 0.
    Sin verificar: el menú con teclado en un navegador real.

## Pendientes

- Error de lint previo en `/report` (fuera del alcance de esta rama).
- `NEXT_PUBLIC_SITE_URL` sin definir: las etiquetas para compartir resuelven a
  `http://localhost:3000`.
- Favicon por defecto; sin política de privacidad ni términos.
- `.claude/CLAUDE.md` sigue describiendo la identidad Newsreader + Atkinson; se
  actualiza solo si la prueba se adopta.
- Confirmar el CTA "Solicitar acceso" → `/registro`.

## Entrega

Estrategia: `ask-on-risk`. Pronóstico: más de 400 líneas cambiadas (reescritura
de `page.tsx`, 442 líneas). La estrategia de cadena queda pendiente de decidir
con el usuario si la prueba se convierte en PR.

## Progreso

- 2026-10-09: rama creada, T0 hecha. Espejo en Engram pendiente
  (`mem_save` falló por sesiones duplicadas).
