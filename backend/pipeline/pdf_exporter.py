"""
Exportador de reportes a PDF usando ReportLab.

En Sprint 4, el Agente 06 (Sintetizador) tomará el StructuredReport y enriquecerá
el contenido con síntesis LLM antes de llamar a generate_pdf().
El layout de este módulo no cambia.
"""

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..api.schemas import StructuredReport

# ── Paleta de colores ──────────────────────────────────────────────────────────
_NEXUS_BLUE = colors.HexColor("#1a3a5c")
_NEXUS_LIGHT = colors.HexColor("#e8f0f8")
_GREEN = colors.HexColor("#2e7d32")
_ORANGE = colors.HexColor("#e65100")
_GRAY = colors.HexColor("#757575")
_RED = colors.HexColor("#c62828")
_AMBER = colors.HexColor("#f57f17")

_EVIDENCE_COLORS = {"I": _GREEN, "II": _ORANGE, "III": _GRAY}
_PRIORITY_COLORS = {"HIGH": _RED, "MEDIUM": _AMBER, "LOW": _NEXUS_BLUE}

# Verificación bibliográfica (Agente 04)
_STATUS_COLORS = {"respaldada": _GREEN, "especulativa": _AMBER}
_STATUS_LABELS = {"respaldada": "RESPALDADA", "especulativa": "ESPECULATIVA"}

# Cómo se rotula cada veredicto de fuente en el PDF.
_VERDICT_LABELS = {
    "verificada": ("verificada", _GREEN),
    "discordante": ("NO CORRESPONDE", _RED),
    "inexistente": ("NO EXISTE EN PUBMED", _RED),
    "sin_pmid": ("sin PMID", _GRAY),
    "no_verificable": ("no verificable", _GRAY),
}


def _hex(color) -> str:
    """Devuelve el color en el formato #rrggbb que espera el markup de ReportLab."""
    return f"#{color.hexval()[2:]}"


# Las fuentes estándar de ReportLab usan WinAnsi y no tienen estos caracteres:
# los dibujan como una letra cualquiera. Los LLM devuelven el guion no separable
# a montones, y sin esta traducción "sensitivo‑motora" sale "sensitivonmotora".
_SUSTITUCIONES = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    " ": " ", " ": " ", " ": " ", " ": " ",
    "…": "...", "≤": "<=", "≥": ">=", "×": "x",
    "−": "-", "­": "",
})


def _limpiar(texto: str) -> str:
    """Reemplaza los caracteres que las fuentes estándar del PDF no saben dibujar."""
    return texto.translate(_SUSTITUCIONES)


def _par(texto: str, estilo) -> Paragraph:
    """Paragraph con el texto ya saneado para las fuentes del PDF."""
    return Paragraph(_limpiar(texto), estilo)


def _source_line(src, indice: str = "") -> str:
    """
    Arma la línea de una fuente con su veredicto de verificación.

    Cuando el PMID existe pero corresponde a otro artículo, se agrega el título
    real: es la prueba de que la cita no respalda lo que el agente afirma.
    """
    partes = [f"{indice}{src.title}"]
    if src.journal:
        partes.append(src.journal)
    if src.year:
        partes.append(str(src.year))
    if src.pmid:
        partes.append(f"PMID: {src.pmid}")
    linea = " · ".join(partes)

    etiqueta = _VERDICT_LABELS.get(src.verification_status or "")
    if etiqueta:
        texto, color = etiqueta
        linea += f" <font color='{_hex(color)}'><b>[{texto}]</b></font>"

    if src.actual_title:
        linea += (
            f"<br/><font color='{_hex(_RED)}'>En PubMed este PMID es:</font> "
            f"<i>{src.actual_title}</i>"
        )
    return linea

# Ancho útil de la página A4 con márgenes de 2 cm a cada lado
_PAGE_W = 17 * cm


# ── Estilos ────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "NTitle", parent=base["Normal"],
            fontSize=22, textColor=_NEXUS_BLUE,
            spaceAfter=4, alignment=TA_CENTER, fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "NSubtitle", parent=base["Normal"],
            fontSize=10, textColor=_GRAY,
            spaceAfter=6, alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "NSection", parent=base["Normal"],
            fontSize=13, textColor=_NEXUS_BLUE,
            spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "NBody", parent=base["Normal"],
            fontSize=9, leading=14, spaceAfter=4, alignment=TA_JUSTIFY,
        ),
        "small": ParagraphStyle(
            "NSmall", parent=base["Normal"],
            fontSize=8, leading=11, textColor=_GRAY,
        ),
        "cell": ParagraphStyle(
            "NCell", parent=base["Normal"],
            fontSize=8, leading=11,
        ),
        "disclaimer": ParagraphStyle(
            "NDisclaimer", parent=base["Normal"],
            fontSize=7, textColor=_GRAY, alignment=TA_CENTER,
        ),
    }


