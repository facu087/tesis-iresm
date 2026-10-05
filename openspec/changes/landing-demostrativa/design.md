## Context

Los tokens semánticos viven en `frontend/src/app/globals.css`. `/report` y `/analyzing` usan colores fijos claros y no consumen esos tokens; `--background` y `--foreground` alimentan el `body` de todas las rutas y no deben cambiar. Ver `proposal.md` para la motivación.

## Goals / Non-Goals

**Goals:**
- Una landing que demuestre el producto con datos reales donde existan y rótulos explícitos donde no.
- Una identidad única para las pantallas con tokens, con contraste AA calculado en claro y oscuro.
- Tema claro por defecto, elegido por el usuario, recordado y sin parpadeo ni errores de hidratación.
- Que `/report` y `/analyzing` no cambien de aspecto con ninguna elección.

**Non-Goals:**
- Migrar `/report` y `/analyzing` a los tokens (queda para otra etapa).
- Seguir el esquema del sistema operativo como opción "automática".

## Decisions

- **Dirección de diseño.** La skill `ui-ux-pro-max` recomendó "demo de producto" con un patrón "antes y después", estilo suizo moderno con grilla editorial, azul marino con acento ocre, títulos en serifa y Atkinson Hyperlegible para el cuerpo. Se descartaron su perfil de "app de salud" con neumorfismo y testimonios, y el violeta de IA: no encajan con una herramienta sobria para médicos y los testimonios serían inventados.
- **Dato real, no inventado.** La comparación entre cita y PubMed usa el PMID 23686244 de la corrida real del caso de prueba del 2026-09-22 (`output/corrida_agente04/reporte.json`, carpeta local no versionada): el modelo citó "IgM paraprotein-associated neuropathy: clinical features and treatment" (Neurology, 2013) y PubMed devuelve "Paper-based transparent flexible thin film supercapacitors.". En esa misma corrida, 14 de 18 citas no coincidieron, 3 sí y 1 no traía PMID. Se presenta como un caso medido con su fecha, no como una tasa. La vista del reporte usa contenido inventado, rotulado como ejemplo ilustrativo.
- **Ocre de texto `#8a5206`** en lugar de `#a16207`, que daba 4,22:1 sobre la superficie sutil.
- **Tokens base en `:root`** y oscuro en `:root[data-theme="dark"]`, sin variantes por ruta. Los pares se calcularon con la fórmula de contraste WCAG.
- **Atkinson solo con tokens.** Se carga en el layout raíz como variable CSS y se aplica con la clase `font-body` en la raíz de cada pantalla con tokens; el `body` sigue en Geist, que es lo que usan `/report` y `/analyzing`.
- **Atributo `data-theme` en `<html>`** en lugar de la media query: un único selector cubre los tokens, `color-scheme` y la variante `dark:`. El script mínimo en el `<head>` lo fija desde `localStorage` antes del primer pintado, con `try/catch`, y `<html>` lleva `suppressHydrationWarning`.
- **El selector lee el tema con `useSyncExternalStore`**, con "claro" como instantánea del servidor, para hidratar sin desajustes.
- **`ThemeScope` marca `data-fixed-light`** en `/report` y `/analyzing`, porque el atributo sobrevive a la navegación del lado del cliente y esas rutas heredarían `color-scheme: dark`.
- **Diagrama del pipeline en todos los anchos.** Bajo 768 px conserva un ancho mínimo legible y se desplaza dentro de su propio contenedor, enfocable con teclado, sin provocar scroll horizontal de la página; la alternativa textual es la lista de etapas, con la misma secuencia.
- **Bordes de campos de formulario** en `fg-muted` (6,5:1 o más) en lugar del borde decorativo (1,4:1), para cumplir 3:1 en controles.

## Risks / Trade-offs

- [El atributo `data-theme` persiste al navegar de una pantalla con selector a una de colores fijos] → `ThemeScope` lo neutraliza para `color-scheme`; los tokens oscuros no afectan a esas rutas porque no los usan.
- [La clave de `localStorage` está duplicada en el script y en el componente] → comentario cruzado en ambos lugares.
- [El dato medido depende de un archivo local no versionado] → la procedencia y la fecha figuran en la propia página y en este documento.
