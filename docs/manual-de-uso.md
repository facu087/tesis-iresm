# Manual de uso de NEXUS

Este manual describe el uso de la aplicación web de NEXUS tal como funciona en la
versión actual del repositorio. Está dirigido a los dos perfiles de usuario del
sistema: el **médico**, que carga casos clínicos y lee los reportes, y el
**administrador**, que revisa las matrículas antes de habilitar las cuentas.

Los nombres de pantallas, botones y mensajes se citan entre comillas tal como
aparecen en la interfaz.

## 1. Alcance y regla general

NEXUS es un sistema de soporte investigativo clínico. Recibe la documentación de un
caso, la procesa con un conjunto de agentes de inteligencia artificial que debaten
entre sí y entrega un reporte con **hipótesis de investigación** priorizadas por nivel
de evidencia y respaldadas por referencias bibliográficas verificadas contra PubMed.

**NEXUS no emite diagnósticos.** Las rutas con sesión (`/analizar`, `/analyzing`,
`/report` y `/admin/pendientes`) muestran al pie el aviso:

> NEXUS no emite diagnósticos clínicos. Las hipótesis generadas son orientativas y
> deben ser evaluadas por el médico responsable.

El reporte trae además su propio descargo, que se muestra en `/report` y se imprime
en el PDF:

> NEXUS es un sistema de soporte investigativo. No emite diagnósticos clínicos. Las
> hipótesis generadas son orientativas y deben ser evaluadas por el médico
> responsable antes de tomar decisiones clínicas.

Toda decisión clínica sigue siendo responsabilidad del médico tratante.

## 2. Uso por parte del médico

### 2.1 Registro (`/registro`)

La pantalla "Registro de médicos" solicita los siguientes datos:

| Campo | Obligatorio | Validación |
|-------|-------------|------------|
| "Nombre" | Sí | No puede quedar vacío. |
| "Apellido" | Sí | No puede quedar vacío. |
| "DNI" | Sí | No puede quedar vacío. |
| "Profesión / especialidad" | No (opcional) | — |
| "Matrícula" | Sí | No puede quedar vacía. |
| "Jurisdicción de matriculación" | Sí | No puede quedar vacía (ejemplo sugerido: "Córdoba"). |
| "Email institucional" | Sí | Debe contener `@`, no empezar ni terminar con `@` y no contener espacios. |
| "Contraseña" | Sí | "Mínimo 8 caracteres." |

Antes de enviar, el médico debe marcar la casilla de consentimiento:

> Acepto el tratamiento de mis datos personales (nombre, DNI, matrícula, email y
> contraseña) con la finalidad de verificar mi habilitación profesional y darme
> acceso al pipeline de NEXUS, conforme a la Ley 25.326.

Sin esa casilla el servidor rechaza el alta con el mensaje "Debe aceptar el
tratamiento de datos personales (Ley 25.326)." El sistema también impide duplicar
identidades y responde, según el caso:

- "Ya existe una cuenta con ese DNI."
- "Ya existe una cuenta con ese email."
- "Ya existe una cuenta con esa matrícula en esa jurisdicción."

El registro se envía con el botón "Registrarme". Al completarse, la aplicación lleva
a `/ingresar` con el aviso de que la cuenta "quedó pendiente de revisión". La
contraseña se guarda solo como hash (Argon2id), nunca en texto plano.

### 2.2 Estados de la cuenta (`/cuenta`)

La pantalla "Mi cuenta" muestra el estado de la solicitud. Hay tres estados posibles
para una cuenta de médico:

| Estado | Título en pantalla | Qué puede hacer el médico |
|--------|--------------------|---------------------------|
| Pendiente | "Pendiente de revisión" | Esperar: un administrador revisará la matrícula contra los buscadores públicos. Todavía no puede analizar casos. |
| Rechazado | "Solicitud rechazada" | Leer el motivo que dejó el administrador, corregir los datos y reenviar la solicitud. |
| Verificado | "Cuenta verificada" | Analizar casos mediante el botón "Analizar un caso →". |

