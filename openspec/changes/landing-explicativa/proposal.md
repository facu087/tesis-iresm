## Why

`/` sirve hoy el formulario operativo de carga de casos clínicos, sin ninguna página
que explique qué es NEXUS, cómo funciona su pipeline o cuál es su alcance antes de
pedirle a alguien (evaluador de tesis, tutor, futuro médico) que suba un documento.
Eso perjudica la primera impresión ante quien evalúa el prototipo y deja `/` ocupado
por una vista operativa, sin lugar para una futura entrada de autenticación de
médicos ("Ingresar"). Se necesita una landing explicativa, minimalista, al estilo
vercel.com, que muestre el sistema y derive a la carga real del caso.

## What Changes

- Nueva página en `/`: landing explicativa (hero, disclaimer, cómo funciona el
  pipeline, agentes/funcionalidades clave, CTA, footer), sin formulario de carga.
- **BREAKING** (solo navegación interna, no hay API pública afectada): el
  formulario de carga de casos clínicos se traslada de `/` a `/analizar`. Los
  `router.push("/")` usados como "volver"/"nuevo análisis" en `/analyzing` y
  `/report` pasan a apuntar a `/analizar`.
- Nuevo sistema de color monocromático (tokens semánticos en `globals.css`, claro y
  oscuro vía `prefers-color-scheme`), en reemplazo de las clases Tailwind
  `slate-*`/`blue-*`/`emerald-*` sueltas en las páginas que este cambio toca.
- Reemplazo de los iconos emoji por SVG inline en las secciones nuevas/tocadas.
- Animación de aparición al hacer scroll (CSS/IntersectionObserver, sin dependencia
  nueva), respetando `prefers-reduced-motion` y visible por completo sin JavaScript.
- Fuera de alcance explícito: registro/login de médicos con verificación de
  matrícula (cambio futuro aparte). El layout del nav deja lugar para un futuro
  enlace "Ingresar", documentado como nota de diseño, sin implementarlo.

## Capabilities

### New Capabilities
- `landing-explicativa`: comportamiento observable de la landing pública en `/` y
  de la reubicación del flujo de carga de casos a `/analizar`.

### Modified Capabilities
(ninguna — no existe una spec vigente que cubra el frontend o el ruteo actual)

## Impact

- Archivos afectados: `frontend/src/app/page.tsx` (reescrita como landing),
  `frontend/src/app/analizar/page.tsx` y `frontend/src/app/analizar/layout.tsx`
  (nuevos — flujo de carga reubicado), `frontend/src/app/analyzing/page.tsx` y
  `frontend/src/app/report/page.tsx` (corregir los dos `router.push("/")`),
  `frontend/src/app/globals.css` (tokens de diseño), `frontend/src/lib/` (módulo
  compartido de pasos del pipeline). Sin impacto en backend ni en la API.
- Sin dependencias npm nuevas: Geist Sans/Mono ya está cargado vía `next/font` en
  `frontend/src/app/layout.tsx`; el movimiento es CSS/IntersectionObserver puro.
- El frontend no tiene corredor de tests (no hay Jest/Playwright/RTL en el repo);
  la evidencia de este cambio es `npm run build` más capturas responsivas manuales
  en 375/768/1024/1440, según se detalla en `design.md`.
- Documentación: `.claude/CLAUDE.md` y `.claude/backlog.md` (EP-08) se actualizan
  al cierre de la implementación.
