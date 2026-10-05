## Context

Los tokens semánticos viven en `frontend/src/app/globals.css` y los oscuros se activaban con `@media (prefers-color-scheme: dark)`. Las rutas `/report` y `/analyzing` usan colores fijos claros y no consumen esos tokens; `--background` y `--foreground` alimentan el `body` de todas las rutas y no deben cambiar. Ver `proposal.md` para la motivación.

## Goals / Non-Goals

**Goals:**
- Tema claro por defecto, elegido por el usuario y recordado, sin parpadeo ni errores de hidratación.
- Que `/report` y `/analyzing` no cambien de aspecto con ninguna elección.

**Non-Goals:**
- Rediseñar la paleta oscura.
- Seguir el esquema del sistema operativo como opción "automática".

## Decisions

- **Atributo `data-theme` en `<html>`** en lugar de la media query. Un único selector (`:root[data-theme="dark"]`) cubre los tokens, `color-scheme` y la variante `dark:` (`@custom-variant dark`). Alternativa descartada: una clase `dark`, equivalente pero menos explícita.
- **Script mínimo en línea en el `<head>`** que fija el atributo desde `localStorage` antes del primer pintado, con `try/catch`. Alternativa descartada: aplicarlo desde un efecto de React, que pinta primero en claro. `<html>` lleva `suppressHydrationWarning` porque el atributo cambia antes de hidratar.
- **El selector lee el tema con `useSyncExternalStore`**, con "claro" como instantánea del servidor: la hidratación coincide y luego se sincroniza con el atributo real. Alternativa descartada: estado local con un efecto, que provoca un render extra y una regla de lint.
- **`ThemeScope` marca `data-fixed-light` en `/report` y `/analyzing`**, porque el atributo sobrevive a la navegación del lado del cliente y esas rutas heredarían `color-scheme: dark`.

## Risks / Trade-offs

- [El atributo persiste al navegar de una pantalla con selector a una de colores fijas] → `ThemeScope` lo neutraliza para `color-scheme`; los tokens oscuros no afectan a esas rutas porque no los usan.
- [La clave de `localStorage` está duplicada en el script y en el componente] → comentario cruzado en ambos lugares.
