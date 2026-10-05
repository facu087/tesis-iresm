## Why

La paleta oscura se activaba sola cuando el sistema operativo estaba en modo oscuro, sin que la persona pudiera elegir. Quien tiene el sistema en oscuro veía siempre esa paleta y no tenía un control para volver al tema claro, que es la identidad principal de NEXUS (papel y verde petróleo).

## What Changes

- El tema claro pasa a ser el predeterminado, sin mirar `prefers-color-scheme`.
- Se agrega un control en la barra de navegación para alternar entre claro y oscuro, disponible también en pantallas angostas.
- La elección se recuerda en el navegador y se aplica en todas las pantallas que usan la paleta semántica: `/`, `/analizar`, `/registro`, `/ingresar`, `/cuenta` y `/admin/pendientes`.
- La elección se aplica antes del primer pintado, para que quien eligió oscuro no vea un destello claro.
- `/report` y `/analyzing` conservan sus colores fijos en claro y no llevan el control.
- **BREAKING**: el requisito "Soporte de tema claro y oscuro" deja de seguir el esquema del sistema operativo.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `landing-explicativa`: el requisito "Soporte de tema claro y oscuro" pasa de seguir el esquema del sistema operativo a mostrar claro por defecto, con un control en la barra y la elección recordada.

## Impact

- Frontend: `globals.css` (selector por atributo en lugar de `@media`, variante `dark:`, `color-scheme`), `layout.tsx` (script de tema inicial), un componente de selector y uno de alcance por ruta, y la barra de las seis pantallas.
- Sin cambios en el backend, en el PDF ni en dependencias.
