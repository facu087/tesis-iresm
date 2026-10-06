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
- Números de historia clínica, afiliado y obra social.
- Teléfonos (fijos y móviles, con o sin característica).
- Correos electrónicos.
- Fechas de calendario completas (numéricas y en palabras).
- Nombres propios **precedidos por un marcador explícito**: "Paciente:",
  "Sr.", "Dra.", "a cargo de", etc.
- Domicilios introducidos por un marcador.

Qué NO detecta, y por qué se dice
---------------------------------
Un nombre suelto en medio de una frase, sin marcador que lo anuncie, no se
detecta. Detectarlo exigiría reconocimiento de entidades nombradas, y una
heurística de "palabras capitalizadas" sobre texto clínico destruiría el
contenido que el sistema necesita: *Charcot-Marie-Tooth*, *Villa Carlos Paz*,
*Guillain-Barré* y los nombres de fármacos son todos secuencias capitalizadas.

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
from typing import Pattern

# Etiquetas con las que se reemplaza cada categoría. Se mantienen legibles para
# que el médico que lea el reporte entienda que ahí había un dato, y para que
# los agentes no interpreten el hueco como información faltante del caso.
ETIQUETAS = {
    "documento": "[DOCUMENTO]",
    "historia_clinica": "[HISTORIA CLINICA]",
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
_PARTICULA = r"(?:de |del |la |las |los |van |von |di |da )?"
# Una palabra capitalizada, admitiendo tildes y guiones internos.
_PALABRA_CAP = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:-[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*"
_NOMBRE = rf"{_PARTICULA}{_PALABRA_CAP}(?:\s+{_PARTICULA}{_PALABRA_CAP}){{0,3}}"

# Orden importante: lo más específico primero. Un CUIL contiene un DNI, y una
# fecha numérica puede parecerse a un teléfono corto.
_REGLAS: list[tuple[str, Pattern[str]]] = [
    # ── Correo electrónico ────────────────────────────────────────────────
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),

    # ── CUIL / CUIT: 11 dígitos con guiones ───────────────────────────────
    ("documento", re.compile(r"\b(?:CUIL|CUIT)?\s*:?\s*\d{2}-\d{7,8}-\d\b", re.I)),

    # ── Documentos argentinos con etiqueta ────────────────────────────────
    ("documento", re.compile(
        r"\b(?:DNI|D\.N\.I\.?|LC|L\.C\.?|LE|L\.E\.?|CI|C\.I\.?|documento)\s*"
        r"(?:n[º°o]\.?|nro\.?|number)?\s*:?\s*\d{1,3}(?:[.\s]\d{3}){1,2}\b",
        re.I,
    )),
    ("documento", re.compile(
        r"\b(?:DNI|D\.N\.I\.?|LC|L\.C\.?|LE|L\.E\.?|CI|C\.I\.?|documento)\s*"
        r"(?:n[º°o]\.?|nro\.?)?\s*:?\s*\d{7,8}\b",
        re.I,
    )),

    # ── Historia clínica, afiliado, obra social ───────────────────────────
    ("historia_clinica", re.compile(
        r"\b(?:historia\s+cl[íi]nica|h\.?\s?c\.?|n[º°o]\s*de\s*afiliado|"
        r"afiliado|legajo|matr[íi]cula\s+del\s+paciente)\s*"
        r"(?:n[º°o]\.?|nro\.?)?\s*:?\s*[\w./-]{4,20}\b",
        re.I,
    )),

    # ── Teléfonos ─────────────────────────────────────────────────────────
    # Dos reglas: una anclada a un marcador ("Tel:"), que puede ser laxa porque
    # el marcador ya dice que lo que sigue es un teléfono; y otra suelta, que
    # exige suficientes dígitos como para no confundirse con un valor de
    # laboratorio. Ambas se validan después con _es_telefono_plausible().
    ("telefono", re.compile(
        r"\b(?:tel|tel[ée]fono|cel|celular|contacto|whatsapp)\s*\.?\s*:?\s*"
        r"(\+?\d[\d\s().-]{5,20}\d)",
        re.I,
    )),
    ("telefono", re.compile(r"(?<![\d/-])\+?\d[\d\s().-]{7,18}\d(?![\d/-])")),

    # ── Fechas numéricas: 12/03/1984, 12-03-84 ────────────────────────────
    ("fecha", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    # ── Fechas en palabras: 12 de marzo de 1984 ───────────────────────────
    ("fecha", re.compile(rf"\b\d{{1,2}}\s+de\s+(?:{_MESES})\s+de\s+\d{{4}}\b", re.I)),

    # ── Domicilio anunciado por marcador ──────────────────────────────────
    # Se enmascara hasta el fin de la línea, a propósito. Cortar en el primer
    # punto dejaría la calle a la vista, porque las direcciones están llenas de
    # abreviaturas ("Av.", "Gral.", "Dto."). El costo es que, si alguien escribe
    # texto clínico en la misma línea del domicilio, también se enmascara: se
    # prefiere perder algo de contexto antes que publicar una dirección.
    ("domicilio", re.compile(
        r"\b(?:domicilio|direcci[óo]n|vive\s+en|reside\s+en)\s*:?\s*([^\n;]{5,120})",
        re.I,
    )),

    # ── Nombres con marcador explícito ────────────────────────────────────
    # El título va primero: "Dra. María Gutiérrez" tiene que resolverse antes
    # que "Derivado por …", o el marcador genérico se queda con "la Dra" y el
    # nombre real sobrevive.
    ("nombre", re.compile(
        rf"\b(?:dr|dra|doctor|doctora|lic|prof)\.?\s+({_NOMBRE})\b", re.I,
    )),
    # "Paciente: Juan Pérez", "Sr. Juan Pérez".
    ("nombre", re.compile(
        rf"\b(?:paciente|sr|sra|srta|don|do[ñn]a|nombre\s+y\s+apellido|"
        rf"nombre|apellido)\.?\s*:?\s+({_NOMBRE})\b",
        re.I,
    )),
    # Marcadores de derivación, admitiendo artículo y título intermedios.
    ("nombre", re.compile(
        rf"\b(?:a\s+cargo\s+de|derivad[oa]\s+(?:a|por)|firma|atendid[oa]\s+por)"
        rf"\s*:?\s+(?:(?:el|la|los|las)\s+)?"
        rf"(?:(?:dr|dra|doctor|doctora|lic|prof)\.?\s+)?({_NOMBRE})\b",
        re.I,
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
""".split())


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
    digitos = sum(c.isdigit() for c in candidato)
    minimo = 6 if con_marcador else 8
    return minimo <= digitos <= 15


_VALIDADORES = {
    "nombre": _es_nombre_plausible,
    "telefono": _es_telefono_plausible,
}


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
    for categoria, patron in _REGLAS:
        etiqueta = ETIQUETAS[categoria]

        def _reemplazar(match: re.Match[str]) -> str:
            # Cuando la regla captura un grupo, se enmascara SOLO ese grupo y se
            # conserva el marcador ("Paciente:", "Domicilio:"): le dice al agente
            # qué clase de dato había ahí, sin revelarlo.
            completo = match.group(0)
            candidato = match.group(1) if match.groups() else completo

            # Que la regla capture un grupo significa que venía anclada a un
            # marcador explícito; eso habilita criterios más laxos.
            con_marcador = bool(match.groups())
            validador = _VALIDADORES.get(categoria)
            if validador and not validador(candidato, con_marcador):
                return completo

            informe.reemplazos[categoria] = informe.reemplazos.get(categoria, 0) + 1
            if match.groups():
                inicio, fin = match.span(1)
                desplazamiento = match.start()
                return (completo[: inicio - desplazamiento]
                        + etiqueta
                        + completo[fin - desplazamiento:])
            return etiqueta

        resultado = patron.sub(_reemplazar, resultado)

    return resultado, informe