**Reenvío tras un rechazo.** Debajo del motivo aparece el formulario "Corregí tus
datos y reenviá la solicitud", con los mismos campos del registro (la jurisdicción
figura como "Jurisdicción"). La contraseña debe volver a definirse ("mínimo 8
caracteres") y el consentimiento debe marcarse de nuevo. Al pulsar "Reenviar
solicitud" la cuenta vuelve al estado pendiente. Solo una cuenta en estado rechazado
puede reenviar; cualquier otra recibe "Solo una cuenta de médico en estado
'rechazado' puede reenviar el registro."

Desde esta pantalla también se cierra la sesión con "Cerrar sesión".

### 2.3 Inicio de sesión (`/ingresar`)

La pantalla "Ingresar" pide "Email institucional" y "Contraseña". Tras un ingreso
correcto, el médico es llevado a `/cuenta` y el administrador a
`/admin/pendientes`.

- Ante credenciales incorrectas el mensaje es siempre "Email o contraseña
  incorrectos.", sin indicar si el email existe.
- Tras **5 intentos fallidos** consecutivos sobre una misma cuenta, el ingreso queda
  bloqueado durante **15 minutos**, aun con la contraseña correcta.

### 2.4 Duración de la sesión

La sesión dura `SESSION_TTL_MINUTES` minutos desde el inicio de sesión (60 por
defecto) y no se renueva con el uso. Una vez vencida, el sistema la trata como si no
existiera: las acciones protegidas responden "Sesión requerida." y es necesario
volver a ingresar. Conviene tenerlo en cuenta antes de lanzar un análisis largo
cerca del vencimiento.

## 3. Uso por parte del administrador

### 3.1 Alta del administrador

Ninguna instalación trae una cuenta de administrador por defecto. La da de alta
quien opera el servidor, por línea de comandos:

```bash
python -m backend.cli crear-admin --email admin@tu-dominio.example
```

La contraseña se pide de forma interactiva. Un administrador no analiza casos: si
intenta entrar a `/analizar` es redirigido a `/admin/pendientes`.

### 3.2 Revisión de cuentas pendientes (`/admin/pendientes`)

La pantalla "Cuentas pendientes" lista las solicitudes con el siguiente recordatorio:
"Revisá cada matrícula contra los buscadores públicos antes de decidir." Cada
solicitud muestra nombre y apellido, "Email", "DNI", "Matrícula" (con su
jurisdicción), "Profesión" (si se informó) y la fecha "Registrada".

Para contrastar los datos, cada tarjeta ofrece enlaces que se abren en una pestaña
nueva:

- **"Buscador Nacional REFEPS"**: el buscador nacional de profesionales de la salud
  del Ministerio de Salud. Siempre está presente y no es configurable.
- **"Buscador provincial"**: aparece solo si el servidor define la variable
  `PROVINCIAL_LICENSE_SEARCH_URL`. Puede quedar sin definir.

### 3.3 Aprobación y rechazo

| Acción | Campo requerido | Resultado |
|--------|-----------------|-----------|
| "Aprobar" | "Fuente consultada (obligatoria para aprobar)" — por ejemplo, "Buscador Nacional REFEPS" | La cuenta pasa a verificada y el médico ya puede analizar casos. |
| "Rechazar" | "Motivo (obligatorio para rechazar)" — por ejemplo, "los datos no coinciden con el buscador" | La cuenta pasa a rechazada y el médico ve el motivo en `/cuenta`. |

Sin el campo requerido, el servidor responde "Debe indicar la fuente consultada." o
"Debe indicar el motivo del rechazo.", según corresponda. La cuenta decidida
desaparece del listado.

### 3.4 Registro de auditoría

Cada aprobación o rechazo genera un registro de auditoría inmutable con el
administrador que decidió, la fecha y hora, la decisión, el motivo (en un rechazo) y
la fuente consultada. No es posible decidir sin que se genere ese registro. La
aplicación web no ofrece una pantalla para consultarlo: queda en la base de datos del
servidor (tabla `decision_auditoria`).

## 4. Ejecución de un análisis

### 4.1 Carga del caso (`/analizar`)

La pantalla "Cargar caso clínico" solo está disponible para médicos verificados. Sin
sesión, la aplicación lleva a `/ingresar`; con una cuenta pendiente o rechazada,
lleva a `/cuenta`. Esta comprobación es de experiencia de usuario: la protección real
está en el servidor, que rechaza el análisis con "Requiere una cuenta de médico
verificada." si la cuenta no está verificada.

Hay dos modos de carga, elegibles con las pestañas "Subir PDF" e "Ingresar texto":

- **Subir PDF.** Se arrastra el archivo ("Arrastrá un PDF aquí") o se lo selecciona
  con un clic. Solo se aceptan archivos PDF ("Solo se aceptan archivos PDF."). Si el
  PDF tiene texto, se extrae directamente; si es un documento escaneado sin texto, se
  aplica reconocimiento óptico de caracteres (OCR) en español e inglés.
- **Ingresar texto.** Se pega el texto del caso en el área "Pegá el texto del caso
  clínico aquí...".

Las imágenes sueltas (JPG, PNG) no se aceptan: un estudio en imagen debe incorporarse
dentro de un PDF. El texto extraído se limita a unos 500 KB; lo que excede ese tamaño
se descarta antes del análisis.

Errores posibles al enviar: "Seleccioná un archivo PDF.", "Ingresá el texto del caso
clínico.", "El archivo enviado está vacío." y "No se pudo extraer texto del
documento."

### 4.2 Progreso del análisis (`/analyzing`)

La pantalla "Analizando caso clínico" muestra una barra de avance, los segundos
transcurridos y los ocho pasos del pipeline, cada uno con estado "Pendiente",
"En curso" o "Completado":

| Paso | Nombre | Descripción |
|------|--------|-------------|
| 01 | Ingesta | Extracción de texto desde PDF nativo o escaneado (OCR). |
| 02 | Normalización | Nombres de fármacos (INN) y unidades de medida. |
| 03 | Síntesis PICO | Construcción del contexto clínico estructurado del caso. |
| 04 | Ronda 1 — Análisis paralelo | Los agentes 01 (Literatura), 02 (Genómica) y 03 (Clínico) generan hipótesis en simultáneo, sin verse entre sí. |
| 05 | Debate — Rondas 2 a 4 | Cada agente recibe las hipótesis de los demás, las critica y revisa las propias. |
| 06 | Verificación y arbitraje | El Agente 04 contrasta cada referencia citada contra PubMed, agrupa el consenso y pide una recitación (Ronda 5) a las hipótesis que quedaron sin respaldo. |
| 07 | Navegación de ensayos | El Agente 05 busca ensayos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet. |
| 08 | Reporte | Hipótesis priorizadas por nivel de evidencia (I, II, III), con sus fuentes y ensayos compatibles. |

El avance de los pasos es **orientativo**: el servidor no informa el progreso real,
de modo que la pantalla recorre los pasos con tiempos fijos (unos 42 segundos en
total) y deja el último "En curso" hasta que llega el reporte. Cuando el reporte
llega, la pantalla muestra "Completado — redirigiendo…" y abre `/report`.

**Duración.** En las corridas reales medidas sobre el caso de prueba, el análisis
completo tardó entre 502 y 517 segundos (unos ocho a nueve minutos). Gran parte del
tiempo se debe a los reintentos ante el límite de velocidad del proveedor del modelo.
No debe cerrarse la pestaña mientras tanto.

**Errores.** Si el análisis falla, la pantalla "Error en el análisis" muestra el
motivo y el botón "Volver a cargar el caso". Si el servidor no responde, el mensaje
es "No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo."
Cuando una fuente externa (PubMed, ClinicalTrials.gov, Orphanet) o un agente
posterior al debate falla, el análisis no se interrumpe: el reporte se entrega
igualmente e informa qué parte quedó incompleta.

## 5. Lectura del reporte (`/report`)

### 5.1 Encabezado y avisos

El "Reporte de análisis" muestra la versión de NEXUS, el botón "Descargar PDF" y una
barra de datos: "Hipótesis", "Tiempo", "Ensayos", "Fuentes" (por ejemplo, "8/8
verificadas") y "Generado". Debajo aparecen, en este orden, los avisos que
condicionan la lectura:

1. **Aviso de modo mock** (solo si corresponde), en rojo y antes que cualquier otro:
   "Reporte de modo mock: las hipótesis, el consenso y los ensayos NO provienen de un
   análisis real. Son respuestas grabadas para desarrollo — no corresponden a ningún
   paciente ni deben usarse para ninguna decisión clínica."
2. **Descargo** del reporte (ver sección 1).
3. **"Verificación bibliográfica:"** cuántas referencias se confirmaron contra
   PubMed, cuántas no se pudieron confirmar y cuántas hipótesis quedan especulativas
   o pendientes.
4. **"Árbitro:"** cuántas hipótesis del debate se consolidaron, cuántas objeciones
   quedaron sin resolver y el resultado de la recitación. Cierra siempre con la
   advertencia: "El consenso es entre agentes de inteligencia artificial: no es un
   diagnóstico ni una recomendación clínica."

### 5.2 Estado global de la verificación bibliográfica

| Estado | Significado | Cómo se muestra |
|--------|-------------|-----------------|
| `completa` | Todas las consultas a PubMed respondieron. | Aviso en verde con las referencias confirmadas. |
| `parcial` | Al menos una consulta respondió y al menos una falló. | "quedó incompleta", con la cantidad de referencias sin consultar y la causa. |
| `no_disponible` | Todas las consultas a PubMed fallaron. | "no se pudo hacer", con la cantidad y la causa. |
| `sin_consulta` | No había nada que consultar: ninguna fuente citada declaraba PMID. | Sin aviso de verificación. |

En los estados `parcial` y `no_disponible` la causa se informa en lenguaje llano:
"PubMed no respondió (sin conexión o tiempo de espera agotado).", "PubMed rechazó la
consulta por exceso de pedidos.", "PubMed rechazó la consulta: posible clave de
PubMed mal configurada en el servidor.", "PubMed devolvió un error." u "Ocurrió un
error no identificado al consultar PubMed." Una verificación incompleta nunca se
presenta como éxito.

### 5.3 Las cinco pestañas

| Pestaña | Contenido |
|---------|-----------|
| "Hipótesis" | "Resumen ejecutivo" y las hipótesis agrupadas por estado. |
| "Caso clínico" | "Narrativa clínica", "Perfil del paciente", "Motivo de consulta", "Duración de la enfermedad", "Tratamientos actuales", "Antecedentes relevantes" y "Procedimientos realizados". |
| "Debate" | "Rondas", "Críticas", "Divergencias", "Consenso" y la lista "Divergencias identificadas". |
| "Ensayos clínicos" | Ensayos activos relacionados y enfermedades raras de Orphanet. |
| "Bibliografía" | Todas las fuentes citadas con su veredicto de verificación. |

**Resumen ejecutivo.** Es un párrafo en prosa redactado por el Agente 06
(Sintetizador) a partir del reporte ya armado. Si el resumen menciona un PMID, un
ensayo o un gen que no figura en el reporte, se descarta y la sección no se muestra.

### 5.4 Hipótesis: estado y nivel de evidencia

Las hipótesis se agrupan en tres bloques:

| Estado | Bloque | Criterio |
|--------|--------|----------|
| Respaldada | "Hipótesis respaldadas" | "Al menos una referencia confirmada contra PubMed." |
| Pendiente | "Pendientes de verificación" | "Sus referencias no se pudieron consultar en PubMed: el nivel queda en III hasta poder confirmar las fuentes." |
| Especulativa | "Hipótesis especulativas" | "Ninguna referencia resistió la verificación. Se muestran, no se descartan." |

Cada hipótesis muestra su prioridad ("Alta", "Media", "Baja"), el distintivo
"Evidencia nivel I/II/III", los agentes que la sostienen ("Agente 01", etc.), el
"Veredicto del Árbitro", la "Justificación" y sus "Fuentes". Cuando corresponde,
también muestra "Objeciones sin resolver", "Sostiene con reservas", "Objeta",
"Recitada: consiguió respaldo" o "Recitada: sin respaldo".

El nivel de evidencia que se muestra es el **efectivo**: el que declaró el agente,
limitado por el tipo de publicación de sus fuentes verificadas (por ejemplo, un
ensayo aleatorizado o un metaanálisis permiten nivel I; un estudio observacional,
nivel II; un reporte de caso o una revisión narrativa, nivel III). La verificación
solo puede bajar el nivel, nunca subirlo, y una hipótesis sin fuentes verificadas
queda en nivel III. Si el nivel bajó, se indica entre paréntesis ("el agente declaró
I"). El orden del reporte es: estado, nivel, cantidad de agentes que la respaldan,
prioridad y cantidad de fuentes verificadas.

### 5.5 Veredicto de cada fuente

En las pestañas "Hipótesis" y "Bibliografía" cada fuente lleva uno de estos
veredictos: "verificada", "no corresponde" (el PMID existe pero es otro artículo; se
muestra el título real al lado del citado), "no existe", "sin PMID" o "no
verificable" (PubMed no respondió). Las fuentes "no corresponde" y "no existe"
aparecen tachadas.

### 5.6 Citas fuera de la literatura recuperada

Una cita con PMID solo se acepta si ese artículo fue ofrecido a los agentes por el
motor de recuperación de literatura (RAG). Las citas a artículos que el RAG no
ofreció se descartan antes de la verificación: no se consultan en PubMed y no
aparecen en el reporte. Las fuentes sin PMID (por ejemplo, una guía clínica) se
conservan. Ninguna hipótesis se descarta por este motivo: la que se queda sin fuentes
pasa a especulativa. El total de citas descartadas queda registrado en el reporte
JSON (`verification.fuera_del_rag`), pero hoy no se muestra en `/report` ni en el PDF.

### 5.7 Ensayos clínicos y enfermedades raras

Cada ensayo muestra su título, el identificador NCT, la compatibilidad, el estado de
reclutamiento ("Aún no recluta" si todavía no abrió), "Sede en Argentina" cuando la
tiene, la fase, "Por qué", "Criterios a verificar", "Hipótesis relacionadas",
"Condiciones", "Patrocinador", "Inicio", "Fin estimado", "Edad", "Sexo" y "Sedes".
La compatibilidad se indica como "Compatibilidad alta", "Compatibilidad media",
"Compatibilidad baja" o "Sin evaluar", con la aclaración: "La compatibilidad es
orientativa: la elegibilidad la determina el equipo investigador de cada ensayo."

Los ensayos cuyo rango de edad o sexo no admite al paciente se excluyen antes de
mostrarse, mediante reglas fijas (no por el modelo de IA). La cantidad de excluidos
por edad y por sexo queda en el reporte JSON, pero hoy no se muestra en pantalla ni
en el PDF.

El bloque "Enfermedades raras relacionadas (Orphanet)" lista las hipótesis que
coinciden con una enfermedad rara catalogada (código ORPHA), con la aclaración "No
son diagnósticos del paciente."

Si alguna consulta falló, el aviso "Estado de la búsqueda:" lo informa (por ejemplo,
"ClinicalTrials.gov no se pudo consultar"). Una lista vacía por falta de respuesta se
distingue de una búsqueda sin resultados: "No se pudo consultar ClinicalTrials.gov:
esto no significa que no existan ensayos relacionados."

### 5.8 Debate y divergencias

La pestaña "Debate" informa si hubo consenso: "Consenso alcanzado — ninguna hipótesis
de alta prioridad fue rechazada por los agentes." o "Divergencias de alta prioridad —
revisá las hipótesis marcadas con cautela." Debajo se listan las divergencias
identificadas entre los agentes.

## 6. Exportación a PDF

El botón "Descargar PDF" envía el reporte a `POST /api/report/pdf`, que exige la
misma sesión de médico verificado que el análisis, y descarga un archivo con nombre
`nexus_reporte_AAAAMMDD_HHMMSS.pdf`. Si falla, aparece "No se pudo generar el PDF.
Verificá que el backend esté activo."

El PDF contiene, en este orden:

1. **Portada**: versión, fecha, cifras principales (hipótesis, ensayos, fuentes,
   referencias verificadas, hipótesis con respaldo, objeciones sin resolver, rondas y
   tiempo de procesamiento), el aviso de modo mock si corresponde, el aviso de
   verificación incompleta con su causa, el resumen del Árbitro y el descargo.
2. "RESUMEN DEL CASO CLÍNICO".
3. "RESUMEN EJECUTIVO" (si el Agente 06 lo produjo).
4. "HIPÓTESIS DE INVESTIGACIÓN", agrupadas por estado, con nivel, fuentes y
   veredictos.
5. "RESUMEN DEL DEBATE ADVERSARIAL".
6. "ENSAYOS CLÍNICOS ACTIVOS RELEVANTES", con su compatibilidad.
7. "BIBLIOGRAFÍA".

## 7. Tema claro y oscuro

El tema claro es el predeterminado. El selector de la barra superior alterna entre
"Claro" y "Oscuro"; la preferencia se recuerda en el navegador. Todas las pantallas
admiten ambos temas.

## 8. Buenas prácticas y límites

- **Verificar cada cita.** La verificación confirma que el PMID corresponde al
  artículo citado, no que el artículo respalde la hipótesis. Esa evaluación es del
  médico. Conviene abrir los enlaces de PubMed antes de usar una referencia.
- **Anonimizar antes de subir.** La anonimización automática de documentos está en
  revisión (PR #82 de GitHub) y **todavía no está activa**: el médico debe quitar nombre, DNI,
  domicilio y cualquier dato identificatorio del paciente antes de cargar el caso.
- **El reporte no se guarda en el servidor.** El documento se procesa en memoria y no
  se escribe a disco; el reporte vive solo en la pestaña del navegador (almacenamiento
  de sesión) y se pierde al cerrarla. Para conservarlo, se debe descargar el PDF.
- **Cuota diaria limitada.** Con el modelo gratuito actual (Groq, cuota de 200.000
  tokens por día) y un consumo medido de entre 80.000 y 85.000 tokens por caso, el
  sistema admite unos **dos análisis reales por día**.
- **Leer los avisos primero.** Un aviso de modo mock, de verificación incompleta o de
  búsqueda de ensayos fallida cambia cómo debe leerse todo el reporte.
- **Las hipótesis especulativas no se descartan.** Se muestran para no ocultar
  información, pero carecen de respaldo bibliográfico verificado.

## 9. Preguntas frecuentes

**¿Por qué no puedo analizar casos si ya me registré?**
La cuenta queda pendiente hasta que un administrador verifica la matrícula. El
estado se consulta en `/cuenta`; el análisis se habilita cuando figura "Cuenta
verificada".

**Mi solicitud fue rechazada. ¿Tengo que registrarme de nuevo?**
No. En `/cuenta` se ve el motivo y el formulario para corregir los datos y reenviar
la misma solicitud, que vuelve a quedar pendiente.

**¿Por qué el análisis tarda tanto si los pasos avanzan rápido?**
Los pasos de `/analyzing` son una representación orientativa con tiempos fijos. El
análisis real tarda unos ocho a nueve minutos en las corridas medidas, y el último
paso permanece "En curso" hasta que el servidor responde.

**¿Puedo subir una fotografía de un estudio?**
No. Solo se aceptan PDF (con texto o escaneados) y texto pegado. Una imagen debe
convertirse antes a PDF; el OCR se aplica automáticamente a los PDF sin texto.

**Una hipótesis declara nivel I pero el reporte muestra nivel III. ¿Por qué?**
El nivel se limita según el tipo de publicación de las fuentes que superaron la
verificación. Si ninguna fuente quedó "verificada", el nivel es III, cualquiera sea
el que declaró el agente.

**¿Qué significa el aviso rojo de modo mock?**
Que el reporte se generó con respuestas grabadas para desarrollo y no con un análisis
real. No corresponde a ningún paciente y no debe usarse para ninguna decisión.
