# landing-explicativa Specification

## Purpose
Define el comportamiento observable de la página pública de NEXUS en `/`: qué debe
mostrar para explicar el sistema antes de que alguien cargue un caso clínico, y
cómo queda reubicado el flujo operativo de carga en `/analizar` para que ambas
rutas convivan sin romper la navegación existente.

## Requirements

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
La página de inicio SHALL describir como operativa la capacidad de los agentes ya
implementados (01 Analista de Literatura, 02 Especialista Genómica, 03 Consultor
Clínico, 04 Árbitro Verificador y 05 Navegador de Ensayos) y MUST NOT presentar al
Agente 06 (Sintetizador) como una funcionalidad activa del sistema.

#### Scenario: Agente pendiente marcado como no operativo
- **WHEN** la página de inicio enumera los seis agentes del sistema
- **THEN** el Agente 06 aparece identificado como pendiente o en desarrollo, y los
  Agentes 01 a 05 se describen cada uno con una capacidad real e implementada

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
El sistema SHALL mostrar las páginas que usan la paleta semántica (`/`, `/analizar`, `/registro`, `/ingresar`, `/cuenta` y `/admin/pendientes`) con el tema claro por defecto, sin importar el esquema de color preferido del sistema operativo. El sistema SHALL ofrecer en la barra de navegación de esas páginas un control para alternar entre el tema claro y el oscuro, operable con teclado y con un nombre accesible que indique la acción que realizará. El sistema SHALL recordar la elección en el navegador y aplicarla en todas esas páginas, desde el primer pintado. Si el navegador no permite guardar la elección, el sistema SHALL seguir funcionando en el tema claro. En ambos temas el texto MUST mantener un contraste de al menos 4.5:1.

#### Scenario: Preferencia de sistema en modo oscuro
- **WHEN** un usuario sin elección guardada visita la página de inicio con el sistema operativo en modo oscuro
- **THEN** el sistema muestra la página con el tema claro

#### Scenario: El usuario elige el tema oscuro
- **WHEN** el usuario activa el control de tema en la barra de navegación estando en el tema claro
- **THEN** el sistema muestra la página con el tema oscuro y el control pasa a ofrecer el cambio al tema claro

#### Scenario: La elección persiste al recargar y al cambiar de pantalla
- **WHEN** el usuario eligió el tema oscuro y recarga la página o navega a otra de las pantallas con paleta semántica
- **THEN** el sistema muestra la página directamente en el tema oscuro, sin un destello inicial en claro

#### Scenario: Control operable con teclado
- **WHEN** el usuario recorre la barra de navegación con la tecla Tab y activa el control con Enter o Espacio
- **THEN** el control recibe un foco visible y el tema cambia

#### Scenario: Almacenamiento no disponible
- **WHEN** el navegador impide guardar la elección (por ejemplo, en modo privado)
- **THEN** el sistema muestra el tema claro y el control sigue alternando el tema durante la sesión

#### Scenario: Contraste en ambos temas
- **WHEN** la página se muestra en el tema claro o en el oscuro
- **THEN** el texto mantiene un contraste de al menos 4.5:1 contra su fondo

### Requirement: Vista del reporte de ejemplo rotulada como ilustrativa
La página de inicio SHALL mostrar una vista del reporte de NEXUS con hipótesis de consenso, su nivel de evidencia y su estado (respaldada, pendiente o especulativa), los agentes que las sostienen, sus fuentes con el estado de verificación y un ensayo clínico con compatibilidad orientativa. La vista SHALL estar rotulada de forma visible como ejemplo ilustrativo, SHALL presentar las hipótesis como hipótesis de investigación y no como diagnósticos, y MUST ser legible para un lector de pantalla como texto, sin depender del color para distinguir los estados.

#### Scenario: Rótulo de ejemplo visible
- **WHEN** un usuario visualiza la vista del reporte en la página de inicio
- **THEN** el rótulo "Ejemplo ilustrativo" es visible junto a la vista y una nota aclara que su contenido es inventado

#### Scenario: Estados distinguibles sin color
- **WHEN** un lector de pantalla recorre las hipótesis de la vista
- **THEN** cada una expone su nivel de evidencia y su estado como texto, y la página explica en texto qué significa cada estado

### Requirement: Comparación entre la cita declarada y la de PubMed
La página de inicio SHALL mostrar, para una cita real de una corrida del sistema, el título tal como lo declaró un modelo junto al título que PubMed devuelve para el mismo PMID, y el veredicto del sistema expresado en texto (por ejemplo, "no coincide"), sin depender del color ni solo de un ícono.

#### Scenario: Cita que no coincide
- **WHEN** un usuario visualiza la comparación
- **THEN** ve el título citado, el título real del PMID y un veredicto en texto que indica que no coinciden y que la referencia no cuenta como respaldo

### Requirement: Procedencia y fecha del dato medido
La página de inicio SHALL presentar cualquier cifra medida sobre una corrida real como un caso medido, con la fecha de la corrida y sin redondearla a un porcentaje ni presentarla como una tasa general, y MUST NOT mostrar métricas de precisión, cantidades de usuarios ni testimonios que no estén respaldados por una fuente verificable.

#### Scenario: Cifra de una corrida real
- **WHEN** un usuario visualiza la cifra de citas que no coincidieron con PubMed
- **THEN** la página indica que proviene de una corrida real del caso de prueba, con su fecha, y aclara que es un caso medido y no una tasa general
