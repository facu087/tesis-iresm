## Why

La landing explicaba el sistema con texto y listas en lugar de demostrarlo: quien llegaba no veía qué recibe un médico ni por qué la verificación importa. Además, la paleta oscura se activaba sola cuando el sistema operativo estaba en modo oscuro, sin que la persona pudiera elegir, y el sitio tenía una identidad (papel y verde petróleo) que no transmitía el carácter institucional de una herramienta para médicos.

## What Changes

- La página de inicio pasa a demostrar el producto: una vista del reporte de ejemplo a todo el ancho (rotulada como ejemplo ilustrativo), una comparación entre una cita declarada por un modelo y lo que devuelve PubMed para ese PMID, las cifras del sistema, el flujo de ocho etapas con su diagrama, los seis agentes y el cierre con la acción.
- La identidad visual del sitio pasa a azul marino institucional con acento ocre, títulos en serifa (Newsreader) y cuerpo en Atkinson Hyperlegible, para las pantallas que usan los tokens semánticos: `/`, `/analizar`, `/registro`, `/ingresar`, `/cuenta` y `/admin/pendientes`.
- El tema claro es el predeterminado, sin mirar `prefers-color-scheme`, con un control en la barra para alternar, la elección recordada en el navegador y aplicada antes del primer pintado.
- `/report` y `/analyzing` conservan sus colores y tipografía fijos y no llevan el control.
- **BREAKING**: el requisito "Soporte de tema claro y oscuro" deja de seguir el esquema del sistema operativo.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `landing-explicativa`: se reescribe el requisito de tema claro y oscuro y se agregan los requisitos de la vista del reporte de ejemplo, de la comparación entre cita declarada y cita de PubMed, y de la procedencia del dato medido. El resto de los requisitos se sigue cumpliendo sin cambios.

## Impact

- Frontend: `globals.css` (tokens azul marino y ocre, tema por atributo en `<html>`, variante `dark:`, `color-scheme`, fuente de cuerpo), `layout.tsx` (script de tema inicial y fuentes), la landing, los componentes `ReportDemo`, `BeforeAfter`, `DebateDiagram`, `ThemeToggle` y `ThemeScope`, y la barra de las seis pantallas con tokens. Se eliminan `ReportPreview` y cuatro íconos sin uso.
- Sin cambios en el backend, en el PDF ni en dependencias.
