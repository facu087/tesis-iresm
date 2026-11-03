"""
Criterios de calidad del reporte (tarjeta #59).

Evalúa un `StructuredReport` contra criterios objetivos de cobertura, fuentes
verificadas y nivel de evidencia, y devuelve un veredicto reproducible:

- `no_evaluable`: el reporte no sirve para medir (modo mock o verificación
  bibliográfica que no corrió completa). Las métricas se calculan igual.
- `no_cumple`: falló un requisito de consistencia o una métrica.
- `cumple`: todo lo anterior se cumple.

Es una herramienta de validación del equipo, no parte del pipeline: no la
llama el router y no se muestra al médico. No usa red ni LLM.

La evaluación nunca copia texto clínico del reporte: identifica cada
hipótesis por su posición en el ranking y arma sus propios motivos.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..api.schemas import StructuredReport

Veredicto = Literal["cumple", "no_cumple", "no_evaluable"]

_RANGO_NIVEL: dict[str, int] = {"I": 0, "II": 1, "III": 2}
_ESTADOS_EVALUABLES = frozenset({"completa", "sin_consulta"})


class Criterios(BaseModel):
    """Umbrales de las métricas, con la versión que los identifica."""

    model_config = ConfigDict(frozen=True)

    version: str
    min_cobertura_respaldo: float
    min_precision_citas: float
    max_sobredeclaracion: float


# Provisionales: se recalibran con la corrida real de la tarjeta #58.
# Cambiar un umbral exige cambiar también la versión.
CRITERIOS = Criterios(
    version="2026-11-provisional",
    min_cobertura_respaldo=0.50,
    min_precision_citas=0.70,
    max_sobredeclaracion=0.50,
)


class Metrica(BaseModel):
    """Una métrica comparada con su umbral. `valor` es None si no hay datos."""

    nombre: str
    valor: float | None
    umbral: float
    sentido: Literal["minimo", "maximo"]
    numerador: int
    denominador: int
    cumple: bool


class DetalleHipotesis(BaseModel):
    """Una fila por hipótesis, sin su texto."""

    rank: int
    status: str
    nivel_declarado: str | None
    nivel_efectivo: str
    fuentes_verificadas: int
    sobredeclarada: bool


class Indicadores(BaseModel):
    """Datos informativos: no tienen umbral ni afectan el veredicto.

    Un campo en None significa que el dato no está en el reporte.
    """

    niveles_efectivos: dict[str, int]
    hipotesis_respaldadas: int
    hipotesis_pendientes: int
    hipotesis_especulativas: int
    fuentes_verificadas: int
    fuentes_discordantes: int
    fuentes_inexistentes: int
    fuentes_sin_pmid: int
    fuentes_no_verificables: int
    # Tarjeta #92: fuentes descartadas al cerrar el debate por no venir del RAG.
    citas_fuera_del_rag: int | None
    citas_del_arbitraje: int | None
    citas_ancladas_en_rag: int | None
    anclaje_rag: float | None
    recitacion_ejecutada: bool | None
    recitacion_hipotesis: int | None
    recitacion_mejoradas: int | None
    contradicciones: int | None
    agentes_con_hipotesis: list[str]
    ensayos_clinicos: int


class EvaluacionCalidad(BaseModel):
    """Resultado completo de evaluar un reporte."""

    veredicto: Veredicto
    motivos: list[str]
    criterios: Criterios
    estado_verificacion: str | None
    modo_mock: bool
    metricas: list[Metrica]
    indicadores: Indicadores
    detalle: list[DetalleHipotesis]


# ── Cálculo ────────────────────────────────────────────────────────────────────

def _proporcion(numerador: int, denominador: int) -> float | None:
    return numerador / denominador if denominador else None


def _metrica(
    nombre: str,
    numerador: int,
    denominador: int,
    umbral: float,
    sentido: Literal["minimo", "maximo"],
) -> Metrica:
    """Compara sobre el valor sin redondear. Sin datos nunca se cumple."""
    valor = _proporcion(numerador, denominador)
    if valor is None:
        cumple = False
    elif sentido == "minimo":
        cumple = valor >= umbral
    else:
        cumple = valor <= umbral
    return Metrica(
        nombre=nombre, valor=valor, umbral=umbral, sentido=sentido,
        numerador=numerador, denominador=denominador, cumple=cumple,
    )


def _sobredeclarada(declarado: str | None, efectivo: str) -> bool:
    """True si el nivel efectivo quedó por debajo del declarado por el agente."""
    if declarado not in _RANGO_NIVEL or efectivo not in _RANGO_NIVEL:
        return False
    return _RANGO_NIVEL[efectivo] > _RANGO_NIVEL[declarado]


def _numero(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _motivo_metrica(m: Metrica) -> str:
    if m.valor is None:
        return f"{m.nombre}: sin datos (denominador cero), no se puede aprobar."
    signo = "<" if m.sentido == "minimo" else ">"
    return f"{m.nombre} {_numero(m.valor)} {signo} {_numero(m.umbral)}."


def _detalle(reporte: StructuredReport) -> list[DetalleHipotesis]:
    return [
        DetalleHipotesis(
            rank=h.rank,
            status=h.status,
            nivel_declarado=h.declared_evidence_level,
            nivel_efectivo=h.evidence_level,
            fuentes_verificadas=h.verified_sources,
            sobredeclarada=_sobredeclarada(h.declared_evidence_level, h.evidence_level),
        )
        for h in reporte.hypotheses
    ]


def _metricas(
    reporte: StructuredReport, detalle: list[DetalleHipotesis], criterios: Criterios
) -> list[Metrica]:
    total = len(detalle)
    v = reporte.verification
    # Fuentes desde el resumen de la verificación: está deduplicado por PMID,
    # así una cita repetida en dos hipótesis no pesa doble.
    contrastadas = v.verificadas + v.discordantes + v.inexistentes
    return [
        _metrica(
            "Cobertura de respaldo",
            sum(1 for d in detalle if d.status == "respaldada"), total,
            criterios.min_cobertura_respaldo, "minimo",
        ),
        _metrica(
            "Precisión de citas",
            v.verificadas, contrastadas,
            criterios.min_precision_citas, "minimo",
        ),
        _metrica(
            "Sobredeclaración",
            sum(1 for d in detalle if d.sobredeclarada), total,
            criterios.max_sobredeclaracion, "maximo",
        ),
    ]


def _indicadores(reporte: StructuredReport, detalle: list[DetalleHipotesis]) -> Indicadores:
    niveles = {"I": 0, "II": 0, "III": 0}
    for d in detalle:
        if d.nivel_efectivo in niveles:
            niveles[d.nivel_efectivo] += 1

    agentes: list[str] = []
    for h in reporte.hypotheses:
        for agente in h.supporting_agents:
            if agente not in agentes:
                agentes.append(agente)

    v = reporte.verification
    a = reporte.arbitration
    return Indicadores(
        niveles_efectivos=niveles,
        hipotesis_respaldadas=sum(1 for d in detalle if d.status == "respaldada"),
        hipotesis_pendientes=sum(1 for d in detalle if d.status == "pendiente"),
        hipotesis_especulativas=sum(1 for d in detalle if d.status == "especulativa"),
        fuentes_verificadas=v.verificadas,
        fuentes_discordantes=v.discordantes,
        fuentes_inexistentes=v.inexistentes,
        fuentes_sin_pmid=v.sin_pmid,
        fuentes_no_verificables=v.no_verificables,
        citas_fuera_del_rag=v.fuera_del_rag,
        citas_del_arbitraje=a.cited_sources if a else None,
        citas_ancladas_en_rag=a.rag_overlap if a else None,
        anclaje_rag=_proporcion(a.rag_overlap, a.cited_sources) if a else None,
        recitacion_ejecutada=a.recitation.executed if a else None,
        recitacion_hipotesis=a.recitation.recited if a else None,
        recitacion_mejoradas=a.recitation.improved if a else None,
        contradicciones=a.contradictions if a else None,
        agentes_con_hipotesis=agentes,
        ensayos_clinicos=len(reporte.clinical_trials),
    )


def _motivos_de_evaluabilidad(reporte: StructuredReport) -> list[str]:
    motivos: list[str] = []
    if reporte.metadata.mock:
        motivos.append("El reporte es de modo mock: sus respuestas son grabadas, no una corrida real.")
    estado = reporte.verification.estado
    if estado is None:
        motivos.append("El reporte no informa el estado de la verificación bibliográfica.")
    elif estado not in _ESTADOS_EVALUABLES:
        motivos.append(
            f"La verificación bibliográfica quedó '{estado}': las métricas de fuentes no son concluyentes."
        )
    return motivos


def _motivos_de_consistencia(
    reporte: StructuredReport, detalle: list[DetalleHipotesis]
) -> list[str]:
    motivos: list[str] = []
    if not detalle:
        motivos.append("El reporte no tiene hipótesis.")
    if not reporte.metadata.disclaimer.strip():
        motivos.append("Falta el aviso de que NEXUS no emite diagnósticos.")
    for d in detalle:
        if d.nivel_efectivo in ("I", "II") and d.fuentes_verificadas == 0:
            motivos.append(
                f"La hipótesis #{d.rank} tiene nivel {d.nivel_efectivo} sin ninguna fuente verificada."
            )
    return motivos


def evaluar(reporte: StructuredReport, criterios: Criterios = CRITERIOS) -> EvaluacionCalidad:
    """
    Evalúa un reporte y devuelve el veredicto con sus motivos, métricas,
    indicadores y el detalle por hipótesis. Es determinista y no hace I/O.
    """
    detalle = _detalle(reporte)
    metricas = _metricas(reporte, detalle, criterios)

    no_evaluable = _motivos_de_evaluabilidad(reporte)
    if no_evaluable:
        veredicto: Veredicto = "no_evaluable"
        motivos = no_evaluable
    else:
        motivos = _motivos_de_consistencia(reporte, detalle) + [
            _motivo_metrica(m) for m in metricas if not m.cumple
        ]
        veredicto = "no_cumple" if motivos else "cumple"

    return EvaluacionCalidad(
        veredicto=veredicto,
        motivos=motivos,
        criterios=criterios,
        estado_verificacion=reporte.verification.estado,
        modo_mock=reporte.metadata.mock,
        metricas=metricas,
        indicadores=_indicadores(reporte, detalle),
        detalle=detalle,
    )
