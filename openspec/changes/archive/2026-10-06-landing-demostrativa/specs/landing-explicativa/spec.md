## MODIFIED Requirements

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

## ADDED Requirements

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
