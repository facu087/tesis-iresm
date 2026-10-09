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

- [x] **T3 — Menos texto, el producto como imagen** · ruta: delegada (varios
  archivos no triviales).
  - Motivo (usuario, 2026-10-09): las ilustraciones generadas no gustaron y la
    página tiene demasiado texto.
  - Se quitan las tres ilustraciones y `og.jpg`; la imagen para compartir pasa
    a generarse con texto (`opengraph-image`).
  - Hero con una tarjeta real del reporte; verificación con la comparación de
    citas y el "14 de 18" como pieza central; pipeline como diagrama animado;
    agentes en fichas compactas con la descripción al enfocar; beneficios como
    anotaciones sobre el reporte de ejemplo; preguntas en acordeón, cinco.
  - Observado (escritor): `tsc` sale 0, `eslint` sobre lo cambiado sale 0,
    `npm run build` sale 0 con 12 páginas, `/` y `/opengraph-image` responden
    200. Palabras visibles: 1.625 → 913 (44 % menos; la meta era la mitad).
  - Repetido por el orquestador: `tsc` sale 0, 913 palabras, capturas de
    escritorio en tema claro revisadas.
  - Abierto: `opengraph-image.tsx` en la raíz aplica a todas las rutas y el
    build avisa que falta `metadataBase` fuera de `/` (se arregla en
    `layout.tsx`); la anotación 3 del reporte dice "Consenso entre agentes" y
    ya no "Desacuerdos a la vista"; tema oscuro del reporte y del pipeline sin
    revisar.

  - Commit: `6710745`. Revisión nativa: riesgo medio, consentimiento
    otorgado, **aprobada** y acusada (`review-60ddd6056ecaf956`).
    - Arreglado después: el respaldo sin JavaScript de las fichas de agentes
      estaba dentro de `@layer components` y lo pisaban las utilidades; ahora
      va fuera de toda capa. Observado en el CSS compilado tras `npm run build`.
    - Descartado: la estabilidad de `close` en `IslandNav.tsx` (es un
      `useCallback` sin dependencias).
    - Abierto: sin pruebas automáticas de interacción; tarjeta para compartir
      en la raíz sin `metadataBase` fuera de `/`.

- [x] **T4 — El logo como motivo de la landing** · ruta: delegada.
  - Pedido del usuario (2026-10-09) tras integrar el logo del PR #54.
  - Isotipo tenue detrás de la tarjeta del hero (oculto bajo `lg`), pipeline
    redibujado con nodos y trazo curvo que se encienden con el degradé, e
    isotipo dentro de la tarjeta del CTA final.
  - El trazado se define una vez (`LandingMarkSprite`) y se reutiliza con
    `<use>`. Observado: 1 aparición del trazado en el HTML servido.
  - Observado (escritor): `tsc`, `npm run lint` y `npm run build` salen 0;
    sin desborde horizontal ni errores de consola en claro y oscuro a 1280 y
    390 px; el pipeline enciende 0 → 2 → 6 → 8 etapas al hacer scroll.
  - Repetido por el orquestador: `tsc` sale 0; capturas del hero y del
    pipeline en claro y del CTA en oscuro revisadas.
  - Abierto: en pantallas chicas el isotipo del CTA queda detrás del texto al
    16 % de opacidad; el extremo claro del pipeline usa `#4a6fa1` y no el
    `#6e8bb0` del logo, por contraste de los números.

  - Commit: `cac7ebb`. Revisión nativa: consentimiento otorgado, pero el
    inicio se detuvo con `lens_context_budget_exceeded`: el tramo desde
    `6710745` incluye el merge de `develop` (PR #47, #49, #50 y #54, con el
    trazado y el SVG del logo) y no entra en el presupuesto del revisor. No se
    creó ninguna autoridad de revisión. Evaluado solo el commit del motivo
    (`8726c8b..cac7ebb`, 331 líneas): riesgo medio, `under_budget`, sin
    revisión debida. Los commits propios posteriores al merge quedan sin
    revisión nativa; los de `develop` se revisaron en sus PR.

