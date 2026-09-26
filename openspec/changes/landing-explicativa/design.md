## Context

Motivación en `proposal.md` (§ Why). Requisitos en
`specs/landing-explicativa/spec.md`.

Estado actual relevado antes de proponer:

- `frontend/src/app/page.tsx` es un Client Component (`"use client"`) que combina
  hero, tarjeta de carga (`UploadForm`), lista de pasos del pipeline, grilla de
  6 agentes (con emoji) y footer con el disclaimer completo. Usa `useRouter` para
  ir a `/analyzing` tras cargar.
- `frontend/src/app/layout.tsx` ya carga `Geist`/`Geist_Mono` vía
  `next/font/google` y expone `--font-geist-sans`/`--font-geist-mono`, referenciadas
  como `--font-sans`/`--font-mono` en `globals.css`. No hace falta instalar ni
  cargar ninguna fuente nueva.
- `globals.css` solo define `--background`/`--foreground` (dos colores). El resto
  del color de la UI son clases Tailwind sueltas (`slate-900`, `blue-500/20`,
  `emerald-500/20`, etc.), sin tokens semánticos ni variante oscura.
- `frontend/src/app/analyzing/page.tsx:139` y `frontend/src/app/report/page.tsx:79`
  hacen `router.push("/")` como "volver al inicio" / "nuevo análisis". Hoy eso
  reabre el formulario de carga; con este cambio esa ruta pasa a ser la landing, así
  que ambos deben apuntar a `/analizar`.
- No hay corredor de tests de frontend (no hay Jest, Playwright ni React Testing
  Library en `package.json`); `tests/` en la raíz del repo es exclusivamente
  backend (Python/pytest). `npm run build` no corre lint (hallazgo H del backlog:
  ya hay 1 error y 1 warning de lint preexistentes, ajenos a este cambio).
- `frontend/AGENTS.md` advierte que esta versión de Next.js (16.2.7) tiene cambios
  incompatibles con el conocimiento de entrenamiento y pide leer
  `node_modules/next/dist/docs/` antes de escribir código. Esa carpeta no existe
  hoy en este worktree (dependencias no instaladas todavía).
- No existe ningún capability de OpenSpec sobre frontend o ruteo: `landing-explicativa`
  es una capability nueva, sin delta sobre una spec existente.

## Goals / Non-Goals

**Goals:**
- Landing explicativa en `/`, estilo vercel.com, minimalista y monocromática, que
  no mienta sobre qué agentes están implementados.
- Reubicar el flujo de carga a `/analizar` sin romper su comportamiento ni la
  navegación interna existente.
- Cero dependencias nuevas: reusar Geist (ya cargado) y CSS/IntersectionObserver
  para el movimiento.
- Dejar un layout de nav que pueda alojar un futuro "Ingresar" sin construirlo.

**Non-Goals:**
- Registro o login de médicos con verificación de matrícula (cambio futuro
  aparte, fuera de alcance).
- Agregar un corredor de tests de frontend (Jest/Playwright/RTL) como
  consecuencia de esta landing; sería su propio cambio de infraestructura.
- Agregar el disclaimer completo a `/analyzing` o `/report` (hoy no lo tienen);
  ver Open Questions.
- Implementar o simular el Agente 02 o el Agente 06 en la landing.
- Cambiar el backend, la API o el contrato `StructuredReport`.

## Decisions

### D1. La landing ocupa `/`; el formulario de carga se muda a `/analizar`
Decisión de producto ya tomada por el usuario. Dejar `/` como raíz pública
(estilo marketing) es la convención esperada y libera esa ruta para una futura
puerta de entrada (p. ej. redirigir según sesión) sin tocar `/analizar`.

- *Alternativa descartada — landing en `/inicio` o `/about`, formulario se queda en
  `/`*: contradice la decisión de producto ya tomada; además no resuelve el
  problema de que `/` sea una vista operativa sin contexto.

### D2. La landing (`/`) se implementa como Server Component; el CTA usa `next/link`
`frontend/src/app/page.tsx` deja de tener `"use client"`: es contenido estático
salvo la animación de scroll (D7, aislada en un componente cliente chico). El CTA
principal usa `<Link href="/analizar">`, no `useRouter`.

- *Alternativa descartada — mantener `"use client"` como hoy*: más simple de
  escribir, pero impide exportar `metadata` propio de la página (regla del stack:
  usar el export `metadata`, no manipular `<head>` a mano) y obliga a enviar JS de
  cliente para contenido que es puramente estático.

