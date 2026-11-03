"""
Demo de la tarjeta #59 — criterios de calidad del reporte.

Sin red ni cuota. Arma reportes sintéticos del caso base (neuropatía axonal
sensitivomotora, varón de 42 años) y muestra, para cada uno, entrada (qué se
simuló) → salida (veredicto, motivos y métricas contra umbral):

    1. Reporte que cumple todos los criterios
    2. Cobertura de respaldo baja (pocas hipótesis con fuente verificada)
    3. Precisión de citas baja (PMIDs que apuntan a otro artículo)
    4. Sobredeclaración (los agentes declaran más nivel del que respaldan)
    5. Nivel II sin ninguna fuente verificada (requisito de consistencia)
    6. Reporte de modo mock (no evaluable)
    7. Verificación bibliográfica caída (no evaluable)

Guarda en output/demo_criterios_calidad/:
    resultado.txt   — salida completa
    resumen.json    — veredicto esperado y obtenido por escenario
    criterios.txt   — tabla de criterios vigente

Sale con código 1 si algún veredicto no es el esperado o si la evaluación
contiene texto clínico del reporte.

Uso:
    python3 scripts/demo_criterios_calidad.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

from backend.api.schemas import (  # noqa: E402
    ArbitrationOut,
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    RecitationOut,
    ReportMetadata,
    StructuredReport,
    VerificationSummary,
)
from backend.models.hypothesis import Source  # noqa: E402
from backend.pipeline.calidad import CRITERIOS, EvaluacionCalidad, evaluar  # noqa: E402

SALIDA = _RAIZ / "output" / "demo_criterios_calidad"

_HIPOTESIS_BASE = [
    "Neuropatía axonal por déficit de vitamina B12",
    "Neuropatía tóxica por exposición a pesticidas organofosforados",
    "Polineuropatía amiloidótica familiar por variante TTR",
    "Neuropatía asociada a gammapatía monoclonal",
    "Charcot-Marie-Tooth tipo 2 de inicio tardío",
    "Neuropatía paraneoplásica con anticuerpos anti-Hu",
]


def _hipotesis(rank: int, *, status="respaldada", efectivo="III", declarado="III", verificadas=1):
    return RankedHypothesis(
        rank=rank,
        text=_HIPOTESIS_BASE[rank - 1],
        priority="MEDIUM",
        evidence_level=efectivo,
        declared_evidence_level=declarado,
        rationale="Fundamentación del caso base.",
        supporting_agents=["Analista de Literatura", "Consultor Clínico"],
        sources=[Source(pmid=f"{31000000 + rank}", title=f"Artículo {rank}")],
        status=status,
        verified_sources=verificadas,
    )


def _reporte(
    hipotesis: list[RankedHypothesis] | None = None,
    *,
    verificadas: int = 9,
    discordantes: int = 1,
    estado: str = "completa",
    mock: bool = False,
) -> StructuredReport:
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
            nexus_version="0.5.0",
            processing_time_seconds=500.0,
            mock=mock,
        ),
        case_summary=CaseSummarySection(
            narrative="Paciente varón de 42 años con neuropatía axonal sensitivomotora."
        ),
        hypotheses=hipotesis if hipotesis is not None else [_hipotesis(i) for i in range(1, 7)],
        debate_summary=DebateSummary(
            rounds_completed=4, total_critiques=6, divergences=[], consensus_reached=True
        ),
        clinical_trials=[],
        bibliography=[],
        verification=VerificationSummary(
            total_fuentes=verificadas + discordantes,
            verificadas=verificadas,
            discordantes=discordantes,
            estado=estado,
        ),
        arbitration=ArbitrationOut(
            cited_sources=10, rag_overlap=6, contradictions=1,
            recitation=RecitationOut(executed=True, recited=2, improved=1),
        ),
    )


@dataclass
class Escenario:
    titulo: str
    simulado: str
    reporte: StructuredReport
    esperado: str


def _escenarios() -> list[Escenario]:
    return [
        Escenario(
            "1. Reporte que cumple",
            "6 hipótesis respaldadas, 9 de 10 citas verificadas, niveles declarados = efectivos",
            _reporte(), "cumple",
        ),
        Escenario(
            "2. Cobertura de respaldo baja",
            "solo 2 de 6 hipótesis tienen una fuente verificada",
            _reporte([_hipotesis(1), _hipotesis(2)] + [
                _hipotesis(i, status="especulativa", verificadas=0) for i in range(3, 7)
            ]),
            "no_cumple",
        ),
        Escenario(
            "3. Precisión de citas baja",
            "de 10 citas contrastadas, 3 verificadas y 7 discordantes (PMID de otro artículo)",
            _reporte(verificadas=3, discordantes=7), "no_cumple",
        ),
        Escenario(
            "4. Sobredeclaración",
            "4 de 6 hipótesis declaradas nivel I por el agente quedan en III tras la verificación",
            _reporte([_hipotesis(i, declarado="I") for i in range(1, 5)] + [
                _hipotesis(5), _hipotesis(6)
            ]),
            "no_cumple",
        ),
        Escenario(
            "5. Nivel II sin fuente verificada",
            "la hipótesis #3 queda con nivel efectivo II y cero fuentes verificadas",
            _reporte([_hipotesis(1), _hipotesis(2), _hipotesis(3, efectivo="II", declarado="II", verificadas=0),
                      _hipotesis(4), _hipotesis(5), _hipotesis(6)]),
            "no_cumple",
        ),
        Escenario(
            "6. Reporte de modo mock",
            "el mismo reporte del escenario 1, generado con NEXUS_MOCK_LLM=1",
            _reporte(mock=True), "no_evaluable",
        ),
        Escenario(
            "7. Verificación caída",
            "PubMed no respondió: la verificación quedó 'no_disponible'",
            _reporte(estado="no_disponible"), "no_evaluable",
        ),
    ]


def _bloque(e: Escenario, evaluacion: EvaluacionCalidad) -> str:
    lineas = [
        "=" * 78,
        e.titulo,
        "=" * 78,
        f"ENTRADA  {e.simulado}",
        f"SALIDA   veredicto: {evaluacion.veredicto}  (esperado: {e.esperado})",
    ]
    lineas += [f"         - {m}" for m in evaluacion.motivos] or ["         (sin motivos)"]
    for m in evaluacion.metricas:
        valor = "sin datos" if m.valor is None else f"{m.valor:.2f}".replace(".", ",")
        signo = "≥" if m.sentido == "minimo" else "≤"
        umbral = f"{m.umbral:.2f}".replace(".", ",")
        lineas.append(f"         [{'OK' if m.cumple else 'NO'}] {m.nombre:<22} {valor:>9}  (umbral {signo} {umbral})")
    return "\n".join(lineas)


def _criterios() -> str:
    c = CRITERIOS
    return "\n".join([
        f"Criterios de calidad del reporte — versión {c.version} (provisional, se recalibra en la #58)",
        "",
        "No evaluable si: el reporte es de modo mock, o la verificación bibliográfica quedó",
        "  'parcial', 'no_disponible' o no informa estado.",
        "No cumple si: no hay hipótesis, falta el aviso de no diagnóstico, alguna hipótesis tiene",
        "  nivel efectivo I o II sin fuente verificada, o falla alguna métrica.",
        "",
        "Métrica                 Cálculo                                               Pasa si",
        f"Cobertura de respaldo   respaldadas / hipótesis                               ≥ {c.min_cobertura_respaldo:.2f}",
        f"Precisión de citas      verificadas / (verificadas+discordantes+inexistentes) ≥ {c.min_precision_citas:.2f}",
        f"Sobredeclaración        efectivo < declarado / hipótesis                      ≤ {c.max_sobredeclaracion:.2f}",
        "",
        "Una métrica sin datos (denominador cero) no se cumple.",
    ]) + "\n"


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    bloques: list[str] = []
    resumen: list[dict] = []
    fallos: list[str] = []

    for e in _escenarios():
        evaluacion = evaluar(e.reporte)
        bloques.append(_bloque(e, evaluacion))
        serializada = evaluacion.model_dump_json()
        filtra = any(h.text in serializada for h in e.reporte.hypotheses)
        if evaluacion.veredicto != e.esperado:
            fallos.append(f"{e.titulo}: se esperaba {e.esperado}, salió {evaluacion.veredicto}")
        if filtra:
            fallos.append(f"{e.titulo}: la evaluación contiene texto de una hipótesis")
        resumen.append({
            "escenario": e.titulo,
            "esperado": e.esperado,
            "obtenido": evaluacion.veredicto,
            "ok": evaluacion.veredicto == e.esperado and not filtra,
            "motivos": evaluacion.motivos,
            "metricas": {m.nombre: m.valor for m in evaluacion.metricas},
        })

    pie = ["", "=" * 78]
    pie += [f"FALLO: {f}" for f in fallos] or [f"OK: {len(resumen)} de {len(resumen)} escenarios con el veredicto esperado."]
    texto = _criterios() + "\n" + "\n\n".join(bloques) + "\n" + "\n".join(pie) + "\n"
    print(texto, end="")

    (SALIDA / "resultado.txt").write_text(texto, encoding="utf-8")
    (SALIDA / "criterios.txt").write_text(_criterios(), encoding="utf-8")
    (SALIDA / "resumen.json").write_text(
        json.dumps({"criterios": CRITERIOS.model_dump(), "escenarios": resumen}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nGuardado en {SALIDA}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
