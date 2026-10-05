## 1. Identidad y tema

- [x] 1.1 Pasar los tokens a azul marino con acento ocre en `:root`, los oscuros a `:root[data-theme="dark"]`, agregar `@custom-variant dark` y `color-scheme`; verificar con `npm run build` y con el fondo computado en claro con el sistema en oscuro
- [x] 1.2 Fijar el tema guardado antes del primer pintado con un script en el `<head>` de `layout.tsx` (con `try/catch`) y `suppressHydrationWarning`; verificar que recargar con oscuro elegido no emite advertencias de hidratación
- [x] 1.3 Crear los íconos de sol y luna, `ThemeToggle` y `ThemeScope`, e incorporar el selector a la barra de las seis pantallas; verificar que a 375 px es visible y no desborda la barra
- [x] 1.4 Cargar Atkinson Hyperlegible y aplicarla con `font-body` solo en las pantallas con tokens; verificar con el `computed style` que `/report` conserva Geist y sus colores
- [x] 1.5 Reforzar el borde de los campos de formulario a 3:1 y revisar las pantallas internas con la paleta nueva; verificar con la tabla de contraste calculada

## 2. Landing demostrativa

- [x] 2.1 Construir la landing: hero con el aviso de alcance visible, vista del reporte de ejemplo (`ReportDemo`) rotulada como ilustrativa, comparación de la cita (`BeforeAfter`) con el veredicto en texto, cifras, flujo con diagrama y lista de etapas, seis agentes y cierre; verificar que las anclas de la barra existen
- [x] 2.2 Presentar los seis agentes con su rol, el 06 marcado en desarrollo; verificar que los textos coinciden con los de la landing anterior
- [x] 2.3 Mostrar el diagrama del pipeline en todos los anchos, con desplazamiento interno en móvil y la lista como alternativa textual; verificar que no hay scroll horizontal de la página a 375, 768, 1024 y 1440 px
- [x] 2.4 Eliminar la variante `/v2`, `ReportPreview` y los íconos sin uso; verificar que `npm run build` no lista `/v2` y que `rg` no encuentra restos

## 3. Verificación y documentación

- [x] 3.1 Comprobar en el navegador: claro por defecto con el sistema en oscuro, cambio a oscuro, persistencia al recargar y al navegar, `/v2` con 404 y `/report` sin cambios
- [x] 3.2 Actualizar `.claude/CLAUDE.md` en lo que quedó desactualizado
- [x] 3.3 Correr `openspec validate landing-demostrativa` y `openspec validate --all` y verificar que ambas pasan