### D3. `/analizar` necesita seguir siendo cliente; su `metadata` vive en un `layout.tsx` hermano
El formulario (`useRouter`, `inputStore.set`, estado de UI) sigue siendo Client
Component, igual que hoy. Como un Client Component no puede exportar `metadata`,
se agrega `frontend/src/app/analizar/layout.tsx` (Server Component) que exporta el
`metadata` de esa ruta (título distinto al de la landing) y envuelve la página
cliente.

- *Alternativa descartada — `generateMetadata` dentro de la página cliente*: no es
  válido para Client Components.
- *Alternativa descartada — dejar `/analizar` sin `metadata` propio*: hereda el
  título genérico del layout raíz; pierde la distinción de pestaña entre "landing"
  y "cargar caso".

### D4. Los pasos del pipeline se leen de una única fuente compartida
Se crea `frontend/src/lib/pipelineSteps.ts` con los pasos (según
`.claude/architecture.md`), consumido tanto por el diagrama de la landing como por
la lista compacta que hoy vive en `/analizar` (movida sin quitar, ver D-Non-Goals).
Evita que ambas vistas describan el pipeline de forma distinta con el tiempo.

- *Alternativa descartada — texto duplicado en cada página*: es lo que ya pasa
  hoy entre `page.tsx` y `analyzing/page.tsx` (los `STEPS` de la vista de progreso
  no comparten fuente); no vale la pena repetir el problema en un cambio nuevo.

### D5. Paleta monocromática por tokens semánticos en `globals.css`, override explícito de la herramienta de diseño
Se agregan tokens (`--color-bg`, `--color-bg-subtle`, `--color-fg`,
`--color-fg-muted`, `--color-border`, `--color-accent`) en `:root`, redefinidos
bajo `@media (prefers-color-scheme: dark)`. Los CTAs usan la inversión
fondo/texto (negro sobre blanco / blanco sobre negro), no un color de marca.

