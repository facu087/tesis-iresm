## Purpose

Define el comportamiento observable de la página pública de NEXUS en `/`: qué debe
mostrar para explicar el sistema antes de que alguien cargue un caso clínico, y
cómo queda reubicado el flujo operativo de carga en `/analizar` para que ambas
rutas convivan sin romper la navegación existente.

## ADDED Requirements

### Requirement: Página de inicio explicativa
El sistema SHALL presentar en la ruta `/` una página explicativa que describa el
propósito de NEXUS, su flujo de análisis y una llamada a la acción hacia el
análisis de un caso, sin requerir que el usuario cargue un documento para
entenderla.

#### Scenario: Visita a la raíz del sitio
- **WHEN** un usuario visita `/`
- **THEN** el sistema muestra la página explicativa (introducción, cómo funciona,
  agentes/funcionalidades clave, llamada a la acción) en vez del formulario de
  carga de casos

### Requirement: Reubicación del flujo de carga a /analizar
El sistema SHALL exponer el formulario de carga de casos clínicos, antes servido
en `/`, en la ruta `/analizar`, conservando su comportamiento funcional (carga de
PDF o texto, validaciones existentes, redirección a `/analyzing` al enviarlo).

#### Scenario: Acceso directo a la carga de casos
- **WHEN** un usuario visita `/analizar`
- **THEN** el sistema muestra el formulario de carga de casos clínicos y, al
  enviarlo con datos válidos, redirige a `/analyzing`

#### Scenario: La llamada a la acción de la landing lleva al análisis
- **WHEN** un usuario hace clic en la llamada a la acción principal de la página
  de inicio
- **THEN** el sistema navega a `/analizar`

### Requirement: Navegación interna consistente tras la reubicación
El sistema SHALL dirigir a `/analizar`, y no a `/`, cualquier acción interna de
"nuevo análisis" o "volver al inicio" ya existente en la vista de progreso
(`/analyzing`) y en la vista de reporte (`/report`).

#### Scenario: Volver al inicio desde un error de análisis
- **WHEN** el usuario está en `/analyzing` con un error visible y hace clic en
  "Volver al inicio"
- **THEN** el sistema navega a `/analizar`

#### Scenario: Nuevo análisis desde el reporte
- **WHEN** el usuario está en `/report` y hace clic en "Nuevo análisis"
- **THEN** el sistema navega a `/analizar`

### Requirement: Representación fiel del estado de los agentes
La página de inicio SHALL describir como operativa únicamente la capacidad de los
agentes ya implementados (01 Analista de Literatura, 03 Consultor Clínico, 04
Árbitro Verificador y 05 Navegador de Ensayos) y MUST NOT presentar al Agente 02
(Especialista Genómica) ni al Agente 06 (Sintetizador) como funcionalidades activas
del sistema.

#### Scenario: Agentes pendientes marcados como no operativos
- **WHEN** la página de inicio enumera los seis agentes del sistema
- **THEN** el Agente 02 y el Agente 06 aparecen identificados como pendientes o en
  desarrollo, y ninguno de los dos se describe con una capacidad activa

### Requirement: Disclaimer de alcance clínico visible sin desplazamiento
El sistema SHALL mostrar, sin necesidad de que el usuario haga scroll, un texto que
indique que NEXUS no emite diagnósticos y que genera hipótesis de investigación
para el médico responsable.

#### Scenario: Carga inicial de la página de inicio en escritorio
- **WHEN** la página de inicio termina de cargar en un viewport de 1440px de ancho
- **THEN** el texto del disclaimer es visible sin necesidad de hacer scroll

#### Scenario: Repetición del disclaimer en el pie de página
- **WHEN** el usuario llega al final de la página de inicio
- **THEN** el pie de página muestra el texto completo del disclaimer

### Requirement: Diagrama del pipeline con alternativa textual
El sistema SHALL presentar un diagrama del flujo del pipeline (agentes → debate →
verificación/Árbitro → ensayos → reporte) acompañado de una alternativa textual
equivalente para lectores de pantalla.

#### Scenario: Recorrido con lector de pantalla
- **WHEN** un lector de pantalla recorre la sección del diagrama del pipeline
- **THEN** encuentra una descripción o lista textual con la misma secuencia de
  pasos que el diagrama visual

### Requirement: Movimiento accesible y degradación sin JavaScript
Cualquier animación de aparición al hacer scroll en la página de inicio SHALL
respetar la preferencia `prefers-reduced-motion` del usuario, y el contenido MUST
renderizarse completo y visible cuando JavaScript está deshabilitado.

#### Scenario: Preferencia de movimiento reducido activada
- **WHEN** el usuario tiene activada la preferencia de sistema de movimiento
  reducido
- **THEN** las secciones de la página de inicio aparecen sin animación de
  transición

#### Scenario: JavaScript deshabilitado
- **WHEN** JavaScript está deshabilitado en el navegador
- **THEN** todo el contenido de la página de inicio es visible igualmente, sin
  depender de la animación de scroll para mostrarse

### Requirement: Diseño responsivo sin scroll horizontal
La página de inicio SHALL renderizarse sin scroll horizontal en anchos de viewport
de 375px, 768px, 1024px y 1440px.

#### Scenario: Viewport de teléfono
- **WHEN** la página de inicio se visualiza en un viewport de 375px de ancho
- **THEN** no aparece scroll horizontal y el contenido permanece legible

### Requirement: Soporte de tema claro y oscuro
El sistema SHALL adaptar los colores de la página de inicio al esquema de color
preferido del sistema operativo del usuario (claro u oscuro), manteniendo un
contraste de texto de al menos 4.5:1 en ambos.

#### Scenario: Preferencia de sistema en modo oscuro
- **WHEN** el sistema operativo del usuario tiene activado el modo oscuro
- **THEN** la página de inicio se muestra con la paleta oscura definida, sin texto
  de bajo contraste
