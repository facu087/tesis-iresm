"""
Material para la revisión del reporte con un médico o el tutor (tarjeta #60).

Dos pasos, con la sesión en el medio (ver docs/revision-medica.md):

    python3 scripts/revision_medica.py preparar output/medicion_costos/reporte.json
    python3 scripts/revision_medica.py tabular output/revision_medica/reporte

`preparar` lee un reporte guardado y genera, en output/revision_medica/<nombre>/
(o en --salida):
    reporte.pdf    → el reporte, tal como lo exporta NEXUS
    planilla.pdf   → la planilla imprimible, un bloque por hipótesis
    planilla.csv   → la misma planilla para cargar las respuestas
    generales.csv  → las preguntas generales del reporte

`tabular` lee planilla.csv y generales.csv ya respondidos (con ',' o ';', como
los guarda LibreOffice o Excel en español), valida cada respuesta contra sus
opciones y guarda resumen.json y resumen.txt en la misma carpeta. El resumen no
copia texto clínico ni los comentarios del médico: solo posiciones y conteos.

Código de salida:
    preparar: 0 listo · 2 reporte de modo mock · 3 reporte inválido · 4 la planilla ya existe
    tabular:  0 planilla completa · 1 faltan respuestas o hay respuestas inválidas
              · 3 no se encontraron los CSV

Sin red ni LLM.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(Path(__file__).parent))

from evaluar_reporte import ReporteInvalido, leer_reporte  # noqa: E402

from backend.pipeline.pdf_exporter import generate_pdf  # noqa: E402
from backend.pipeline.revision_medica import (  # noqa: E402
    COLUMNAS_PLANILLA,
    PREGUNTAS_GLOBALES,
    PREGUNTAS_HIPOTESIS,
    ResumenRevision,
    filas_planilla,
    generar_planilla_pdf,
    tabular,
)

SALIDA = _RAIZ / "output" / "revision_medica"
_COLUMNAS_GENERALES = ("pregunta", "enunciado", "opciones", "respuesta")


# ── preparar ───────────────────────────────────────────────────────────────────

def _escribir_csv(ruta: Path, columnas: tuple[str, ...], filas: list[dict]) -> None:
    # utf-8-sig: con el BOM, Excel abre las tildes bien.
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(columnas))
        escritor.writeheader()
        escritor.writerows(filas)


def preparar(ruta_reporte: Path, salida: Path | None) -> int:
    try:
        reporte = leer_reporte(ruta_reporte)
    except ReporteInvalido as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    if reporte.metadata.mock:
        print("Error: el reporte es de modo mock (respuestas grabadas). "
              "Para la revisión médica usá el reporte de una corrida real.", file=sys.stderr)
        return 2

    carpeta = salida or SALIDA / ruta_reporte.stem
    if (carpeta / "planilla.csv").exists():
        print(f"Error: {carpeta / 'planilla.csv'} ya existe y puede tener respuestas. "
              "Usá otra --salida.", file=sys.stderr)
        return 4
    carpeta.mkdir(parents=True, exist_ok=True)

    (carpeta / "reporte.pdf").write_bytes(generate_pdf(reporte))
    (carpeta / "planilla.pdf").write_bytes(generar_planilla_pdf(reporte))
    _escribir_csv(carpeta / "planilla.csv", COLUMNAS_PLANILLA, filas_planilla(reporte))
    generales = [
        {"pregunta": p.id, "enunciado": p.enunciado, "opciones": " / ".join(p.opciones), "respuesta": ""}
        for p in PREGUNTAS_GLOBALES
    ] + [{"pregunta": "comentarios", "enunciado": "Comentarios generales",
          "opciones": "texto libre", "respuesta": ""}]
    _escribir_csv(carpeta / "generales.csv", _COLUMNAS_GENERALES, generales)

    print(f"Material listo: {len(reporte.hypotheses)} hipótesis.")
    for nombre in ("reporte.pdf", "planilla.pdf", "planilla.csv", "generales.csv"):
        print(f"  {nombre}")
    print(f"Carpeta: {carpeta.name}/")
    return 0


# ── tabular ────────────────────────────────────────────────────────────────────

def _leer_csv(ruta: Path) -> list[dict]:
    texto = ruta.read_text(encoding="utf-8-sig")
    encabezado = texto.splitlines()[0] if texto else ""
    delimitador = ";" if encabezado.count(";") > encabezado.count(",") else ","
    return list(csv.DictReader(texto.splitlines(), delimiter=delimitador))


def _valor(v: float | None) -> str:
    return "sin datos" if v is None else f"{v:.2f}".replace(".", ",")


def formatear(r: ResumenRevision) -> str:
    """Texto del resumen: solo conteos y posiciones de hipótesis, sin texto clínico."""
    c = r.conteos
    lineas = [
        "Revisión médica del reporte — NEXUS",
        f"Hipótesis revisadas: {r.hipotesis}",
        "Planilla completa" if r.completa else f"Planilla incompleta: {len(r.problemas)} problema(s)",
    ]
    lineas += [f"  - {p}" for p in r.problemas]
    con_cita = sum(v for k, v in c["cita_respalda"].items() if k != "sin_cita")
    lineas += [
        "",
        "Indicadores",
        f"  Pertinencia: {_valor(r.indicadores['pertinencia'])} "
        f"({c['pertinente']['si']} de {sum(c['pertinente'].values())})",
        f"  Citas que respaldan la hipótesis: {_valor(r.indicadores['citas_que_respaldan'])} "
        f"({c['cita_respalda']['si']} de {con_cita} con cita)",
        f"  Nivel de evidencia razonable: {_valor(r.indicadores['nivel_razonable'])} "
        f"({c['nivel_razonable']['si']} de {sum(c['nivel_razonable'].values())})",
        f"  La investigaría: {_valor(r.indicadores['investigaria'])} "
        f"({c['investigaria']['si']} de {sum(c['investigaria'].values())})",
        f"  Hipótesis con respaldo verificado sin respaldo clínico: "
        f"{len(r.respaldo_verificado_sin_respaldo_clinico)}"
        + (f" (hipótesis {', '.join(map(str, r.respaldo_verificado_sin_respaldo_clinico))})"
           if r.respaldo_verificado_sin_respaldo_clinico else ""),
        "",
        "Respuestas por pregunta",
    ]
    for p in PREGUNTAS_HIPOTESIS:
        detalle = ", ".join(f"{k}={v}" for k, v in c[p.id].items())
        lineas.append(f"  {p.id}: {detalle}, sin responder={r.sin_responder[p.id]}")
    lineas += ["", "Preguntas generales"]
    for p in PREGUNTAS_GLOBALES:
        lineas.append(f"  {p.id}: {r.globales.get(p.id, 'sin respuesta válida')}")
    return "\n".join(lineas) + "\n"


def tabular_carpeta(carpeta: Path) -> int:
    planilla, generales = carpeta / "planilla.csv", carpeta / "generales.csv"
    faltan = [p.name for p in (planilla, generales) if not p.exists()]
    if faltan:
        print(f"Error: no se encontró {', '.join(faltan)} en {carpeta}.", file=sys.stderr)
        return 3

    resumen = tabular(_leer_csv(planilla), _leer_csv(generales))
    texto = formatear(resumen)
    print(texto, end="")
    (carpeta / "resumen.json").write_text(resumen.model_dump_json(indent=2), encoding="utf-8")
    (carpeta / "resumen.txt").write_text(texto, encoding="utf-8")
    return 0 if resumen.completa else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Material de la revisión médica del reporte.")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_prep = sub.add_parser("preparar", help="genera el PDF del reporte y la planilla")
    p_prep.add_argument("reporte", type=Path, help="JSON del reporte (de una corrida real)")
    p_prep.add_argument("--salida", type=Path, default=None,
                        help="carpeta de salida (por defecto output/revision_medica/<nombre>)")
    p_tab = sub.add_parser("tabular", help="resume la planilla respondida")
    p_tab.add_argument("carpeta", type=Path, help="carpeta con planilla.csv y generales.csv")
    args = parser.parse_args(argv)

    if args.comando == "preparar":
        return preparar(args.reporte, args.salida)
    return tabular_carpeta(args.carpeta)


if __name__ == "__main__":
    sys.exit(main())
