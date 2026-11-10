"""
Anonimización de texto clínico antes de que salga del sistema.

Por qué existe
--------------
`POST /api/analyze` manda el texto del paciente a varios servicios de terceros:
Groq (síntesis PICO, extracción de biomarcadores y los seis agentes), PubMed,
ClinicalTrials.gov, Orphanet y PharmGKB. Hasta ahora no había nada entre el
documento subido y esas APIs: `ClinicalCase.raw_text` llevaba el comentario
"(ya anonimizado)", que era un supuesto sobre quien cargaba el archivo, no un
control del sistema.

Esto implementa el principio que la documentación de Etapa 1 ya declaraba —
"los datos clínicos se procesan de forma anonimizada antes de enviarse a las
APIs externas"— y la regla de `CLAUDE.md`: "anonimizar antes de enviar a APIs
externas".

Qué detecta
-----------
Identificadores directos, con reglas deterministas y auditables:

- Documentos argentinos: DNI, LC, LE, CI, CUIL y CUIT.
- Números de historia clínica, afiliado, credencial de obra social y
  matrícula profesional (MP/MN). Siempre exigen un número: "HC: hipertensión"
  o "Afiliado PAMI" no son identificadores.
- Teléfonos (fijos y móviles, con o sin característica). Sin un marcador
  ("Tel:", "Cel:") no se aceptan números con espacios o puntos, ni seguidos de
  una unidad, ni rangos de años: son valores de laboratorio y fechas.
- Correos electrónicos.
- Fechas de calendario completas (numéricas y en palabras).
- Nombres propios **precedidos por un marcador explícito**: "Paciente:",
  "Sr.", "Dra.", "a cargo de", "Solicitante:", "Apellido y nombre:", etc.
  Admite "Apellido, Nombre" y nombres en mayúsculas, como los imprimen los
  laboratorios. Sin dos puntos ("Paciente Juan Pérez") y para familiares
  ("Esposa: María López", "Hijo de Juan Pérez") el criterio es más estricto:
  dos o más palabras con el mismo formato, ninguna de ellas un término clínico.
- Domicilios: el campo rotulado ("Domicilio:") completo; en prosa ("reside
  en") solo una calle con número de puerta, para no llevarse "zona rural con
  exposición a pesticidas".

Qué aprende del propio documento
--------------------------------
Los informes repiten el nombre sin rótulo en títulos y pies de página, y el
número de documento en otros campos. Lo que el documento ya declaró con un
marcador (cada palabra de un nombre, cada DNI) se enmascara en **todas** sus
apariciones. Es determinista y no usa un modelo: solo busca lo que encontró.
Busca los nombres únicamente con inicial mayúscula o todo en mayúsculas, nunca
en minúscula, y no propaga apellidos que además son términos médicos ("Wilson",
"Charcot"): prefiere dejar un apellido antes que destruir "enfermedad de Wilson".

Qué NO detecta, y por qué se dice
---------------------------------
Un nombre que **nunca** aparece con un marcador en el documento no se detecta.
Detectarlo exigiría reconocimiento de entidades nombradas, y una heurística de
"palabras capitalizadas" sobre texto clínico destruiría el contenido que el
sistema necesita: *Charcot-Marie-Tooth*, *Villa Carlos Paz*, *Guillain-Barré* y
los nombres de fármacos son todos secuencias capitalizadas.

Medido sobre estudios reales (22 PDF de una persona, un mismo sanatorio): de 167
identificadores presentes, la versión anterior dejaba pasar 85 y esta, 0. Es
una medición sobre los mismos formatos con los que se escribieron las reglas:
no demuestra cobertura sobre informes de otros centros.

Por eso esta capa es una **red de seguridad determinista, no una garantía de
desidentificación**. El criterio de diseño es no romper el texto clínico: ante
la duda, no se enmascara. Para una garantía más fuerte haría falta un modelo de
NER biomédico en español, evaluado con métricas propias; eso excede el alcance
de la tesis y queda documentado como trabajo futuro.

Qué devuelve
------------
`anonimizar()` devuelve el texto enmascarado y un `InformeAnonimizacion` con
**conteos por categoría, nunca los valores encontrados**: el informe viaja a
logs y al reporte, y volcar ahí lo que se acaba de enmascarar anularía el
propósito.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Pattern

# Etiquetas con las que se reemplaza cada categoría. Se mantienen legibles para
# que el médico que lea el reporte entienda que ahí había un dato, y para que
# los agentes no interpreten el hueco como información faltante del caso.
ETIQUETAS = {
    "documento": "[DOCUMENTO]",
    "historia_clinica": "[HISTORIA CLINICA]",
    "matricula": "[MATRICULA]",
    "telefono": "[TELEFONO]",
    "email": "[EMAIL]",
    "fecha": "[FECHA]",
    "nombre": "[NOMBRE]",
    "domicilio": "[DOMICILIO]",
}

_MESES = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    "septiembre|setiembre|octubre|noviembre|diciembre"
)

# Partícula inicial de apellidos compuestos ("de la Fuente", "del Valle").
# Pueden encadenarse ("de la Fuente", "van der ..."): una sola no alcanza.
_PARTICULA = r"(?:(?:de|del|la|las|los|van|von|di|da)[ \t]+)*"
# Etiquetas de campo que los informes imprimen al lado del nombre. Los PDF de dos
# columnas las intercalan ("PACIENTE: PÉREZ JUAN FEC. NAC.: ..."), y sin esta
# exclusión el nombre se tragaba "FEC" y la etiqueta siguiente dejaba de verse.
_CAMPOS = (
    r"autor|fec|fecha|nac|sexo|edad|dni|documento|tipo|servicio|solicitante|"
    r"paciente|cobertura|protocolo|domicilio|tel|tel[ée]fono"
)
# Una palabra de nombre propio: capitalizada ("Pérez") o toda en mayúsculas
# ("PÉREZ", como imprimen los laboratorios), con guiones internos. Distingue
# mayúsculas de minúsculas a propósito, aunque el patrón compile con re.I: antes
# "Paciente: Juan Pérez presenta debilidad" se enmascaraba entero y se llevaba
# puesto texto clínico, que es justo lo que el sistema necesita leer.
_PALABRA_CAP = (
    rf"(?!(?i:{_CAMPOS})\b)"
    r"(?-i:(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})"
    r"(?:-(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,}))*)"
)
# Entre palabras solo espacios: con \s+ un nombre al final de línea se llevaba el
# primer encabezado de la línea siguiente ("Pérez\nDiagnóstico").
_NOMBRE = rf"{_PARTICULA}{_PALABRA_CAP}(?:[ \t]+{_PARTICULA}{_PALABRA_CAP}){{0,3}}"
# "Apellido, Nombre": el formato de los informes de laboratorio y de cardiología.
_NOMBRE_COMPUESTO = (
    rf"{_NOMBRE}(?:[ \t]*,[ \t]*{_PALABRA_CAP}(?:[ \t]+{_PALABRA_CAP}){{0,2}})?"
)

# Nombre sin un marcador fuerte ("Paciente Juan Pérez", "Esposa: María López"):
# dos a cuatro palabras con mayúscula. Además pasa por _es_nombre_estricto(),
# que exige el mismo formato en todas y que ninguna sea un término clínico. Sin
# eso, "Paciente Portador de HLA-B*15:02" se llevaba el alelo que usa el Agente 02.
_NOMBRE_ESTRICTO = (
    rf"{_PALABRA_CAP}(?:[ \t]+{_PARTICULA}{_PALABRA_CAP}){{1,3}}"
)
# Obras sociales que los informes imprimen delante del número de afiliado.
_OBRAS_SOCIALES = (
    r"PAMI|IOSFA|IOMA|APROSS|OSDE|OSECAC|OSPRERA|OSPE|SANCOR|GALENO|MEDIF[EÉ]|"
    r"OMINT|SWISS[ \t]+MEDICAL|ACCORD"
)
# Unidades que siguen a un valor de laboratorio: un número seguido de una de
# estas no es un teléfono ("12500000 /ul", "126130145 mg/dl").
_UNIDAD = (
    r"[ \t]*(?:/|%|mg|mcg|[µu]g|ng|pg|g/|ml|dl|mm|cm|kg|mmol|meq|ui|u/|x[ \t]?10|c[ée]l)"
)

# Rótulos con los que un número de documento aparece en los informes.
_MARCA_DOCUMENTO = (
    r"(?:DNI|D\.N\.I\.?|LC|L\.C\.?|LE|L\.E\.?|CI|C\.I\.?|documento|doc\.?|"
    r"identificaci[óo]n(?:\s+del\s+paciente)?|id)"
)

# Orden importante: lo más específico primero. Un CUIL contiene un DNI, y una
# fecha numérica puede parecerse a un teléfono corto.
# Cada regla es (categoría, patrón) o (categoría, patrón, validador). El
# validador propio reemplaza al de la categoría (_VALIDADORES).
_Validador = Callable[[str, bool], bool]
_REGLAS: list[tuple[str, Pattern[str]] | tuple[str, Pattern[str], _Validador]] = [
    # ── Correo electrónico ────────────────────────────────────────────────
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),

    # ── CUIL / CUIT: 11 dígitos con guiones ───────────────────────────────
    ("documento", re.compile(r"\b(?:CUIL|CUIT)?\s*:?\s*\d{2}-\d{7,8}-\d\b", re.I)),

    # ── Documentos argentinos con etiqueta ────────────────────────────────
    ("documento", re.compile(
        rf"\b{_MARCA_DOCUMENTO}\s*"
        r"(?:n[º°o]\.?|nro\.?|number)?\s*:?\s*\d{1,3}(?:[.\s]\d{3}){1,2}\b",
        re.I,
    )),
    ("documento", re.compile(
        rf"\b{_MARCA_DOCUMENTO}\s*"
        r"(?:n[º°o]\.?|nro\.?)?\s*:?\s*\d{7,8}\b",
        re.I,
    )),

    # ── Historia clínica ──────────────────────────────────────────────────
    # El valor tiene que llevar al menos un dígito: "HC: hipertensión
    # controlada" es texto clínico, no un número de historia.
    ("historia_clinica", re.compile(
        r"\b(?:historia\s+cl[íi]nica|h\.?\s?c\.?|legajo|"
        r"matr[íi]cula\s+del\s+paciente)\s*"
        r"(?:n[º°o]\.?|nro\.?)?\s*:?\s*(?=[\w./-]*\d)[\w./-]{4,20}\b",
        re.I,
    )),

    # ── Afiliado y credencial de obra social ──────────────────────────────
    # "Credencial PAMI 150123456789/00", "IOSFA nro 1234567", "N° de afiliado:
    # 12345678". Exige el número: "Afiliado PAMI" solo no dice nada.
    # Comparte etiqueta con la historia clínica, como antes de este cambio.
    ("historia_clinica", re.compile(
        rf"\b(?:n[º°o][ \t]*de[ \t]*afiliado|afiliado|credencial|carnet|"
        rf"obra[ \t]+social|{_OBRAS_SOCIALES})"
        rf"(?:[ \t]+(?:{_OBRAS_SOCIALES}))?"
        r"[ \t]*(?:n[º°o]\.?|nro\.?|n[úu]mero)?[ \t]*:?[ \t]*\d[\d./-]{3,24}\d",
        re.I,
    ), lambda c, _m: _minimo_digitos(c, 5)),

    # ── Matrícula profesional ─────────────────────────────────────────────
    # "M.P. 34567", "MN 123456", "Matrícula provincial 1234". Las siglas
    # distinguen mayúsculas a propósito; el número lleva al menos 4 dígitos.
    ("matricula", re.compile(
        r"(?:\b(?i:matr[íi]cula)(?:[ \t]+(?i:provincial|nacional|profesional))?"
        r"|\bM\.?[ \t]?[PN]\.?)(?![A-Za-z])"
        r"[ \t]*(?i:n[º°o]\.?|nro\.?)?[ \t]*:?[ \t]*(\d[\d.]{2,9}\d)",
    ), lambda c, _m: _minimo_digitos(c, 4)),

    # ── Teléfonos ─────────────────────────────────────────────────────────
    # Dos reglas: una anclada a un marcador ("Tel:"), que puede ser laxa porque
    # el marcador ya dice que lo que sigue es un teléfono; y otra suelta, que
    # exige suficientes dígitos como para no confundirse con un valor de
    # laboratorio. Ambas se validan después con _es_telefono_plausible().
    # Un teléfono nunca cruza un salto de línea: con \s en la clase, una columna de
    # valores de laboratorio ("0.94-1.52" y el número del renglón siguiente) se
    # tomaba por un teléfono largo y se borraba el rango de referencia.
    ("telefono", re.compile(
        r"\b(?:tel|tel[ée]fono|cel|celular|contacto|whatsapp)[ \t]*\.?[ \t]*:?[ \t]*"
        r"(\+?\d[\d \t().-]{5,20}\d)",
        re.I,
    )),
    # Sin marcador, solo números sin espacios ni puntos (o con "+" o una
    # característica entre paréntesis), y nunca seguidos de una unidad: así
    # quedan afuera "126 130 145 128 mg/dl" y "12.500.000 /ul".
    ("telefono", re.compile(
        r"(?<![\d/.,-])"
        r"(?:\+\d[\d \t().-]{7,18}\d|\(\d{2,5}\)[ \t]?\d[\d-]{5,10}\d|\d[\d-]{6,16}\d)"
        rf"(?![\d/.,-])(?!{_UNIDAD})"
    )),

    # ── Fechas numéricas: 12/03/1984, 12-03-84 ────────────────────────────
    ("fecha", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    # ── Fechas en palabras: 12 de marzo de 1984 ───────────────────────────
    ("fecha", re.compile(rf"\b\d{{1,2}}\s+de\s+(?:{_MESES})\s+de\s+\d{{4}}\b", re.I)),

    # ── Domicilio ─────────────────────────────────────────────────────────
    # El campo rotulado ("Domicilio:") se enmascara hasta el fin de la línea:
    # cortar en el primer punto dejaría la calle a la vista, porque las
    # direcciones están llenas de abreviaturas ("Av.", "Gral.", "Dto.").
    ("domicilio", re.compile(
        r"\b(?:domicilio|direcci[óo]n)[ \t]*:[ \t]*([^\n;]{5,120})",
        re.I,
    )),
    # En prosa ("reside en", "vive en") se tapa hasta el último número de la
    # línea (o "s/n"), con el piso y el departamento que lo siguen. Sin número no
    # hay dirección: una ciudad o un barrio solos no identifican a nadie. La
    # versión anterior tapaba hasta el fin de la línea y se llevaba "zona rural
    # con exposición a pesticidas"; _es_domicilio_plausible() descarta los
    # tramos con palabras de texto clínico ("con", "desde", "trabaja").
    ("domicilio", re.compile(
        r"\b(?:vive|reside|domiciliad[oa]|domicilio(?:[ \t]+actual)?|direcci[óo]n)"
        r"(?:[ \t]+en)?[ \t]*:?[ \t]*"
        r"([^\n;]{0,80}(?:\d(?:[°º]|to|vo|ro|do|er|mo|no)?(?:[ \t]*(?-i:[A-Z])\b)?"
        r"|\bs/n\b))",
        re.I,
    ), lambda c, _m: _es_domicilio_plausible(c)),

    # ── Nombres con marcador explícito ────────────────────────────────────
    # El título va primero: "Dra. María Gutiérrez" tiene que resolverse antes
    # que "Derivado por …", o el marcador genérico se queda con "la Dra" y el
    # nombre real sobrevive.
    ("nombre", re.compile(
        rf"\b(?:dr|dra|doctor|doctora|lic|prof)\.?\s+({_NOMBRE_COMPUESTO})\b", re.I,
    )),
    # "Sr. Juan Pérez", "Paciente: Juan Pérez", "Apellido y nombre: Pérez, Juan".
    # Un tratamiento ("Sr.") alcanza como marcador; un rótulo ("Paciente")
    # necesita los dos puntos para usar el criterio laxo.
    ("nombre", re.compile(
        rf"\b(?:sr|sra|srta|don|do[ñn]a)\.?\s*:?\s+({_NOMBRE_COMPUESTO})\b",
        re.I,
    )),
    ("nombre", re.compile(
        rf"\b(?:paciente|nombre\s+y\s+apellido|apellido\s+y\s+nombre|nombre|apellido)"
        rf"\.?[ \t]*:\s*({_NOMBRE_COMPUESTO})\b",
        re.I,
    )),
    # Sin dos puntos ("Paciente Juan Pérez"): criterio estricto. Con el laxo,
    # "Paciente Tratado con Carbamazepina" perdía "Tratado".
    ("nombre", re.compile(
        rf"\b(?:paciente|nombre\s+y\s+apellido|apellido\s+y\s+nombre|nombre|apellido)"
        rf"[ \t]+({_NOMBRE_ESTRICTO})\b",
        re.I,
    ), lambda c, _m: _es_nombre_estricto(c)),
    # Familiares, siempre con el criterio estricto. Detrás de "Padre:" o
    # "Hermana:" va un antecedente ("Padre: Diabetes Mellitus"), y las
    # enfermedades no caben en una lista: para padres, hijos y hermanos solo
    # cuenta la filiación ("Hijo de Juan Pérez"). Cónyuge y tutor con dos puntos
    # ("Esposa: María López") sí son una persona.
    ("nombre", re.compile(
        rf"\b(?:espos[oa]|c[óo]nyuge|pareja|tutor|tutora|acompañante)"
        rf"(?:[ \t]+legal)?[ \t]*:[ \t]*({_NOMBRE_ESTRICTO})\b",
        re.I,
    ), lambda c, _m: _es_nombre_estricto(c)),
    ("nombre", re.compile(
        rf"\b(?:hij[oa]|herman[oa]|espos[oa]|c[óo]nyuge)[ \t]+de[ \t]+({_NOMBRE_ESTRICTO})\b",
        re.I,
    ), lambda c, _m: _es_nombre_estricto(c)),
    # Marcadores de derivación y de autoría, admitiendo artículo y título
    # intermedios. "Solicitante" y "autor" son los rótulos de los laboratorios.
    ("nombre", re.compile(
        rf"\b(?:a\s+cargo\s+de|derivad[oa]\s+(?:a|por)|firma(?:\s+y\s+sello)?|sello|"
        rf"atendid[oa]\s+por|"
        rf"solicitante|autor|m[eé]dico\s+(?:solicitante|derivante|tratante))"
        rf"\s*:?\s+(?:(?:el|la|los|las)\s+)?"
        rf"(?:(?:dr|dra|doctor|doctora|lic|prof)\.?\s+)?({_NOMBRE_COMPUESTO})\b",
        re.I,
    )),
    # Nombre partido en dos líneas. Los PDF de dos columnas imprimen
    # "PACIENTE: PÉREZ JUAN   FEC. NAC.: 06/01/1971" y mandan el último nombre a
    # la línea de abajo, sola y en mayúsculas. Exige una segunda etiqueta con ":"
    # en la línea del paciente (señal de que el nombre quedó cortado); sin eso,
    # un encabezado en mayúsculas ("DIAGNÓSTICO") se tomaría por nombre.
    ("nombre", re.compile(
        r"\bpaciente[ \t]*:[^\n:]*:[^\n]*\n[ \t]*"
        r"((?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:[ \t]+[A-ZÁÉÍÓÚÑ]{2,})?))[ \t]*(?=\n|$)",
        re.I,
    )),
    # "Apellido, Nombre" pegado a un número al final de la línea: así queda el
    # nombre cuando el membrete de la clínica comparte renglón con el paciente
    # ("MOLINO DE TORRES 5301 Pérez, Juan").
    ("nombre", re.compile(
        rf"\b\d{{3,5}}[ \t]+(?=[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ]{{3}})"
        rf"({_PALABRA_CAP}[ \t]*,[ \t]*{_PALABRA_CAP}"
        rf"(?:[ \t]+{_PALABRA_CAP}){{0,2}})[ \t]*$",
        re.M,
    )),
]

# Palabras que nunca son un nombre propio aunque sigan a un marcador. Evitan
# que "paciente masculino" o "paciente femenina" se coman la descripción
# clínica, que es justamente lo que el sistema necesita leer.
_NO_SON_NOMBRES = frozenset("""
masculino femenina femenino masculina varon varón mujer hombre adulto adulta
mayor menor joven anciano anciana nino niño nina niña lactante neonato
sin con que de del la el los las un una presenta refiere consulta derivado
derivada ingresa acude internado internada ambulatorio ambulatoria
dr dra doctor doctora lic prof sr sra srta don dona doña
diagnostico diagnóstico resultados resultado estudio informe motivo antecedentes
laboratorio hemograma observaciones conclusion conclusión
pre post quirurgico quirúrgico apellido nombre
portador portadora tratado tratada diabetico diabético diabetica diabética
hipertenso hipertensa obeso obesa tabaquista alcoholista asintomatico
asintomático asintomatica asintomática sano sana vivo viva fallecido fallecida
enfermedad sindrome síndrome cancer cáncer tumor neoplasia antecedente
""".split())

# Apellidos y nombres que además son términos médicos o topónimos. Se usan solo en
# la propagación: si el paciente se apellida "Wilson", el apellido sobrevive en el
# resto del documento antes que destruir "enfermedad de Wilson", que el sistema
# necesita leer. Mismo criterio de la capa: ante la duda, no se enmascara.
_PROTEGIDOS = frozenset("""
charcot marie tooth guillain barre barré parkinson alzheimer wilson huntington
crohn addison cushing graves hashimoto raynaud sjogren sjögren behcet behçet
kawasaki down turner klinefelter fabry gaucher pompe duchenne becker
villa carlos paz cordoba córdoba argentina
""".split())

# Partículas de apellidos compuestos: no son un dato por sí solas.
_PARTICULAS = frozenset("de del la las los van von di da y e".split())


@dataclass
class InformeAnonimizacion:
    """
    Qué se enmascaró, sin decir qué decía.

    Lleva conteos por categoría a propósito: este informe va a los logs y al
    reporte, y volcar ahí los valores encontrados anularía la anonimización.
    """

    reemplazos: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.reemplazos.values())

    @property
    def hubo_hallazgos(self) -> bool:
        return self.total > 0

    def resumen(self) -> str:
        """Línea legible para logs y para el reporte."""
        if not self.hubo_hallazgos:
            return "Anonimización: no se detectaron identificadores directos."
        detalle = ", ".join(
            f"{cantidad} {categoria.replace('_', ' ')}"
            for categoria, cantidad in sorted(self.reemplazos.items())
        )
        return f"Anonimización: {self.total} identificadores enmascarados ({detalle})."


def _es_nombre_plausible(candidato: str, _con_marcador: bool = False) -> bool:
    """
    Descarta descripciones clínicas que siguen a un marcador.

    Se mira **solo la primera palabra**, no todas: "de", "la" y "del" están en
    la lista porque no arrancan un nombre, pero sí aparecen dentro de apellidos
    compuestos. Mirando todas las palabras, "Ana María de la Fuente" quedaba
    descartada y el apellido sobrevivía.
    """
    palabras = candidato.split()
    if not palabras:
        return False
    return palabras[0].lower().strip(",.;:") not in _NO_SON_NOMBRES


def _es_telefono_plausible(candidato: str, con_marcador: bool = False) -> bool:
    """
    Cuántos dígitos hacen falta para creer que es un teléfono.

    Con un marcador explícito delante ("Tel:", "Celular:") alcanza con 6: el
    marcador ya dice qué es, y hay fijos de 7 dígitos sin característica. Sin
    marcador el piso sube a 8, para no comerse recuentos de laboratorio ni
    dosis. El techo de 15 evita tragarse una tira de mediciones separadas por
    espacios como si fuera un número solo.
    """
    # "Evolución 2019-2023" es un rango de años, no un teléfono.
    if re.fullmatch(r"(?:19|20)\d\d-(?:19|20)\d\d", candidato.strip()):
        return False
    digitos = sum(c.isdigit() for c in candidato)
    minimo = 6 if con_marcador else 8
    return minimo <= digitos <= 15


def _es_nombre_estricto(candidato: str) -> bool:
    """
    Nombre sin marcador fuerte: todas las palabras con el mismo formato
    (capitalizadas o todas en mayúsculas) y ninguna un término clínico.

    "Portador de HLA" mezcla formatos y "Enfermedad Coronaria" arranca con un
    término clínico: ninguno de los dos es un nombre. "Juan Pérez" y
    "PÉREZ JUAN" sí.
    """
    palabras = [
        p for p in candidato.split() if p.lower() not in _PARTICULAS
    ]
    if len(palabras) < 2:
        return False
    if any(p.lower().strip(",.;:") in _NO_SON_NOMBRES | _PROTEGIDOS for p in palabras):
        return False
    todas_mayusculas = [p.isupper() for p in palabras]
    return all(todas_mayusculas) or not any(todas_mayusculas)


# Palabras que no aparecen en una dirección y sí en texto clínico.
_NO_SON_DOMICILIO = frozenset("""
con desde hace durante años año meses mes semanas días trabaja trabajó trabajando
expuesto expuesta exposición por para que sin presenta refiere
""".split())


def _es_domicilio_plausible(candidato: str) -> bool:
    """
    Un tramo en prosa es una dirección si no tiene palabras de texto clínico:
    "Av. Colón 1234" sí, "zona rural con exposición a pesticidas desde 2015" no.
    """
    palabras = re.findall(r"[a-záéíóúñ]+", candidato.lower())
    return not any(p in _NO_SON_DOMICILIO for p in palabras)


def _minimo_digitos(candidato: str, minimo: int) -> bool:
    """Un número de afiliado o de matrícula tiene al menos `minimo` dígitos."""
    return sum(c.isdigit() for c in candidato) >= minimo


_VALIDADORES = {
    "nombre": _es_nombre_plausible,
    "telefono": _es_telefono_plausible,
}


def _tokens_de_nombre(candidato: str) -> set[str]:
    """
    Las palabras de un nombre ya detectado, aptas para buscarlas en el resto del
    documento. Solo cuentan las que empiezan en mayúscula (lo que el patrón ya
    exige) y tienen al menos 3 letras; se excluyen partículas, palabras que nunca
    son un nombre y términos médicos que coinciden con un apellido.
    """
    palabras = re.split(r"[\s,\-]+", candidato)
    tokens = set()
    for palabra in palabras:
        palabra = palabra.strip(".,;:()")
        minuscula = palabra.lower()
        if (
            len(palabra) >= 3
            and palabra[0].isupper()
            and minuscula not in _PARTICULAS
            and minuscula not in _NO_SON_NOMBRES
            and minuscula not in _PROTEGIDOS
        ):
            tokens.add(palabra)
    return tokens


def _propagar(texto: str, nombres: set[str], documentos: set[str],
              informe: "InformeAnonimizacion") -> str:
    """
    Enmascara en todo el documento lo que ya se detectó en un lugar con marcador.

    Los informes repiten el nombre sin rótulo en títulos y pies de página
    ("Estudio: Juan Pérez - 12/03/2026", "Pérez , Juan - Página 3"), y el número
    de documento en otros campos. Si el documento ya dijo con un marcador que
    "Pérez" es el paciente, cada aparición de "Pérez" lo es. Es determinista y no
    necesita un modelo: lo que enmascara lo aprendió del propio documento.

    Los nombres se buscan solo escritos con inicial mayúscula o todo en
    mayúsculas, nunca en minúscula: un apellido como "Blanco" no debe llevarse
    puesto "tono blanco" en una descripción clínica.
    """
    if nombres:
        variantes = {v for n in nombres for v in (n.capitalize(), n.upper())}
        patron = re.compile(
            r"\b(?:" + "|".join(re.escape(v) for v in sorted(variantes, key=len, reverse=True))
            + r")\b"
        )
        texto, cantidad = patron.subn(ETIQUETAS["nombre"], texto)
        if cantidad:
            informe.reemplazos["nombre"] = informe.reemplazos.get("nombre", 0) + cantidad
    for digitos in documentos:
        patron = re.compile(r"(?<![\d.])" + r"\.?".join(digitos) + r"(?!\d)")
        texto, cantidad = patron.subn(ETIQUETAS["documento"], texto)
        if cantidad:
            informe.reemplazos["documento"] = informe.reemplazos.get("documento", 0) + cantidad
    return texto


def anonimizar(texto: str) -> tuple[str, InformeAnonimizacion]:
    """
    Enmascara identificadores directos en un texto clínico.

    Args:
        texto: Texto clínico ya normalizado.

    Returns:
        (texto_anonimizado, informe). El informe trae conteos por categoría,
        nunca los valores encontrados.
    """
    informe = InformeAnonimizacion()
    if not texto:
        return texto, informe

    resultado = texto
    # Lo que se detectó con marcador, para buscarlo después sin marcador.
    nombres_vistos: set[str] = set()
    documentos_vistos: set[str] = set()
    for regla in _REGLAS:
        categoria, patron = regla[0], regla[1]
        etiqueta = ETIQUETAS[categoria]
        validador = regla[2] if len(regla) == 3 else _VALIDADORES.get(categoria)

        def _reemplazar(match: re.Match[str]) -> str:
            # Cuando la regla captura un grupo, se enmascara SOLO ese grupo y se
            # conserva el marcador ("Paciente:", "Domicilio:"): le dice al agente
            # qué clase de dato había ahí, sin revelarlo.
            completo = match.group(0)
            candidato = match.group(1) if match.groups() else completo

            # Que la regla capture un grupo significa que venía anclada a un
            # marcador explícito; eso habilita criterios más laxos.
            con_marcador = bool(match.groups())
            if validador and not validador(candidato, con_marcador):
                return completo

            informe.reemplazos[categoria] = informe.reemplazos.get(categoria, 0) + 1
            if categoria == "nombre":
                nombres_vistos.update(_tokens_de_nombre(candidato))
            elif categoria == "documento":
                digitos = "".join(c for c in candidato if c.isdigit())
                if 7 <= len(digitos) <= 8:
                    documentos_vistos.add(digitos)
            if match.groups():
                inicio, fin = match.span(1)
                desplazamiento = match.start()
                return (completo[: inicio - desplazamiento]
                        + etiqueta
                        + completo[fin - desplazamiento:])
            return etiqueta

        resultado = patron.sub(_reemplazar, resultado)

    resultado = _propagar(resultado, nombres_vistos, documentos_vistos, informe)
    return resultado, informe
