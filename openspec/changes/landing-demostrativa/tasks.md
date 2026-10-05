## 1. Tokens y variante oscura

- [x] 1.1 Pasar los tokens oscuros (incluidos los de la región de marca) de `@media (prefers-color-scheme: dark)` a `:root[data-theme="dark"]`, agregar `@custom-variant dark` y `color-scheme`; verificar con `npm run build` y con el fondo computado en claro con el sistema en oscuro
- [x] 1.2 Fijar el tema guardado antes del primer pintado con un script en el `<head>` de `layout.tsx` (con `try/catch`) y `suppressHydrationWarning`; verificar que recargar con oscuro elegido no emite advertencias de hidratación en consola

## 2. Selector de tema

- [x] 2.1 Crear los íconos de sol y luna en `components/icons.tsx` y el componente cliente `ThemeToggle` (botón con nombre accesible, foco visible, área táctil de 44 px, estado también en texto); verificar con `npx tsc --noEmit` y `npm run lint`
- [x] 2.2 Crear `ThemeScope` para que `/report` y `/analyzing` queden siempre en claro; verificar con el `color-scheme` computado en esas rutas tras elegir oscuro
- [x] 2.3 Incorporar el selector a la barra de `/`, `/analizar`, `/registro`, `/ingresar`, `/cuenta` y `/admin/pendientes`; verificar que a 375 px es visible y no desborda la barra

## 3. Verificación

- [x] 3.1 Comprobar en el navegador: claro por defecto con el sistema en oscuro, cambio a oscuro, persistencia al recargar y al navegar, vuelta a claro, operación solo con teclado y consola limpia
- [x] 3.2 Correr `openspec validate selector-de-tema` y `openspec validate --all` y verificar que ambas pasan
