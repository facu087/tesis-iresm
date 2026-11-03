"""
Revisión del reporte con un médico o el tutor de la tesis (tarjeta #60).

Los criterios de calidad de la tarjeta #59 (`calidad.py`) miden lo que se puede
comprobar sin un clínico: si los PMIDs existen, si corresponden al artículo
citado y si el nivel de evidencia declarado tiene respaldo. No pueden decir si
una hipótesis es pertinente para el paciente ni si el artículo citado la
sostiene: la verificación confirma que el PMID es ese artículo, no que el
artículo respalde lo que se afirma. Eso lo juzga el médico, con esta planilla.

El módulo arma la planilla desde un reporte (una fila por hipótesis, con las
preguntas en blanco) y tabula las respuestas: valida que cada una sea una de
las opciones, cuenta y cruza el juicio del médico con el estado automático de
la verificación. No usa red ni LLM.
"""

from __future__ import annotations

import io
import unicodedata
from collections.abc import Sequence

from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..api.schemas import StructuredReport
from .pdf_exporter import _hr, _par, _styles, _t


class Pregunta(BaseModel):
    """Pregunta cerrada de la planilla."""

    id: str
    enunciado: str
    opciones: tuple[str, ...]


PREGUNTAS_HIPOTESIS: tuple[Pregunta, ...] = (
    Pregunta(id="pertinente", enunciado="¿La hipótesis es pertinente para este caso?",
             opciones=("si", "parcial", "no")),
    Pregunta(id="cita_respalda", enunciado="¿El artículo citado respalda la hipótesis?",
             opciones=("si", "parcial", "no", "sin_cita")),
    Pregunta(id="nivel_razonable", enunciado="¿El nivel de evidencia asignado es razonable?",
             opciones=("si", "sobreestimado", "subestimado")),
    Pregunta(id="investigaria", enunciado="¿Investigaría esta hipótesis en este paciente?",
             opciones=("si", "no")),
)

# Columnas de texto libre por hipótesis: no se validan ni se cuentan.
TEXTO_LIBRE_HIPOTESIS: tuple[str, ...] = ("estudio_que_pediria", "observaciones")

PREGUNTAS_GLOBALES: tuple[Pregunta, ...] = (
    Pregunta(id="falta_hipotesis",
             enunciado="¿Falta alguna hipótesis que consideraría obvia para este caso? (cuál, en comentarios)",
             opciones=("si", "no")),
    Pregunta(id="utilidad",
             enunciado="¿Le serviría un reporte así como apoyo para orientar la investigación del caso?",
             opciones=("si", "quizas", "no")),
    Pregunta(id="claridad", enunciado="¿El reporte se entiende sin una explicación previa?",
             opciones=("si", "parcial", "no")),
)

COLUMNAS_PLANILLA: tuple[str, ...] = (
    ("rank", "hipotesis", "nivel", "estado", "citas")
    + tuple(p.id for p in PREGUNTAS_HIPOTESIS)
    + TEXTO_LIBRE_HIPOTESIS
)

_SIN_CITA = "sin_cita"

# Cómo se muestra cada opción en el PDF. La tabulación acepta las dos formas
# porque normaliza tildes, pero en el CSV se carga el identificador.
_ETIQUETAS = {"si": "sí", "sin_cita": "sin cita", "quizas": "quizás"}


# ── Planilla ───────────────────────────────────────────────────────────────────

def filas_planilla(reporte: StructuredReport) -> list[dict]:
    """
    Una fila por hipótesis del reporte, en su orden, con las respuestas vacías.

    Las citas muestran el título real de PubMed cuando la verificación lo trajo:
    el médico tiene que juzgar el artículo que es, no el que el agente dijo citar.
    """
    filas: list[dict] = []
    for h in reporte.hypotheses:
        citas = " | ".join(
            f"PMID {s.pmid}: {s.actual_title or s.title}" if s.pmid else s.title
            for s in h.sources
        )
        fila: dict = {
            "rank": h.rank,
            "hipotesis": h.text,
            "nivel": h.evidence_level,
            "estado": h.status,
            "citas": citas,
        }
        fila.update({col: "" for col in COLUMNAS_PLANILLA if col not in fila})
        filas.append(fila)
    return filas


def generar_planilla_pdf(reporte: StructuredReport) -> bytes:
    """Planilla imprimible: un bloque por hipótesis y las preguntas generales al final."""
    s = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="NEXUS - Planilla de revisión médica")
    historia = [
        _par("NEXUS - Planilla de revisión médica del reporte", s["title"]),
        _par(
            "Marque una opción por pregunta. NEXUS no emite diagnósticos: cada hipótesis es una "
            "línea de investigación propuesta para el médico responsable. Lo que se evalúa es si "
            "esa propuesta es útil y está bien fundamentada, no si acierta un diagnóstico.",
            s["subtitle"],
        ),
        Spacer(1, 6),
    ]
    for fila in filas_planilla(reporte):
        bloque = [
            _hr(),
            Paragraph(f"<b>Hipótesis {fila['rank']}</b> - nivel {_t(fila['nivel'])}, "
                      f"{_t(fila['estado'])}", s["section"]),
            Paragraph(_t(fila["hipotesis"]), s["body"]),
            Paragraph("<b>Citas:</b> " + (_t(fila["citas"]) or "ninguna"), s["small"]),
            Spacer(1, 4),
            _tabla_preguntas(PREGUNTAS_HIPOTESIS, s),
            Paragraph("Estudio que pediría: " + "_" * 70, s["celda"]),
            Paragraph("Observaciones: " + "_" * 75, s["celda"]),
        ]
        historia.append(KeepTogether(bloque))
    historia += [
        _hr(),
        Paragraph("Preguntas generales", s["section"]),
        _tabla_preguntas(PREGUNTAS_GLOBALES, s),
        Paragraph("Comentarios: " + "_" * 78, s["celda"]),
        Paragraph("_" * 92, s["celda"]),
    ]
    doc.build(historia)
    return buffer.getvalue()


