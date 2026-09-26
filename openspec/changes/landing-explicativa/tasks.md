## 1. Preparación y tokens de diseño

- [x] 1.1 Instalar dependencias del frontend si falta `node_modules` (`npm install` en `frontend/`) y revisar `frontend/node_modules/next/dist/docs/` (metadata, layouts anidados con página cliente, `next/font`) antes de tocar código; si la carpeta no existe tras instalar, dejar constancia en el commit de qué notas de versión de Next 16 se usaron en su lugar (design D11); verificar con `npm install` sin errores
- [x] 1.2 Definir los tokens semánticos de color monocromático (fondo, texto, texto atenuado, borde, acento) como custom properties en `frontend/src/app/globals.css`, con la variante oscura bajo `@media (prefers-color-scheme: dark)` (design D5); verificar con `npm run build` y alternando el tema del sistema operativo en el navegador
- [x] 1.3 Crear `frontend/src/lib/pipelineSteps.ts` con los pasos del pipeline según `.claude/architecture.md` (design D4); verificar con `npm run build`

## 2. Ruta /analizar (reubicación del flujo de carga)

- [ ] 2.1 Crear `frontend/src/app/analizar/page.tsx` moviendo la lógica cliente actual de `frontend/src/app/page.tsx` (formulario de carga, `useRouter`, `inputStore`, lista de pasos ahora leída de `pipelineSteps.ts`), sin el hero ni la grilla de agentes, re-skineada con los tokens de la tarea 1.2; verificar con `npm run build` y probando manualmente el envío del formulario hasta `/analyzing`
- [ ] 2.2 Crear `frontend/src/app/analizar/layout.tsx` (Server Component) con `export const metadata` propio de la ruta (design D3); verificar que `npm run build` genera la ruta y que el título de la pestaña difiere entre `/` y `/analizar`
- [ ] 2.3 Actualizar `frontend/src/app/analyzing/page.tsx` (línea del botón "Volver al inicio") y `frontend/src/app/report/page.tsx` (línea del botón "Nuevo análisis") para que sus `router.push("/")` apunten a `/analizar`; verificar navegando manualmente desde un error de análisis y desde "Nuevo análisis" en el reporte

## 3. Landing — header y hero

- [ ] 3.1 Reescribir `frontend/src/app/page.tsx` como Server Component (sin `"use client"`) con `export const metadata` propio, header minimalista (wordmark, enlaces de ancla, CTA a `/analizar` vía `next/link`, con espacio de layout para un futuro "Ingresar" sin implementarlo — design D9) y hero con titular, bajada y el disclaimer corto visible sin scroll; verificar con `npm run build` y una captura a 1440px confirmando que el disclaimer es visible sin hacer scroll
- [ ] 3.2 Crear el componente cliente `ScrollReveal` que aplica la animación de aparición al hacer scroll respetando `prefers-reduced-motion` y deja el contenido visible por defecto sin JavaScript (design D6); verificar deshabilitando JavaScript en el navegador y confirmando que el hero es visible, y activando "reducir movimiento" del sistema operativo y confirmando que no hay animación

## 4. Landing — cómo funciona (diagrama del pipeline)

- [ ] 4.1 Construir la sección "Cómo funciona" con el diagrama inline SVG/HTML del pipeline (agentes → debate rondas 1–4 → verificación/Árbitro + Ronda 5 → ensayos → reporte) usando `pipelineSteps.ts`, con `role="img"` y `aria-label` resumen; verificar con `npm run build` e inspeccionando el HTML generado
- [ ] 4.2 Agregar la alternativa textual accesible (lista visualmente oculta con los mismos pasos, en el mismo orden que el diagrama) para lectores de pantalla; verificar inspeccionando el DOM o con un lector de pantalla

## 5. Landing — agentes y funcionalidades clave

- [ ] 5.1 Construir la grilla de los 6 agentes con iconos SVG inline (sin emoji), marcando explícitamente al Agente 06 como pendiente/en desarrollo y describiendo a los Agentes 01, 02, 03, 04 y 05 con una capacidad real e implementada (design D8) — el Agente 02 se describe por su análisis genómico/molecular con guarda anti-invención sobre contexto que incluye anotaciones de PharmGKB; verificar releyendo `backend/agents/agent_02_genomics.py`, `.claude/architecture.md` y `.claude/backlog.md` contra el texto final (no `.claude/CLAUDE.md`, desactualizado en el estado del Agente 02 — ver design D8), confirmando que el único agente pendiente descrito como tal es el 06
- [ ] 5.2 Construir la sección de funcionalidades clave (3–5 tarjetas: verificación bibliográfica contra PubMed, clasificación EBM I/II/III, navegación de ensayos ClinicalTrials.gov + Orphanet, debate adversarial multi-agente) con iconos SVG inline; verificar con `npm run build`

## 6. Landing — CTA, footer y accesibilidad de interacción

- [ ] 6.1 Agregar la sección de CTA final ("Analizar un caso" → `/analizar` vía `next/link`) y el footer con el disclaimer completo y el crédito IRESM; verificar con una captura confirmando que el footer repite el texto completo del disclaimer
- [ ] 6.2 Revisar estados de foco visibles, `cursor-pointer` en elementos clicables y transiciones hover de 150–300ms en todos los elementos interactivos nuevos (nav, CTA, tarjetas); verificar navegando con teclado (Tab) y confirmando que el foco es visible en cada elemento interactivo

## 7. QA responsivo y evidencia

- [ ] 7.1 Ejecutar `npm run build` en `frontend/` y confirmar que compila sin errores nuevos (las advertencias de lint preexistentes del hallazgo H del backlog son ajenas a este cambio y no bloquean, ya que `next build` no corre lint); verificar con la salida del comando
- [ ] 7.2 Tomar capturas de `/` y de `/analizar` en 375px, 768px, 1024px y 1440px, en modo claro y oscuro, confirmando ausencia de scroll horizontal y contraste de texto ≥4.5:1; guardar las capturas como evidencia de la tarjeta de Trello correspondiente; verificar revisando cada captura contra los requisitos de `specs/landing-explicativa/spec.md`

## 8. Documentación

- [ ] 8.1 Actualizar `.claude/CLAUDE.md` (Sprint 4: sumar la landing y la ruta `/analizar` al árbol de carpetas del frontend, y corregir la tabla de numeración de agentes para que el 02 figure como implementado, no pendiente — ver design D8) y `.claude/backlog.md` (EP-08: nueva tarea con las decisiones D1–D11 resumidas); verificar con `openspec validate landing-explicativa --strict` y `npm run build`
