"""
Demo de verificación — Verificación bibliográfica de PMIDs (Agente 04).

Muestra el problema que resuelve el módulo: los agentes citan PMIDs que existen
en PubMed pero corresponden a otro artículo. Un chequeo de existencia los da por
buenos; solo comparar el título real los detecta.

A diferencia de demo_pubmed.py, este script SÍ consulta PubMed de verdad: la
evidencia pierde sentido si los títulos reales están simulados.

Entrada por defecto: las referencias que el pipeline produjo realmente para el
caso de la tesis (neuropatía axonal, 42 años). También acepta el JSON de una
corrida propia:

    python scripts/demo_verificacion.py
    python scripts/demo_verificacion.py output/mi_reporte.json

Artefactos generados en output/demo_verificacion/:
    1. veredictos.txt → citado vs. real, con el estado de cada fuente
    2. resumen.json   → conteo por estado y etiquetado de las hipótesis
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# La consola de Windows usa cp1252 y no puede imprimir los caracteres de las
# cajas: sin esto el script termina en UnicodeEncodeError al mostrar el reporte.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Report
from backend.pipeline.verification import SourceStatus, verify_report_sources

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_verificacion"

# Referencias tal como las emitió el pipeline en una corrida real del caso de la
# tesis. Se dejan fijas para que la demo sea reproducible: el pipeline no es
# determinista y cada corrida cita PMIDs distintos.
_CITAS_DEL_PIPELINE = [
    ("22439958", "Metformin-associated vitamin B12 deficiency: a systematic review", "Diabetes Care", 2012),
    ("25043758", "Peripheral neuropathy in hypothyroidism: a systematic review", "Thyroid", 2014),
    ("27433186", "Alcoholic neuropathy: clinical features and pathogenesis", "Journal of Neurology", 2016),
    ("28512367", "Drug-induced peripheral neuropathy: a systematic review", "Drug Safety", 2017),
    ("28598765", "Paraneoplastic peripheral neuropathies: clinical features and diagnosis", "Brain", 2017),
    ("30627458", "Chronic inflammatory demyelinating polyradiculoneuropathy: diagnosis", "Lancet Neurology", 2019),
    ("31712345", "Guidelines for the management of diabetic peripheral neuropathy", "Diabetes Care", 2019),
    ("33194912", "Guidelines for the diagnosis and treatment of vitamin B12 deficiency", "Blood Reviews", 2020),
    ("33243738", "American Academy of Neurology guideline update: CIDP", "Neurology", 2020),
    (None, "Guidelines for the management of hypothyroidism (American Thyroid Association)", None, None),
]

_HIPOTESIS_DEMO = "Deficiencia de vitamina B12 secundaria al uso crónico de metformina."

_ETIQUETA = {
    SourceStatus.VERIFICADA: "✓ verificada",
    SourceStatus.DISCORDANTE: "✗ DISCORDANTE",
    SourceStatus.INEXISTENTE: "✗ inexistente",
    SourceStatus.SIN_PMID: "· sin PMID",
    SourceStatus.NO_VERIFICABLE: "? no verificable",
}


def _cargar_fuentes(ruta: Path | None) -> list[Source]:
    """Toma las fuentes del reporte indicado, o las de la corrida de referencia."""
    if ruta is None:
        return [
            Source(pmid=pmid, title=titulo, journal=revista, year=anio)
            for pmid, titulo, revista, anio in _CITAS_DEL_PIPELINE
        ]

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    fuentes: list[Source] = []
    vistos: set[str] = set()
    for hipotesis in datos.get("hypotheses", []):
        for s in hipotesis.get("sources", []):
            clave = s.get("pmid") or s.get("title", "")
            if clave and clave not in vistos:
                vistos.add(clave)
                fuentes.append(
                    Source(
                        pmid=s.get("pmid"),
                        title=s.get("title", ""),
                        journal=s.get("journal"),
                        year=s.get("year"),
                    )
                )
    return fuentes


def main() -> None:
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if ruta is not None and not ruta.exists():
        print(f"No existe el archivo: {ruta}")
        sys.exit(1)

    fuentes = _cargar_fuentes(ruta)
    origen = str(ruta) if ruta else "corrida de referencia del pipeline (caso de la tesis)"

    print(_SEP)
    print("  VERIFICACIÓN BIBLIOGRÁFICA — Agente 04 (Árbitro Verificador)")
    print(_SEP)
    print(f"  Origen de las citas : {origen}")
    print(f"  Fuentes a verificar : {len(fuentes)}")
    print(f"  PMIDs declarados    : {sum(1 for f in fuentes if f.pmid)}")
    print()
    print("  Consultando PubMed (una sola llamada batch a esummary)…")
    print()

    report = Report(
        case_summary="Neuropatía axonal sensitivomotora, paciente de 42 años.",
        hypotheses=[
            Hypothesis(
                text=_HIPOTESIS_DEMO,
                priority=Priority.HIGH,
                evidence_level=EvidenceLevel.I,
                rationale="Hipótesis de la corrida real, con sus referencias.",
                sources=fuentes,
            )
        ],
    )
    veredictos = asyncio.run(verify_report_sources(report))

    if not veredictos:
        print("  No se obtuvo ningún veredicto: el reporte no tenía fuentes.")
        return

    print(_SEP)
    print("  CITADO POR EL AGENTE  vs.  LO QUE EL PMID ES EN REALIDAD")
    print(_SEP)

    lineas: list[str] = []
    for veredicto in sorted(veredictos.values(), key=lambda v: v.pmid or "zzz"):
        cabecera = f"[{_ETIQUETA[veredicto.status]}]  PMID {veredicto.pmid or '—'}"
        bloque = [cabecera, f"    citado : {veredicto.claimed_title}"]
        if veredicto.actual_title:
            bloque.append(f"    REAL   : {veredicto.actual_title}")
            bloque.append(f"    coincidencia de título: {veredicto.match_score}")
        lineas.extend(bloque)
        lineas.append("")

    texto = "\n".join(lineas)
    print(texto)

    conteo = {estado: 0 for estado in SourceStatus}
    for veredicto in veredictos.values():
        conteo[veredicto.status] += 1
    validas = conteo[SourceStatus.VERIFICADA]

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    veredictos_txt = _OUT_DIR / "veredictos.txt"
    resumen_json = _OUT_DIR / "resumen.json"

    veredictos_txt.write_text(
        f"VERIFICACIÓN BIBLIOGRÁFICA — Agente 04\nOrigen: {origen}\n\n{texto}",
        encoding="utf-8",
    )
    resumen = {
        "origen": origen,
        "total_fuentes": len(veredictos),
        "verificadas": validas,
        "discordantes": conteo[SourceStatus.DISCORDANTE],
        "inexistentes": conteo[SourceStatus.INEXISTENTE],
        "sin_pmid": conteo[SourceStatus.SIN_PMID],
        "no_verificables": conteo[SourceStatus.NO_VERIFICABLE],
        "estado_hipotesis": "respaldada" if validas else "especulativa",
    }
    resumen_json.write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Fuentes verificadas   : {validas}")
    print(f"  DISCORDANTES          : {conteo[SourceStatus.DISCORDANTE]}  (el PMID existe pero es otro artículo)")
    print(f"  Inexistentes          : {conteo[SourceStatus.INEXISTENTE]}")
    print(f"  Sin PMID              : {conteo[SourceStatus.SIN_PMID]}")
    print(f"  No verificables       : {conteo[SourceStatus.NO_VERIFICABLE]}  (fallo de red: no invalida la cita)")
    print()
    print(f"  La hipótesis queda como: {resumen['estado_hipotesis'].upper()}")
    print("  Las especulativas NO se descartan: se muestran etiquetadas para el médico.")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Veredicto por fuente → {veredictos_txt}")
    print(f"    • Resumen del conteo   → {resumen_json}")
    print(_SEP)


if __name__ == "__main__":
    main()