- [x] **T5 — `/registro` e `/ingresar` con el sistema visual de la landing** ·
  ruta: delegada.
  - Motivo (usuario, 2026-10-09): "Solicitar acceso" saca al médico de la
    landing nueva y lo deja en una pantalla con la identidad anterior.
  - Amplía el alcance original (solo `/`) a esas dos rutas. Solo presentación:
    la lógica de los formularios, las llamadas al backend y el texto del
    consentimiento Ley 25.326 no cambian.
  - Fuera de alcance: `/cuenta`, `/admin/pendientes`, `/analizar`.
  - Observado (escritor): `tsc`, `npm run lint` y `npm run build` salen 0;
    las 21 cadenas de registro y las 12 de ingresar siguen presentes;
    `src/lib` sin diferencias; mismas llamadas (`registrarMedico`, `login`) y
    mismas redirecciones; sin desborde ni errores de consola en ambos temas a
    1280 y 390 px. Con el backend caído, `/ingresar` muestra el error en línea.
  - Repetido por el orquestador: `tsc` sale 0; `lib`, `cuenta`, `admin` y
    `analizar` sin diferencias; capturas de registro (claro) e ingresar
    (oscuro) revisadas.
  - Cambios de texto: "Ya tengo cuenta — Ingresar" pasó de la cabecera a
    debajo del botón; se agregaron los enlaces de la píldora y "Saltar al
    contenido".
  - Commit: `30e604d`. Revisión nativa del tramo `21e12dc..30e604d` (todo lo
    posterior al merge, 907 líneas): riesgo medio, consentimiento otorgado,
    **aprobada** y acusada (`review-119a7b3dd99e6e04`).
  - Hallazgo 1 (cableado de formularios sin prueba), comprobado después en un
    navegador con las respuestas del backend simuladas:
    - `/registro` no envía sin el consentimiento marcado; con él, manda las
      nueve claves de `RegistroMedicoPayload` con los valores cargados y
      redirige a `/ingresar?registrado=1`.
    - `/ingresar` manda `email` y `password`; ante un 401 muestra el `detail`
      en línea y se queda en la página; ante un 200 redirige a `/cuenta`.
  - Hallazgos abiertos: `LandingMark` no dibuja nada si la página no incluye
    `LandingMarkSprite`, y nada lo avisa; `PipelineDiagram.tsx:56` divide por
    cero si la lista tuviera una sola etapa (hoy tiene ocho).
  - Sin verificar: el alta y el ingreso contra el backend real.

- [x] **T6 — Hero interactivo** · ruta: delegada.
  - La tarjeta del reporte del hero pasa a tener tres pestañas (respaldada,
    pendiente, especulativa) con las tres hipótesis del reporte de ejemplo;
    al cambiar se ven el nivel de evidencia y el estado de la cita.
  - Sin texto nuevo: reutiliza el contenido de `ReportDemo.tsx`.
  - Observado (escritor): `tsc`, lint y build salen 0. En navegador, ambos
    temas a 1280 y 390 px: una sola pestaña seleccionada al cargar; clic y
    teclado (flechas con vuelta, Inicio, Fin) cambian hipótesis, nivel y
    estado; sin desplazamiento (botón del hero en 442,5 px y tarjeta de 481 px
    en las tres pestañas a 1280); sin desborde ni errores de consola; sin
    JavaScript se ve la primera hipótesis.
  - Repetido por el orquestador: `tsc` sale 0; capturas de "Respaldada" y
    "Especulativa" en claro revisadas.
  - Única cadena nueva: el nombre accesible de las pestañas, "Estado de la
    hipótesis". Palabras en el HTML: 961 (las dos hipótesis ocultas del hero).
  - Abierto: las pestañas "Pendiente" y "Especulativa" dejan espacio vacío
    abajo, porque el alto se reserva para la más larga.
  - Commit: `65c7d9f`. Revisión nativa: riesgo medio, consentimiento
    otorgado, **aprobada** y acusada (`review-d846c56400fa8787`).
    - Arreglado después: las teclas con modificador (Alt, Ctrl, Meta, Mayús)
      ya no cambian de pestaña. Observado: Alt+flecha deja "Respaldada",
      flecha sola pasa a "Pendiente".
    - Arreglado después: a 320 px se recortaban "Respaldada" (7 px) y
      "Especulativa" (13 px). Con letra más chica y menos margen bajo 360 px,
      el recorte medido es 0 a 320 y a 360 px.
    - Descartado: la transición con movimiento reducido; la regla global de
      `.landing` ya anula las transiciones.
    - Abierto: sin pruebas automáticas de las pestañas.

- [x] **T7 — La verificación como secuencia** · ruta: delegada.
  - Al entrar en pantalla, la comparación de citas se reproduce en tres
    tiempos: el título citado, la consulta a PubMed y el título real con el
    veredicto "no coincide". Se reproduce una vez; hay un control para verla
    de nuevo.
  - Sin texto nuevo salvo el control de repetición y un estado de consulta;
    los títulos y la nota de medición quedan literales.
  - Observado (escritor): `tsc`, lint y build salen 0; las 12 cadenas
    protegidas siguen literales. En navegador: no arranca antes del scroll;
    pasa por citado (0 ms), consulta (800), resultado (1900) y veredicto
    (2600), 3197 ms en total; no se repite al volver a pasar; "Ver de nuevo"
    la reinicia con clic y con teclado; dos clics seguidos dejan una sola
    corrida; alto del bloque idéntico en todos los muestreos (355 px a 1280,
    628 px a 390); con movimiento reducido o sin JavaScript se ve el estado
    final de entrada.
  - Repetido por el orquestador: `tsc` sale 0; capturas de la consulta y del
    estado final en claro revisadas.
  - Cadenas nuevas: "Ver de nuevo" y "Consultando PubMed".
  - Abierto: al recargar con la sección ya en pantalla se ve un instante el
    estado final antes de que arranque la secuencia.

## Pendientes

- ~~Error de lint previo en `/report`~~: resuelto por el PR #49, que entró con
  el merge de `develop` (`21e12dc`). `npm run lint` sale 0.
- `NEXT_PUBLIC_SITE_URL` sin definir: las etiquetas para compartir resuelven a
  `http://localhost:3000`.
- ~~Favicon por defecto~~: resuelto por el PR #54 (`icon.svg`). Sigue sin
  política de privacidad ni términos.
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
