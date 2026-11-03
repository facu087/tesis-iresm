"""
Evalúa un reporte de NEXUS guardado en JSON contra los criterios de calidad
(tarjeta #59, `backend/pipeline/calidad.py`).

Uso:
    python3 scripts/evaluar_reporte.py output/medicion_costos/reporte.json

Imprime la evaluación y guarda `evaluacion.json` y `evaluacion.txt` en
`output/evaluacion_calidad/<nombre-del-reporte>/` (ignorada por git).

Código de salida:
    0  cumple
    1  no_cumple
    2  no_evaluable (modo mock o verificación bibliográfica incompleta)
    3  el archivo no existe, no es JSON o no es un reporte válido

No usa red ni LLM: se puede correr las veces que haga falta sobre la misma
corrida. La evaluación no contiene texto clínico del reporte.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

from pydantic import ValidationError  # noqa: E402

from backend.api.schemas import StructuredReport  # noqa: E402
from backend.pipeline.calidad import EvaluacionCalidad, Metrica, evaluar  # noqa: E402

SALIDA = _RAIZ / "output" / "evaluacion_calidad"

CODIGOS = {"cumple": 0, "no_cumple": 1, "no_evaluable": 2}
CODIGO_ARCHIVO_INVALIDO = 3


class ReporteInvalido(Exception):
    """El archivo no se pudo leer como un reporte de NEXUS."""


def leer_reporte(ruta: Path) -> StructuredReport:
    """Lee y valida el reporte; levanta `ReporteInvalido` con el motivo."""
    try:
        crudo = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ReporteInvalido(f"No existe el archivo {ruta}.") from None
    except OSError as exc:
        raise ReporteInvalido(f"No se pudo leer {ruta}: {exc.strerror}.") from None
    try:
        json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise ReporteInvalido(f"{ruta} no es JSON válido (línea {exc.lineno}).") from None
    try:
        return StructuredReport.model_validate_json(crudo)
    except ValidationError as exc:
        campos = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})[:5]
        raise ReporteInvalido(
            f"{ruta} no es un reporte de NEXUS válido. Campos con problemas: {', '.join(campos)}."
        ) from None


def _valor(valor: float | None) -> str:
    return "sin datos" if valor is None else f"{valor:.2f}".replace(".", ",")


def _fila_metrica(m: Metrica) -> str:
    signo = "≥" if m.sentido == "minimo" else "≤"
    marca = "OK " if m.cumple else "NO "
    return (
        f"  [{marca}] {m.nombre:<22} {_valor(m.valor):>9}  "
        f"(umbral {signo} {_valor(m.umbral)}; {m.numerador}/{m.denominador})"
    )


def formatear(evaluacion: EvaluacionCalidad, origen: str) -> str:
    """Texto legible de la evaluación."""
    ind = evaluacion.indicadores
    lineas = [
        "Evaluación de calidad del reporte — NEXUS",
        f"Reporte: {origen}",
        f"Criterios: versión {evaluacion.criterios.version}",
        "",
        f"VEREDICTO: {evaluacion.veredicto.upper()}",
    ]
    lineas += [f"  - {m}" for m in evaluacion.motivos] or ["  (sin motivos: se cumplen todos los criterios)"]
    lineas += ["", "Métricas"] + [_fila_metrica(m) for m in evaluacion.metricas]

    def _opt(valor: object) -> str:
        return "no disponible" if valor is None else str(valor)

    lineas += [
        "",
        "Indicadores (informativos)",
        f"  Estado de la verificación: {_opt(evaluacion.estado_verificacion)}"
        + ("  ·  modo mock" if evaluacion.modo_mock else ""),
        "  Niveles efectivos: " + ", ".join(f"{k}={v}" for k, v in ind.niveles_efectivos.items()),
        f"  Hipótesis: {ind.hipotesis_respaldadas} respaldadas, {ind.hipotesis_pendientes} pendientes, "
        f"{ind.hipotesis_especulativas} especulativas",
        f"  Fuentes: {ind.fuentes_verificadas} verificadas, {ind.fuentes_discordantes} discordantes, "
        f"{ind.fuentes_inexistentes} inexistentes, {ind.fuentes_sin_pmid} sin PMID, "
        f"{ind.fuentes_no_verificables} no verificables",
        f"  Anclaje en el RAG: {_valor(ind.anclaje_rag) if ind.anclaje_rag is not None else 'no disponible'}"
        f" ({_opt(ind.citas_ancladas_en_rag)} de {_opt(ind.citas_del_arbitraje)} citas)",
        f"  Recitación (Ronda 5): ejecutada={_opt(ind.recitacion_ejecutada)}, "
        f"entraron={_opt(ind.recitacion_hipotesis)}, mejoradas={_opt(ind.recitacion_mejoradas)}",
        f"  Contradicciones: {_opt(ind.contradicciones)}",
        f"  Agentes con hipótesis: {', '.join(ind.agentes_con_hipotesis) or 'ninguno'}",
        f"  Ensayos clínicos: {ind.ensayos_clinicos}",
        "",
        "Detalle por hipótesis (por posición; sin texto clínico)",
        "  #   estado        declarado  efectivo  verificadas  sobredeclarada",
    ]
    for d in evaluacion.detalle:
        lineas.append(
            f"  {d.rank:<3} {d.status:<13} {d.nivel_declarado or '-':<10} {d.nivel_efectivo:<9} "
            f"{d.fuentes_verificadas:<12} {'sí' if d.sobredeclarada else 'no'}"
        )
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None, salida: Path = SALIDA) -> int:
    parser = argparse.ArgumentParser(description="Evalúa la calidad de un reporte de NEXUS.")
    parser.add_argument("reporte", type=Path, help="JSON del reporte (el que devuelve POST /api/analyze)")
    args = parser.parse_args(argv)

    try:
        reporte = leer_reporte(args.reporte)
    except ReporteInvalido as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return CODIGO_ARCHIVO_INVALIDO

    evaluacion = evaluar(reporte)
    texto = formatear(evaluacion, args.reporte.name)
    print(texto, end="")

    carpeta = salida / args.reporte.stem
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "evaluacion.json").write_text(
        evaluacion.model_dump_json(indent=2), encoding="utf-8"
    )
    (carpeta / "evaluacion.txt").write_text(texto, encoding="utf-8")
    print(f"\nGuardado en {carpeta}")
    return CODIGOS[evaluacion.veredicto]


if __name__ == "__main__":
    sys.exit(main())
