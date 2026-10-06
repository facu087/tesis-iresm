## Purpose

Construir, sin LLM y de forma reproducible, el perfil genómico de un caso clínico que consume el Agente 02:
qué reporta el caso, qué solo menciona, qué dicen las fuentes farmacogenómicas externas y en qué estado
quedó cada fuente, sin enviar nunca texto clínico fuera del sistema.

## ADDED Requirements

### Requirement: Perfil genómico determinista del caso
El sistema SHALL construir el perfil genómico de un caso a partir de los biomarcadores extraídos y de la
síntesis PICO, sin llamar a ningún LLM. El perfil MUST distinguir entre:
- **hallazgos reportados**: variantes genéticas y hallazgos genéticos positivos que el caso informa;
- **menciones**: genes nombrados en el documento, cuya sola mención NO implica alteración;
- **estudios genéticos negativos**: estudios negativos de la síntesis PICO que refieren a genes, paneles,
  secuenciación, exoma, variantes o mutaciones.

Un hallazgo genético de la síntesis PICO redactado como resultado negativo (contiene "negativo", "sin
variantes", "no se detect" o "normal") MUST clasificarse como estudio genético negativo y no como hallazgo
reportado.

El perfil SHALL quedar en modo **con hallazgos genómicos** si y solo si tiene al menos una variante o un
hallazgo genético positivo; en cualquier otro caso SHALL quedar en modo **sin hallazgos genómicos**. La
mención de genes, por sí sola, MUST NOT activar el modo con hallazgos.

#### Scenario: Caso base sin hallazgos genómicos
- **WHEN** se construye el perfil del caso de neuropatía axonal sensitivomotora (hombre de 42 años) cuyos
  biomarcadores no traen variantes, cuya síntesis PICO no trae hallazgos genéticos positivos y cuyos
  estudios negativos incluyen "Panel CMT 40 genes negativo"
- **THEN** el perfil queda en modo sin hallazgos genómicos, con cero variantes, y lista "Panel CMT 40 genes
  negativo" como estudio genético negativo

#### Scenario: Caso con variante reportada
- **WHEN** se construye el perfil de un caso cuyos biomarcadores traen el gen `TTR` y la variante `p.Val30Met`
- **THEN** el perfil queda en modo con hallazgos genómicos y lista `p.Val30Met` como hallazgo reportado

#### Scenario: Estudio negativo cargado como hallazgo genético
- **WHEN** la síntesis PICO trae "Panel genético CMT (40 genes) negativo" dentro de los hallazgos genéticos
- **THEN** ese texto se clasifica como estudio genético negativo y el perfil queda en modo sin hallazgos
  genómicos

#### Scenario: Genes mencionados sin variantes
- **WHEN** el caso nombra el gen `PMP22` pero no trae variantes ni hallazgos genéticos positivos
- **THEN** `PMP22` figura como gen mencionado y el perfil queda en modo sin hallazgos genómicos

#### Scenario: Reproducibilidad
- **WHEN** se construye dos veces el perfil del mismo caso
- **THEN** ambos perfiles son idénticos

### Requirement: Saneamiento de símbolos de genes
El sistema SHALL conservar como gen solo los símbolos con formato de símbolo génico (mayúscula inicial,
letras mayúsculas, dígitos o guion, entre 2 y 10 caracteres) que no pertenezcan a una lista de siglas que
no son genes (enfermedades como `CMT`, `FAP`, `ATTR`, `HMSN`, `CIDP` y siglas clínicas como `EMG`, `LCR`).
Los símbolos descartados MUST quedar registrados como descartados en el perfil y MUST NOT presentarse al
agente como genes ni enviarse a fuentes externas.

#### Scenario: Sigla de enfermedad extraída como gen
- **WHEN** los biomarcadores del caso base traen `CMT` en la lista de genes
- **THEN** `CMT` queda registrado como descartado y la lista de genes del perfil queda vacía

#### Scenario: Símbolo génico válido
- **WHEN** los biomarcadores traen `TTR`
- **THEN** `TTR` se conserva en la lista de genes del perfil

#### Scenario: Entrada que no es un símbolo
- **WHEN** los biomarcadores traen una entrada con espacios o minúsculas, como `gen de la transtiretina`
- **THEN** la entrada queda descartada y no se envía a ninguna fuente externa

### Requirement: Enriquecimiento farmacogenómico por gen
El sistema SHALL consultar PharmGKB solo por los genes saneados del perfil, con un máximo de 3 genes por
caso, y SHALL agregar al perfil las anotaciones clínicas encontradas (gen, fármaco, fenotipo, variante y
nivel de evidencia PharmGKB). Si el perfil no tiene genes saneados, el sistema MUST NOT hacer ninguna
consulta externa. El sistema MUST NOT consultar PharmGKB por nombres de fármacos en este cambio.

#### Scenario: Caso sin genes saneados
- **WHEN** se enriquece el perfil del caso base (sin genes tras el saneamiento)
- **THEN** no se realiza ninguna solicitud a PharmGKB y la fuente queda en estado `no_consultada`

#### Scenario: Más de tres genes
- **WHEN** el perfil tiene 5 genes saneados
- **THEN** se consulta PharmGKB solo por los 3 primeros, en el orden del perfil

#### Scenario: Anotaciones encontradas
- **WHEN** PharmGKB devuelve anotaciones clínicas para `TTR`
- **THEN** el perfil incluye esas anotaciones con su nivel de evidencia PharmGKB y la fuente queda en estado
  `consultada`

### Requirement: Anonimización de las consultas externas
Toda solicitud a una fuente genómica externa MUST contener únicamente símbolos de genes saneados. Las
solicitudes MUST NOT contener narrativa clínica, perfil del paciente, antecedentes, estudios negativos,
nombres de fármacos ni ningún otro texto del documento clínico.

#### Scenario: Contenido de la solicitud
- **WHEN** se enriquece el perfil de un caso con el gen `TTR` y una narrativa clínica que menciona edad, sexo
  y antecedentes familiares
- **THEN** los parámetros enviados a PharmGKB contienen `TTR` y ningún fragmento de la narrativa, del perfil
  del paciente ni de los estudios negativos

### Requirement: Estado explícito por fuente y tolerancia a fallas
El perfil SHALL registrar, por cada fuente genómica externa, uno de estos estados: `consultada` (devolvió al
menos una anotación), `sin_resultados` (respondió sin anotaciones para los genes consultados),
`no_disponible` (error de red, HTTP, timeout o circuit breaker abierto) o `no_consultada` (no había nada que
consultar). Un error de la fuente MUST NOT confundirse con ausencia de resultados, MUST NOT interrumpir el
pipeline y MUST NOT silenciarse: SHALL registrarse en stderr con el nombre de la fuente y el tipo de error,
sin datos clínicos.

#### Scenario: Fuente caída
- **WHEN** PharmGKB responde con error HTTP 503 al consultar `TTR`
- **THEN** la fuente queda en estado `no_disponible`, el perfil se entrega sin anotaciones y la Ronda 1
  continúa

#### Scenario: Gen sin anotaciones
- **WHEN** PharmGKB responde correctamente pero sin anotaciones para el gen consultado
- **THEN** la fuente queda en estado `sin_resultados`

#### Scenario: Circuit breaker abierto
- **WHEN** el circuit breaker de PharmGKB está abierto
- **THEN** no se realiza la solicitud y la fuente queda en estado `no_disponible`

### Requirement: Bloque de contexto genómico para el agente
El sistema SHALL traducir el perfil a un bloque de texto para el Agente 02 que declare el modo, los hallazgos
reportados, los genes mencionados (aclarando que la mención no implica alteración), los estudios genéticos
negativos, las anotaciones farmacogenómicas y el estado de cada fuente. En modo sin hallazgos genómicos el
bloque MUST afirmar explícitamente que el caso no reporta variantes ni hallazgos genéticos positivos. Una
fuente `no_disponible` MUST presentarse como no disponible y MUST NOT presentarse como "sin interacciones".

#### Scenario: Bloque en modo sin hallazgos
- **WHEN** se traduce el perfil del caso base
- **THEN** el bloque afirma que el caso no reporta variantes ni hallazgos genéticos positivos y no lista
  ningún gen

#### Scenario: Bloque con fuente no disponible
- **WHEN** se traduce un perfil cuya fuente PharmGKB quedó en `no_disponible`
- **THEN** el bloque indica que PharmGKB no estuvo disponible y no afirma que no existan interacciones
