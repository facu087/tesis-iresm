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
