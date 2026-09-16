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

from ..api.schemas import RankedHypothesis, StructuredReport
from ..models.trial import ClinicalTrial, TrialSearchSummary
from .trial_matching import has_preferred_location

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

# Verificación bibliográfica (Agente 04) y clasificación EBM (pipeline/evidence.py)
_SKY = colors.HexColor("#0277bd")
_STATUS_COLORS = {"respaldada": _GREEN, "pendiente": _SKY, "especulativa": _AMBER}
_STATUS_LABELS = {
    "respaldada": "RESPALDADA",
    "pendiente": "PENDIENTE",
    "especulativa": "ESPECULATIVA",
}

# Grupos de hipótesis, en el mismo orden en que las ordena el backend.
_STATUS_GROUPS = [
    ("respaldada", "Hipótesis respaldadas",
     "Al menos una referencia confirmada contra PubMed."),
    ("pendiente", "Pendientes de verificación",
     "PubMed no respondió: el nivel queda en III hasta poder confirmar las fuentes."),
    ("especulativa", "Hipótesis especulativas",
     "Ninguna referencia resistió la verificación. Se muestran, no se descartan."),
]

# Navegación de ensayos (Agente 05): etiqueta orientativa por ensayo.
_COMPATIBILITY_LABELS = {
    "alta": ("COMPATIBILIDAD ALTA", _GREEN),
    "media": ("COMPATIBILIDAD MEDIA", _AMBER),
    "baja": ("COMPATIBILIDAD BAJA", _GRAY),
    "sin_evaluar": ("SIN EVALUAR", _GRAY),
}