def _hr() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5, color=_NEXUS_BLUE, spaceAfter=6)


def _section(title: str, s: dict) -> list:
    return [Spacer(1, 0.3 * cm), _par(title, s["section"]), _hr()]


# ── Secciones del PDF ──────────────────────────────────────────────────────────

def _cover(report: StructuredReport, s: dict) -> list:
    elems = [Spacer(1, 2 * cm)]
    elems.append(_par("NEXUS", s["title"]))
    elems.append(_par("Sistema de Soporte Investigativo Clínico", s["subtitle"]))
    elems.append(Spacer(1, 0.4 * cm))

    date_str = report.metadata.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    elems.append(_par(f"Generado el {date_str}", s["subtitle"]))
    elems.append(_par(f"Versión {report.metadata.nexus_version}", s["subtitle"]))
    elems.append(Spacer(1, 1 * cm))

    v = report.verification
    stats = [
        ["Hipótesis identificadas", str(len(report.hypotheses))],
        ["Ensayos clínicos encontrados", str(len(report.clinical_trials))],
        ["Fuentes bibliográficas", str(len(report.bibliography))],
    ]
    if v and v.total_fuentes:
        stats.append(["Referencias verificadas en PubMed", f"{v.verificadas} de {v.total_fuentes}"])
        stats.append(["Hipótesis con respaldo verificable", str(v.hipotesis_respaldadas)])
    stats += [
        ["Rondas de debate", str(report.debate_summary.rounds_completed)],
        ["Tiempo de procesamiento", f"{report.metadata.processing_time_seconds:.1f} s"],
    ]
    t = Table(stats, colWidths=[10 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _NEXUS_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.8 * cm))

    # Aviso de verificación: si las referencias no resisten el contraste contra
    # PubMed, el lector tiene que enterarse en la portada, no en la bibliografía.
    if v and v.total_fuentes:
        sospechosas = v.discordantes + v.inexistentes
        if sospechosas:
            aviso = (
                f"<b>Advertencia de verificación bibliográfica:</b> {sospechosas} de "
                f"{v.total_fuentes} referencias citadas no se pudieron confirmar contra "
                f"PubMed"
            )
            if v.discordantes:
                aviso += f" ({v.discordantes} corresponden a otro artículo)"
            aviso += (
                f". {v.hipotesis_especulativas} de "
                f"{v.hipotesis_especulativas + v.hipotesis_respaldadas} hipótesis quedan "
                f"marcadas como especulativas y deben leerse como tales."
            )
            elems.append(_par(f"<font color='{_hex(_RED)}'>{aviso}</font>", s["disclaimer"]))
            elems.append(Spacer(1, 0.5 * cm))

    elems.append(_par(report.metadata.disclaimer, s["disclaimer"]))
    elems.append(PageBreak())
    return elems


def _case_summary(report: StructuredReport, s: dict) -> list:
    elems = _section("RESUMEN DEL CASO CLÍNICO", s)
    cs = report.case_summary

    rows = []
    if cs.patient_profile:
        rows.append(["Perfil del paciente", cs.patient_profile])
    if cs.chief_complaint:
        rows.append(["Motivo de consulta", cs.chief_complaint])
    if cs.disease_duration:
        rows.append(["Tiempo de evolución", cs.disease_duration])
    if cs.current_treatments:
        rows.append(["Tratamientos actuales", ", ".join(cs.current_treatments)])
    if cs.relevant_history:
        rows.append(["Antecedentes relevantes", ", ".join(cs.relevant_history)])
    if cs.procedures_done:
        rows.append(["Procedimientos realizados", ", ".join(cs.procedures_done)])

    if rows:
        t = Table(rows, colWidths=[5 * cm, 12 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_NEXUS_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.3 * cm))

    elems.append(_par("<b>Narrativa clínica:</b>", s["body"]))
    elems.append(_par(cs.narrative, s["body"]))
    return elems


