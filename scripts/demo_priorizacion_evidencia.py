"""
Demo de priorización — Hipótesis priorizadas por nivel de evidencia EBM (I, II, III).

Muestra cómo backend/pipeline/evidence.py acota el nivel que autodeclara cada
agente con los tipos de publicación que PubMed indexa para sus fuentes
verificadas, asigna el estado (respaldada / pendiente / especulativa) y ordena
el reporte: estado → nivel efectivo → prioridad → fuentes verificadas.

Modos:
    python3 scripts/demo_priorizacion_evidencia.py            # sin red (por defecto)
    python3 scripts/demo_priorizacion_evidencia.py --pubmed   # verifica PMIDs reales

El modo por defecto usa veredictos fijos que cubren cada regla (reproducible,
sin red). El modo --pubmed consulta PubMed de verdad (una sola llamada batch) y
deja registrados los tipos de publicación reales.

Caso: neuropatía axonal sensitivomotora, paciente masculino de 42 años.

Artefactos en output/demo_priorizacion_evidencia/:
    1. priorizacion.txt → entrada (nivel declarado, fuentes, veredicto, tipos) → salida
    2. reporte.json     → StructuredReport completo
    3. reporte.pdf      → PDF exportado, con las hipótesis agrupadas por estado
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.api.schemas import StructuredReport
from backend.models.case import ClinicalCase
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Report
from backend.pipeline.pdf_exporter import generate_pdf
from backend.pipeline.report_builder import build_export
from backend.pipeline.verification import (
    SourceStatus,
    SourceVerification,
    source_key,
    verify_report_sources,
)

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_priorizacion_evidencia"
_CASO = "Neuropatía axonal sensitivomotora, paciente masculino de 42 años."

I, II, III = EvidenceLevel.I, EvidenceLevel.II, EvidenceLevel.III
V = SourceStatus

# ── Modo por defecto: veredictos fijos que cubren cada regla ──────────────────
# (texto, prioridad, nivel declarado, [(pmid, título citado, veredicto, tipos)])
_CASOS_SIN_RED = [
    ("Déficit de vitamina B12 inducido por metformina.", Priority.HIGH, I,
     [("30615306", "Associations between metformin use and vitamin B12 levels, anemia, and neuropathy",
       V.VERIFICADA, ["Journal Article", "Meta-Analysis"])]),
    ("Asociación bidireccional entre neuropatía periférica y déficit de B12.", Priority.HIGH, I,
     [("37344286", "Bidirectional association between diabetic peripheral neuropathy and vitamin B12 deficiency",
       V.VERIFICADA, ["Journal Article", "Observational Study"])]),
    ("Polineuropatía desmielinizante inflamatoria crónica (CIDP) de curso atípico.", Priority.MEDIUM, I,
     [("34327760", "EAN/PNS guideline on diagnosis and treatment of chronic inflammatory demyelinating polyradiculoneuropathy",
       V.VERIFICADA, ["Journal Article", "Practice Guideline"])]),
    ("Degeneración combinada subaguda con compromiso periférico.", Priority.LOW, II,
     [("20134380", "Metformin-induced vitamin B12 deficiency presenting as a peripheral neuropathy",
       V.VERIFICADA, ["Case Reports", "Journal Article"])]),
    ("Neuropatía asociada a déficit de B12 según revisión sistemática previa a 2019 (ejemplo sintético).",
     Priority.MEDIUM, I,
     [("90000001", "Vitamin B12 deficiency and neuropathy: a systematic review",
       V.VERIFICADA, ["Journal Article", "Review"])]),
    ("Neuropatía por fármaco citado en un ensayo luego retractado (ejemplo sintético).", Priority.HIGH, I,
     [("90000002", "Randomized trial of a neurotoxic drug in axonal neuropathy",
       V.VERIFICADA, ["Randomized Controlled Trial", "Retracted Publication"])]),
    ("Déficit de B12 por metformina según revisión sistemática citada por el agente.", Priority.HIGH, I,
     [("22439958", "Metformin-associated vitamin B12 deficiency: a systematic review", V.DISCORDANTE, [])]),
    ("Neuropatía autoinmune con anticuerpos antinodales.", Priority.MEDIUM, II,
     [("33000001", "Nodal and paranodal antibodies in chronic inflammatory neuropathy", V.NO_VERIFICABLE, [])]),
    ("Amiloidosis hereditaria por transtiretina (TTR).", Priority.HIGH, III, []),
]

# Título real de PubMed para el PMID discordante (tomado de demo_verificacion.py).
_TITULO_REAL = {"22439958": "Breeding replacement gilts for organic pig herds."}

# ── Modo --pubmed: PMIDs reales elegidos por tipo de publicación ──────────────
# (texto, prioridad, nivel declarado, [(pmid, título citado)])
_CASOS_PUBMED = [
    ("Déficit de vitamina B12 inducido por metformina.", Priority.HIGH, I,
     [("30615306", "Associations between metformin use and vitamin B12 levels, anemia, and neuropathy in patients with diabetes")]),
    ("Suplementación con B12 en neuropatía diabética como prueba terapéutica.", Priority.MEDIUM, I,
     [("33513879", "Vitamin B12 Supplementation in Diabetic Neuropathy: A 1-Year, Randomized, Double-Blind, Placebo-Controlled Trial")]),
    ("Asociación bidireccional entre neuropatía periférica y déficit de B12.", Priority.HIGH, I,
     [("37344286", "Bidirectional association between diabetic peripheral neuropathy and vitamin B12 deficiency: Two longitudinal")]),
    ("Polineuropatía desmielinizante inflamatoria crónica (CIDP) de curso atípico.", Priority.MEDIUM, I,
     [("34327760", "European Academy of Neurology/Peripheral Nerve Society guideline on diagnosis and treatment of chronic inflammatory demyelinating polyradiculoneuropathy")]),
    ("Degeneración combinada subaguda con compromiso periférico.", Priority.LOW, II,
     [("20134380", "Metformin-induced vitamin B12 deficiency presenting as a peripheral neuropathy")]),
    ("Déficit de B12 por metformina según revisión sistemática citada por el agente.", Priority.HIGH, I,
     [("22439958", "Metformin-associated vitamin B12 deficiency: a systematic review")]),
    ("Amiloidosis hereditaria por transtiretina (TTR).", Priority.HIGH, III, []),
]


def _hipotesis(texto: str, prioridad: Priority, nivel: EvidenceLevel, fuentes: list[Source]) -> Hypothesis:
    return Hypothesis(
        text=texto, priority=prioridad, evidence_level=nivel,
        rationale="Hipótesis de demostración del caso base.", sources=fuentes,
    )


def _escenario_sin_red() -> tuple[Report, dict[str, SourceVerification]]:
    """Arma el reporte y los veredictos fijos del modo por defecto."""
    hipotesis: list[Hypothesis] = []
    veredictos: dict[str, SourceVerification] = {}
    for texto, prioridad, nivel, fuentes in _CASOS_SIN_RED:
        sources = []
        for pmid, titulo, estado, tipos in fuentes:
            source = Source(pmid=pmid, title=titulo)
            sources.append(source)
            veredictos[source_key(source)] = SourceVerification(
                pmid=pmid, status=estado, claimed_title=titulo,
                actual_title=_TITULO_REAL.get(pmid, "") if estado is V.DISCORDANTE else "",
                publication_types=tipos,
            )
        hipotesis.append(_hipotesis(texto, prioridad, nivel, sources))
    return Report(case_summary=_CASO, hypotheses=hipotesis), veredictos


def _escenario_pubmed() -> tuple[Report, dict[str, SourceVerification]]:
    """Arma el reporte con PMIDs reales y lo verifica contra PubMed (una llamada batch)."""
    hipotesis = [
        _hipotesis(texto, prioridad, nivel, [Source(pmid=p, title=t) for p, t in fuentes])
        for texto, prioridad, nivel, fuentes in _CASOS_PUBMED
    ]
    report = Report(case_summary=_CASO, hypotheses=hipotesis)
    return report, asyncio.run(verify_report_sources(report))


def _render(export: StructuredReport, modo: str) -> str:
    """Tabla de entrada → salida por hipótesis, en el orden final del reporte."""
    lineas = [
        _SEP,
        "  PRIORIZACIÓN POR NIVEL DE EVIDENCIA EBM — tarjeta #54",
        _SEP,
        f"  Caso : {_CASO}",
        f"  Modo : {modo}",
        "  Orden: estado → nivel efectivo → prioridad → fuentes verificadas",
        "",
    ]
    for h in export.hypotheses:
        cambio = (
            f"declarado {h.declared_evidence_level} → efectivo {h.evidence_level}"
            if h.declared_evidence_level != h.evidence_level
            else f"declarado {h.declared_evidence_level} = efectivo {h.evidence_level}"
        )
        lineas.append(f"#{h.rank} [{h.status.upper():12}] {cambio:28} prioridad {h.priority}")
        lineas.append(f"    {h.text}")
        if not h.sources:
            lineas.append("    fuentes : (ninguna)")
        for s in h.sources:
            tipos = ", ".join(s.publication_types) if s.publication_types else "—"
            lineas.append(f"    PMID {s.pmid or '—':9} veredicto: {s.verification_status or 'sin veredicto':15} tipos: {tipos}")
        lineas.append(f"    nota    : {h.evidence_note}")
        lineas.append("")

    v = export.verification
    lineas += [
        _SEP,
        "  RESULTADO",
        _SEP,
        f"  Respaldadas  : {v.hipotesis_respaldadas}",
        f"  Pendientes   : {v.hipotesis_pendientes}  (PubMed no respondió: nivel III, no se invalidan)",
        f"  Especulativas: {v.hipotesis_especulativas}  (se muestran, no se descartan)",
        f"  Topeadas     : {v.hipotesis_topeadas}  (nivel efectivo por debajo del declarado)",
        "",
        "  Limitación documentada: una revisión sistemática previa a 2019 indexada solo",
        "  como 'Review' topea en III (el tipo 'Systematic Review' existe desde 2019).",
    ]
    return "\n".join(lineas)


def main() -> None:
    usar_pubmed = "--pubmed" in sys.argv[1:]
    if usar_pubmed:
        print("  Consultando PubMed (una sola llamada batch a esummary)…")
        report, veredictos = _escenario_pubmed()
        modo = "--pubmed (veredictos y tipos reales de PubMed)"
    else:
        report, veredictos = _escenario_sin_red()
        modo = "sin red (veredictos fijos que cubren cada regla)"

    export = build_export(
        case=ClinicalCase(raw_text=_CASO), report=report, trials=[],
        processing_time=0.0, verifications=veredictos,
    )
    texto = _render(export, modo)
    print(texto)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt = _OUT_DIR / "priorizacion.txt"
    js = _OUT_DIR / "reporte.json"
    pdf = _OUT_DIR / "reporte.pdf"
    txt.write_text(texto + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(export.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pdf.write_bytes(generate_pdf(export))

    print(_SEP)
    print("  ARTEFACTOS GENERADOS (adjuntar a la tarjeta de Trello):")
    print(f"    • Entrada → salida      → {txt}")
    print(f"    • StructuredReport JSON → {js}")
    print(f"    • PDF agrupado por estado → {pdf}")
    print(_SEP)


if __name__ == "__main__":
    main()