# Aclaración fija: la misma que muestra el frontend.
_TRIAL_DISCLAIMER = (
    "La compatibilidad es orientativa: la elegibilidad la determina el equipo "
    "investigador de cada ensayo."
)

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

    # Tipos de publicación de PubMed: son los que fijan el tope de evidencia.
    if src.verified and src.publication_types:
        linea += f" <font color='{_hex(_GRAY)}'>(tipo: {', '.join(src.publication_types)})</font>"

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
    if v and v.hipotesis_pendientes:
        stats.append(["Hipótesis pendientes de verificación", str(v.hipotesis_pendientes)])
    if v and v.hipotesis_topeadas:
        stats.append(["Hipótesis con nivel de evidencia topeado", str(v.hipotesis_topeadas)])
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
        total_hipotesis = (
            v.hipotesis_respaldadas + v.hipotesis_pendientes + v.hipotesis_especulativas
        )
        if sospechosas or v.hipotesis_pendientes:
            aviso = "<b>Advertencia de verificación bibliográfica:</b>"
            if sospechosas:
                aviso += (
                    f" {sospechosas} de {v.total_fuentes} referencias citadas no se "
                    f"pudieron confirmar contra PubMed"
                )
                if v.discordantes:
                    aviso += f" ({v.discordantes} corresponden a otro artículo)"
                aviso += (
                    f". {v.hipotesis_especulativas} de {total_hipotesis} hipótesis quedan "
                    f"marcadas como especulativas y deben leerse como tales."
                )
            if v.hipotesis_pendientes:
                aviso += (
                    f" {v.hipotesis_pendientes} de {total_hipotesis} hipótesis quedan "
                    f"pendientes: PubMed no respondió y su nivel queda en III."
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


def _group_status(status: str) -> str:
    """Estado de agrupación: uno desconocido (reporte viejo) va con las especulativas."""
    conocidos = {estado for estado, _, _ in _STATUS_GROUPS}
    return status if status in conocidos else "especulativa"


def _hypotheses(report: StructuredReport, s: dict) -> list:
    elems = _section("HIPÓTESIS DE INVESTIGACIÓN", s)

    if not report.hypotheses:
        elems.append(_par("No se generaron hipótesis.", s["body"]))
        return elems

    for estado, titulo, descripcion in _STATUS_GROUPS:
        grupo = [h for h in report.hypotheses if _group_status(h.status) == estado]
        if not grupo:
            continue
        color = _STATUS_COLORS[estado]
        elems.append(Spacer(1, 0.15 * cm))
        elems.append(_par(
            f"<font color='{_hex(color)}'><b>{titulo.upper()} ({len(grupo)})</b></font>",
            s["body"],
        ))
        elems.append(_par(descripcion, s["small"]))
        elems.append(Spacer(1, 0.15 * cm))
        for h in grupo:
            elems.extend(_hypothesis_block(h, s))

    return elems


def _hypothesis_block(h: RankedHypothesis, s: dict) -> list:
    """Bloque de una hipótesis: badges, texto, justificación, nivel y fuentes."""
    elems: list = []
    ev_color = _EVIDENCE_COLORS.get(h.evidence_level, _GRAY)
    pr_color = _PRIORITY_COLORS.get(h.priority, _NEXUS_BLUE)

    st_color = _STATUS_COLORS.get(h.status, _GRAY)
    st_label = _STATUS_LABELS.get(h.status, h.status.upper())

    topeada = bool(h.declared_evidence_level) and h.declared_evidence_level != h.evidence_level
    evidencia = f"Evidencia {h.evidence_level}"
    if topeada:
        evidencia += f" (declarado {h.declared_evidence_level})"

    # Fila de badges: rango | estado | evidencia | prioridad | agentes
    badge_row = [[
        _par(f"<b>#{h.rank}</b>", s["cell"]),
        _par(
            f"<font color='{_hex(st_color)}'><b>{st_label}</b></font>",
            s["cell"],
        ),
        _par(
            f"<font color='#{ev_color.hexval()[2:]}'>{evidencia}</font>",
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
    badge_t = Table(badge_row, colWidths=[1.2 * cm, 2.8 * cm, 3.8 * cm, 2.0 * cm, 7.2 * cm])
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
    if h.evidence_note:
        color = _ORANGE if topeada else _GRAY
        elems.append(_par(
            f"<font color='{_hex(color)}'><i>Nivel de evidencia:</i> {h.evidence_note}</font>",
            s["small"],
        ))

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


def _search_status_notice(report: StructuredReport) -> str:
    """Aviso de que alguna API de la navegación no respondió del todo."""
    busqueda = report.trial_search
    if busqueda is None:
        return ""

    avisos: list[str] = []
    if busqueda.estado_clinicaltrials == "no_disponible":
        avisos.append("ClinicalTrials.gov no se pudo consultar")
    elif busqueda.estado_clinicaltrials == "parcial":
        avisos.append("algunas consultas a ClinicalTrials.gov fallaron")
    if busqueda.estado_orphanet == "no_disponible":
        avisos.append("Orphanet no se pudo consultar")
    elif busqueda.estado_orphanet == "parcial":
        avisos.append("algunas consultas a Orphanet fallaron")
    if busqueda.evaluacion == "fallback":
        avisos.append("la evaluación de compatibilidad no se pudo completar")
    if not avisos:
        return ""
    return f"Estado de la búsqueda: {'; '.join(avisos)}."


def _trial_block(
    trial: ClinicalTrial, busqueda: TrialSearchSummary | None, s: dict
) -> list:
    """Bloque de un ensayo. Sin `busqueda` imprime igual que antes del Agente 05."""
    elems: list = []
    phase_str = f" | {trial.phase}" if trial.phase else ""
    elems.append(_par(f"<b>{trial.nct_id}{phase_str}</b> — {trial.title}", s["body"]))

    if busqueda is not None:
        etiquetas: list[str] = []
        texto, color = _COMPATIBILITY_LABELS.get(
            trial.compatibility, _COMPATIBILITY_LABELS["sin_evaluar"]
        )
        etiquetas.append(f"<font color='{_hex(color)}'><b>{texto}</b></font>")
        if trial.status == "NOT_YET_RECRUITING":
            # Advertencia, no badge de calidad: el ensayo todavía no abrió.
            etiquetas.append(f"<font color='{_hex(_ORANGE)}'><b>AÚN NO RECLUTA</b></font>")
        if has_preferred_location(trial):
            etiquetas.append(f"<font color='{_hex(_NEXUS_BLUE)}'><b>SEDE EN ARGENTINA</b></font>")
        elems.append(_par(" · ".join(etiquetas), s["small"]))

        if trial.compatibility_rationale:
            elems.append(_par(f"<i>Fundamento:</i> {trial.compatibility_rationale}", s["small"]))
        if trial.criteria_to_verify:
            elems.append(_par("<i>Criterios a verificar:</i>", s["small"]))
            for criterio in trial.criteria_to_verify:
                elems.append(_par(f"· {criterio}", s["small"]))
        if trial.related_hypotheses:
            elems.append(_par(
                f"<i>Hipótesis relacionadas:</i> {'; '.join(trial.related_hypotheses)}",
                s["small"],
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


def _rare_diseases(report: StructuredReport, s: dict) -> list:
    """
    Apartado de Orphanet: hipótesis que corresponden a una enfermedad rara.

    Nunca es un diagnóstico del paciente: son hipótesis de investigación que
    coinciden con una entidad catalogada.
    """
    if not report.rare_diseases:
        return []

    elems: list = [Spacer(1, 0.3 * cm)]
    elems.append(_par("<b>Enfermedades raras relacionadas (Orphanet)</b>", s["body"]))
    elems.append(_par(
        "Hipótesis de investigación que corresponden a una enfermedad rara catalogada. "
        "No son diagnósticos del paciente.",
        s["small"],
    ))
    for marca in report.rare_diseases:
        elems.append(_par(
            f"· <b>ORPHA:{marca.orpha_code}</b> — {marca.name} · {marca.url}", s["small"]
        ))
        elems.append(_par(f"  Hipótesis: {marca.hypothesis}", s["small"]))
    return elems


def _clinical_trials(report: StructuredReport, s: dict) -> list:
    elems = _section("ENSAYOS CLÍNICOS ACTIVOS RELEVANTES", s)
    # `trial_search` nulo = reporte anterior al Agente 05: se imprime como antes.
    busqueda = report.trial_search

    aviso = _search_status_notice(report)
    if aviso:
        elems.append(_par(f"<font color='{_hex(_RED)}'>{aviso}</font>", s["small"]))

    if not report.clinical_trials:
        if busqueda is not None and busqueda.estado_clinicaltrials == "no_disponible":
            elems.append(_par(
                "No se pudo consultar ClinicalTrials.gov: esto no significa que no "
                "existan ensayos relacionados.",
                s["body"],
            ))
        else:
            elems.append(_par(
                "No se encontraron ensayos clínicos activos relacionados.", s["body"]
            ))
        elems.extend(_rare_diseases(report, s))
        return elems

    if busqueda is not None:
        elems.append(_par(_TRIAL_DISCLAIMER, s["small"]))
        elems.append(Spacer(1, 0.2 * cm))

    for trial in report.clinical_trials:
        elems.extend(_trial_block(trial, busqueda, s))

    elems.extend(_rare_diseases(report, s))
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