def _hypotheses(report: StructuredReport, s: dict) -> list:
    elems = _section("HIPÓTESIS DE INVESTIGACIÓN", s)

    if not report.hypotheses:
        elems.append(_par("No se generaron hipótesis.", s["body"]))
        return elems

    for h in report.hypotheses:
        ev_color = _EVIDENCE_COLORS.get(h.evidence_level, _GRAY)
        pr_color = _PRIORITY_COLORS.get(h.priority, _NEXUS_BLUE)

        st_color = _STATUS_COLORS.get(h.status, _GRAY)
        st_label = _STATUS_LABELS.get(h.status, h.status.upper())

        # Fila de badges: rango | estado | evidencia | prioridad | agentes
        badge_row = [[
            _par(f"<b>#{h.rank}</b>", s["cell"]),
            _par(
                f"<font color='{_hex(st_color)}'><b>{st_label}</b></font>",
                s["cell"],
            ),
            _par(
                f"<font color='#{ev_color.hexval()[2:]}'>Evidencia {h.evidence_level}</font>",
                s["cell"],
            ),
            _par(
                f"<font color='#{pr_color.hexval()[2:]}'>{h.priority}</font>",
                s["cell"],
            ),
            _par(
                ", ".join(h.supporting_agents) if h.supporting_agents else "—",
                s["small"],
            ),
        ]]
        badge_t = Table(badge_row, colWidths=[1.2 * cm, 3.0 * cm, 3.0 * cm, 2.3 * cm, 7.5 * cm])
        badge_t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(badge_t)
        elems.append(_par(h.text, s["body"]))
        elems.append(_par(f"<i>Justificación:</i> {h.rationale}", s["small"]))

        if h.sources:
            elems.append(_par("<i>Fuentes:</i>", s["small"]))
            # Una fuente por línea: el veredicto y el título real no entran en
            # una lista separada por puntos.
            for src in h.sources[:3]:
                elems.append(_par(_source_line(src, "· "), s["small"]))

        elems.append(Spacer(1, 0.3 * cm))

    return elems


def _debate_summary(report: StructuredReport, s: dict) -> list:
    elems = _section("RESUMEN DEL DEBATE ADVERSARIAL", s)
    ds = report.debate_summary

    consensus = (
        "Sí — los agentes convergieron en las hipótesis principales."
        if ds.consensus_reached
        else "No — se detectaron divergencias significativas."
    )
    rows = [
        ["Rondas completadas", str(ds.rounds_completed)],
        ["Total de críticas generadas", str(ds.total_critiques)],
        ["Consenso alcanzado", consensus],
    ]
    t = Table(rows, colWidths=[6 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_NEXUS_LIGHT, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(t)

    if ds.divergences:
        elems.append(Spacer(1, 0.2 * cm))
        elems.append(_par("<b>Divergencias detectadas:</b>", s["body"]))
        for div in ds.divergences:
            elems.append(_par(f"• {div}", s["small"]))

    return elems


def _clinical_trials(report: StructuredReport, s: dict) -> list:
    elems = _section("ENSAYOS CLÍNICOS ACTIVOS RELEVANTES", s)

    if not report.clinical_trials:
        elems.append(_par(
            "No se encontraron ensayos clínicos activos relacionados.", s["body"]
        ))
        return elems

    for trial in report.clinical_trials:
        phase_str = f" | {trial.phase}" if trial.phase else ""
        elems.append(_par(
            f"<b>{trial.nct_id}{phase_str}</b> — {trial.title}", s["body"]
        ))
        details = []
        if trial.conditions:
            details.append(f"Condiciones: {', '.join(trial.conditions[:3])}")
        if trial.locations:
            details.append(f"Países: {', '.join(trial.locations[:4])}")
        if trial.min_age or trial.max_age:
            details.append(f"Rango etario: {trial.min_age or '?'} – {trial.max_age or '?'}")
        if trial.url:
            details.append(f"URL: {trial.url}")
        for detail in details:
            elems.append(_par(detail, s["small"]))
        elems.append(Spacer(1, 0.2 * cm))

    return elems


def _bibliography(report: StructuredReport, s: dict) -> list:
    elems = _section("BIBLIOGRAFÍA", s)

    if not report.bibliography:
        elems.append(_par("No se registraron fuentes bibliográficas.", s["body"]))
        return elems

    for i, src in enumerate(report.bibliography, 1):
        elems.append(_par(_source_line(src, f"{i}. "), s["small"]))
        elems.append(Spacer(1, 0.1 * cm))

    return elems


# ── Punto de entrada ───────────────────────────────────────────────────────────

def generate_pdf(report: StructuredReport) -> bytes:
    """
    Genera el reporte estructurado en formato PDF.

    Args:
        report: StructuredReport ensamblado por build_export().

    Returns:
        Bytes del PDF generado, listos para enviar como HTTP response o guardar a disco.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="NEXUS - Reporte de Investigación Clínica",
        author=f"NEXUS v{report.metadata.nexus_version}",
    )

    s = _styles()
    elements: list = []
    elements.extend(_cover(report, s))
    elements.extend(_case_summary(report, s))
    elements.extend(_hypotheses(report, s))
    elements.extend(_debate_summary(report, s))
    elements.extend(_clinical_trials(report, s))
    elements.extend(_bibliography(report, s))

    doc.build(elements)
    return buffer.getvalue()