def _tabla_preguntas(preguntas: Sequence[Pregunta], s: dict) -> Table:
    filas = [
        [Paragraph(_t(p.enunciado), s["celda"]),
         Paragraph("   ".join(f"[  ] {_t(_ETIQUETAS.get(o, o))}" for o in p.opciones), s["celda"])]
        for p in preguntas
    ]
    tabla = Table(filas, colWidths=[8.5 * cm, 8.5 * cm])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tabla


# ── Tabulación ─────────────────────────────────────────────────────────────────

class ResumenRevision(BaseModel):
    """Resultado de tabular una planilla respondida. No copia texto clínico."""

    hipotesis: int
    conteos: dict[str, dict[str, int]]
    sin_responder: dict[str, int]
    indicadores: dict[str, float | None]
    # Hipótesis que la verificación automática dio por respaldadas y cuya cita,
    # para el médico, no respalda la hipótesis.
    respaldo_verificado_sin_respaldo_clinico: list[int]
    globales: dict[str, str]
    problemas: list[str]
    completa: bool


def normalizar(respuesta: object) -> str:
    """
    Minúsculas, sin tildes ni espacios alrededor: "Sí " y "si" son la misma
    opción, y "sin cita" (como figura en el PDF) es "sin_cita".
    """
    texto = unicodedata.normalize("NFKD", str(respuesta or "").strip().lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return "_".join(texto.split())


def _proporcion(numerador: int, denominador: int) -> float | None:
    return numerador / denominador if denominador else None


def tabular(filas: Sequence[dict], globales: Sequence[dict]) -> ResumenRevision:
    """
    Valida y cuenta las respuestas de la planilla.

    Args:
        filas:    filas por hipótesis (columnas de `COLUMNAS_PLANILLA`).
        globales: filas `{"pregunta": id, "respuesta": valor}` de las preguntas generales.
    """
    conteos = {p.id: {o: 0 for o in p.opciones} for p in PREGUNTAS_HIPOTESIS}
    sin_responder = {p.id: 0 for p in PREGUNTAS_HIPOTESIS}
    problemas: list[str] = []
    cruce: list[int] = []

    for fila in filas:
        rank = fila.get("rank", "?")
        respuestas = {}
        for p in PREGUNTAS_HIPOTESIS:
            valor = normalizar(fila.get(p.id))
            if not valor:
                sin_responder[p.id] += 1
                problemas.append(f"Hipótesis {rank}, {p.id} sin responder.")
                continue
            if valor not in p.opciones:
                problemas.append(
                    f"Hipótesis {rank}, {p.id}: \"{fila.get(p.id, '').strip()}\" no es una opción "
                    f"({', '.join(p.opciones)})."
                )
                continue
            conteos[p.id][valor] += 1
            respuestas[p.id] = valor

        cita = respuestas.get("cita_respalda")
        tiene_citas = bool(str(fila.get("citas", "")).strip())
        if cita == _SIN_CITA and tiene_citas:
            problemas.append(f"Hipótesis {rank}: tiene citas pero se respondió sin_cita.")
        elif cita and cita != _SIN_CITA and not tiene_citas:
            problemas.append(f"Hipótesis {rank}: no tiene citas; la respuesta debe ser sin_cita.")
        if cita == "no" and fila.get("estado") == "respaldada":
            cruce.append(int(rank))

    respuestas_globales: dict[str, str] = {}
    por_id = {g.get("pregunta"): g.get("respuesta") for g in globales}
    for p in PREGUNTAS_GLOBALES:
        valor = normalizar(por_id.get(p.id))
        if not valor:
            problemas.append(f"Pregunta general {p.id} sin responder.")
        elif valor not in p.opciones:
            problemas.append(
                f"Pregunta general {p.id}: \"{str(por_id.get(p.id)).strip()}\" no es una opción "
                f"({', '.join(p.opciones)})."
            )
        else:
            respuestas_globales[p.id] = valor

    def _si(pregunta: str, excluir: tuple[str, ...] = ()) -> float | None:
        c = conteos[pregunta]
        total = sum(v for k, v in c.items() if k not in excluir)
        return _proporcion(c["si"], total)

    if not filas:
        problemas.append("La planilla no tiene hipótesis.")

    return ResumenRevision(
        hipotesis=len(filas),
        conteos=conteos,
        sin_responder=sin_responder,
        indicadores={
            "pertinencia": _si("pertinente"),
            "citas_que_respaldan": _si("cita_respalda", excluir=(_SIN_CITA,)),
            "nivel_razonable": _si("nivel_razonable"),
            "investigaria": _si("investigaria"),
        },
        respaldo_verificado_sin_respaldo_clinico=sorted(cruce),
        globales=respuestas_globales,
        problemas=problemas,
        completa=not problemas,
    )