La herramienta de diseño (`ui-ux-pro-max`, búsqueda "medical research SaaS minimal
monochrome") recomendó azul de confianza + naranja para el CTA y tipografía Plus
Jakarta Sans. Se descarta explícitamente esa recomendación por decisión del
usuario ("estilo Vercel"): monocromático, sin azul ni naranja, y se reusa Geist
(ya cargado, ver Contexto) en lugar de sumar una tipografía nueva.

- *Alternativa descartada — seguir la recomendación de la herramienta tal cual*:
  no es lo que pidió el usuario y suma una fuente nueva sin necesidad.

### D6. Movimiento: visible por defecto, reveal solo como mejora progresiva
El estado base en CSS es el final (`opacity: 1`, sin transformación), así que sin
JavaScript el contenido se ve completo. Un componente cliente chico
(`ScrollReveal`) agrega, después de montarse y solo si
`window.matchMedia("(prefers-reduced-motion: reduce)").matches` es `false`, una
clase que oculta levemente el contenido (8–16px, opacity 0) hasta que un
`IntersectionObserver` compartido lo revela (300–400ms) al entrar en el viewport;
deja de observar tras revelar (no se vuelve a ocultar). Sin dependencias nuevas
(nada de GSAP/Framer Motion).

- *Alternativa descartada — ocultar por CSS y revelar por JS (patrón típico)*:
  rompe la degradación sin JavaScript, que es un requisito explícito.
- *Alternativa descartada — `@starting-style`/scroll-driven animations nativas*:
  soporte de navegador todavía desigual (principalmente Chromium); no es una base
  confiable para una demo de tesis que puede mostrarse en cualquier navegador.

### D7. Iconos: SVG inline hechos a medida, sin librería de iconos
Se reemplazan los emoji de la grilla de agentes y se usan SVG inline (stroke,
`currentColor`) en el diagrama del pipeline y las tarjetas de funcionalidades. No
se suma ninguna librería de iconos (coherente con "sin librerías de UI" del stack).

### D8. Precisión sobre el estado de los agentes (no es una opción de estilo)
Los Agentes 01, 03, 04 y 05 se describen con una capacidad real e implementada
(verificación de PMIDs contra PubMed, clasificación EBM I/II/III, Ronda 5 de
recitación, navegación ClinicalTrials.gov + Orphanet). Los Agentes 02 y 06 se
marcan como pendientes/en desarrollo, sin describir ninguna capacidad activa,
siguiendo la tabla de estado de `.claude/CLAUDE.md` y `.claude/architecture.md`.

- *Alternativa descartada — describir los 6 agentes por igual*: presentaría al
  evaluador (Juan Lencina, profesor) capacidades que no existen todavía en el
  código; es exactamente el tipo de afirmación que este mismo repositorio evita en
  sus reportes clínicos (nunca se sobreafirma evidencia no verificada) y no
  corresponde sobreafirmarlo en el propio sitio del proyecto.

### D9. Nav con lugar para un futuro "Ingresar", sin implementarlo
El header usa una fila flexible (wordmark — enlaces de ancla — CTA) con espacio
para insertar un enlace/botón adicional antes o después del CTA. Es una nota de
diseño y una decisión de layout, no código: no se agrega ningún botón, enlace,
estado deshabilitado ni ruta para "Ingresar" en este cambio.

### D10. Evidencia para frontend sin corredor de tests: `npm run build` + capturas responsivas
Como no existe infraestructura de tests de frontend (Non-Goals) y el patrón
`scripts/demo_*.py` es exclusivamente backend (`openspec/config.yaml`), la
verificación de cada tarea de este cambio es `npm run build` (compila TypeScript y
build de producción) más capturas manuales en 375/768/1024/1440px, en ambos temas,
adjuntadas como evidencia de Trello. Esto sustituye, para este cambio puntual, a
"un test en `tests/`".

### D11. Verificación de APIs de Next 16 antes de escribir páginas
`frontend/AGENTS.md` exige leer `node_modules/next/dist/docs/` antes de escribir
código porque esta versión de Next tiene cambios incompatibles con el
conocimiento de entrenamiento. Esa carpeta no existe hoy en este worktree. La
primera tarea de implementación instala dependencias si hace falta y revisa esa
carpeta (metadata en layouts anidados con página cliente, `next/font`, rutas); si
la carpeta sigue sin existir tras instalar, se documenta explícitamente el uso de
las notas de versión de Next 16 como respaldo. Es una decisión de proceso, no
cambia comportamiento observable, por eso vive acá y no en la spec.

## Risks / Trade-offs

- [Los pasos del pipeline se describen en dos lugares (landing y `/analizar`) y
  podrían desincronizarse] → D4: fuente compartida en `frontend/src/lib/pipelineSteps.ts`.
- [Un `IntersectionObserver` mal ajustado podría parpadear o revelar de más]
  → D6: el estado base ya es visible; el observer solo agrega una clase y deja de
  observar tras el primer reveal, nunca vuelve a ocultar.
- [Quitar el hero y la grilla de agentes de `/` podría sorprender a quien tenga
  `/` guardado esperando el formulario] → aceptable en un prototipo de tesis
  pre-lanzamiento (Sprint 4, sin usuarios en producción); el CTA deja `/analizar`
  a un clic, y la navegación interna se corrige en el mismo cambio (D1–D3).
- [Next 16 puede tener APIs distintas a las esperadas por entrenamiento]
  → D11: chequeo obligatorio de `node_modules/next/dist/docs/` antes de codear.
- [Sin test automatizado, el rediseño depende de QA manual] → D10: `npm run build`
  más capturas responsivas explícitas por tarea, con checklist de contraste y
  scroll horizontal.
- [Advertencias de lint preexistentes (hallazgo H del backlog) podrían confundirse
  con errores de este cambio] → documentado en Contexto; `next build` no corre
  lint, así que no bloquean, y no se atribuyen a esta landing.

## Migration Plan

- Sin migración de datos ni de esquema: cambio de frontend estático.
- Landing y `/analizar` se entregan en el mismo cambio (no por etapas): una
  landing sin ruta de análisis alcanzable, o viceversa, dejaría la navegación
  rota.
- Rollback: revertir la rama; no hay acoplamiento con el backend ni con otros
  cambios de OpenSpec en curso.

## Open Questions

- ¿`/analyzing` y `/report` deberían sumar el disclaimer completo (hoy solo lo
  tiene `/`, y con este cambio lo tendrá `/analizar`)? Es una brecha preexistente,
  no introducida por este cambio; queda para un cambio aparte, a decidir por el
  usuario.
- Copy final (titular del hero, textos de las tarjetas de funcionalidades,
  etiquetas del nav): se redacta durante la implementación siguiendo la guardia de
  precisión D8; no es una decisión de alcance ni de comportamiento, así que no
  bloquea esta propuesta.
