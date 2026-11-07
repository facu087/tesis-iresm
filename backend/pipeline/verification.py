"""
Verificación bibliográfica de las fuentes citadas por los agentes.

Los LLM alucinan PMIDs: generan números con formato válido que además suelen
existir en PubMed, pero que apuntan a artículos sin ninguna relación con lo que
el agente afirma haber citado. Por eso `PubMedClient.verify_pmid()` (chequeo de
existencia) no alcanza: hay que traer los metadatos reales y comparar el título
declarado contra el título que PubMed devuelve para ese PMID.

Este módulo es el núcleo de verificación del Agente 04 (Árbitro Verificador).
No descarta nada: marca cada fuente con su estado y deja que el reporte
etiquete como "especulativa" toda hipótesis sin respaldo verificable.
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum

import httpx

from ..external.pubmed import PubMedClient
from ..models.hypothesis import Source
from ..models.report import Report

# Umbral de coincidencia entre el título declarado y el real (0–1).
# Se usa containment (intersección sobre el conjunto más chico) para tolerar
# subtítulos truncados y variantes de puntuación, no para tolerar otro paper.
_MIN_TITLE_MATCH = 0.60

# Palabras sin valor discriminante al comparar títulos.
_STOPWORDS = frozenset(
    """a an and as at by for from in into of on or the to with without vs versus
    el la los las un una unos unas de del y o en con sin para por a""".split()
)


class SourceStatus(str, Enum):
    """Resultado de verificar una fuente contra PubMed."""

    VERIFICADA = "verificada"        # El PMID existe y el título coincide
    DISCORDANTE = "discordante"      # El PMID existe pero es otro artículo
    INEXISTENTE = "inexistente"      # El PMID no está en PubMed
    SIN_PMID = "sin_pmid"            # La fuente no declaró PMID
    NO_VERIFICABLE = "no_verificable"  # Falló la consulta (red, rate limit, etc.)


@dataclass
class SourceVerification:
    """
    Veredicto sobre una fuente citada, con el título real si difiere.

    `publication_types` son los tipos que PubMed indexa para el artículo
    ("Meta-Analysis", "Case Reports", …). Solo se completan cuando la fuente
    queda VERIFICADA: los de un PMID discordante son de otro artículo.
    """

    pmid: str | None
    status: SourceStatus
    claimed_title: str
    actual_title: str = ""
    match_score: float = 0.0
    publication_types: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True solo si la referencia respalda realmente lo que el agente citó."""
        return self.status is SourceStatus.VERIFICADA


# ── Estado global y causa de un fallo (tarjeta #91) ───────────────────────────

class CausaFallo(str, Enum):
    """Por qué falló una consulta a PubMed. Es lo único del fallo que llega al reporte."""

    RED = "red"                              # Sin conexión o tiempo de espera agotado
    LIMITE_VELOCIDAD = "limite_velocidad"    # HTTP 429
    CONFIGURACION = "configuracion"          # HTTP 400/401/403: casi siempre la api_key
    ERROR_API = "error_api"                  # HTTP 5xx u otra respuesta inutilizable
    DESCONOCIDA = "desconocida"              # Cualquier otro fallo


class EstadoVerificacion(str, Enum):
    """Resultado global de las consultas a PubMed de un análisis."""

    COMPLETA = "completa"
    PARCIAL = "parcial"
    NO_DISPONIBLE = "no_disponible"
    SIN_CONSULTA = "sin_consulta"


@dataclass(frozen=True)
class ResultadoConsulta:
    """Resultado de una consulta a PubMed: respondió, o falló por `causa`."""

    ok: bool
    causa: CausaFallo | None = None


def clasificar_fallo(exc: BaseException) -> CausaFallo:
    """
    Traduce la excepción de una consulta a PubMed a una categoría fija.

    Se decide por el tipo de excepción y el código HTTP, nunca por el texto:
    el mensaje de httpx cambia entre versiones y contiene la URL con `api_key`.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        codigo = exc.response.status_code
        if codigo == 429:
            return CausaFallo.LIMITE_VELOCIDAD
        if codigo in (400, 401, 403):
            return CausaFallo.CONFIGURACION
        return CausaFallo.ERROR_API
    if isinstance(exc, httpx.TransportError):
        return CausaFallo.RED
    if isinstance(exc, ValueError):
        # Incluye json.JSONDecodeError: PubMed respondió algo que no es JSON.
        return CausaFallo.ERROR_API
    return CausaFallo.DESCONOCIDA


def estado_verificacion(
    resultados: Sequence[ResultadoConsulta],
) -> tuple[EstadoVerificacion, CausaFallo | None]:
    """
    Estado global a partir de los resultados de las consultas, en orden.

    Con más de un fallo se informa la causa del primero: la verificación inicial
    va antes que la Ronda 5 y es la que afecta a más fuentes.
    """
    if not resultados:
        return EstadoVerificacion.SIN_CONSULTA, None
    fallos = [r for r in resultados if not r.ok]
    if not fallos:
        return EstadoVerificacion.COMPLETA, None
    estado = (
        EstadoVerificacion.NO_DISPONIBLE
        if len(fallos) == len(resultados)
        else EstadoVerificacion.PARCIAL
    )
    return estado, fallos[0].causa


_registro_activo: ContextVar[list[ResultadoConsulta] | None] = ContextVar(
    "nexus_registro_consultas_pubmed", default=None
)


@contextmanager
def registro_de_consultas() -> Iterator[list[ResultadoConsulta]]:
    """
    Abre el registro de consultas a PubMed de un análisis.

    Mientras está abierto, cada consulta que hace `verify_sources()` —la
    verificación inicial en el router y la re-verificación de la Ronda 5 dentro
    del Árbitro— anota su resultado en la lista que devuelve. Se basa en
    `contextvars`, así que dos análisis concurrentes no se mezclan. Fuera de un
    registro (scripts, tests sueltos) no se anota nada.
    """
    resultados: list[ResultadoConsulta] = []
    token = _registro_activo.set(resultados)
    try:
        yield resultados
    finally:
        _registro_activo.reset(token)


def _anotar(resultado: ResultadoConsulta) -> None:
    """Anota en el registro activo, si hay uno."""
    registro = _registro_activo.get()
    if registro is not None:
        registro.append(resultado)


def _normalize_tokens(title: str) -> set[str]:
    """
    Reduce un título a su conjunto de palabras significativas.

    Quita acentos, mayúsculas, puntuación (incluidos los guiones no separables
    que devuelven algunos LLM) y stopwords.
    """
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c)
    )
    limpio = "".join(c.lower() if c.isalnum() else " " for c in sin_acentos)
    return {t for t in limpio.split() if len(t) > 2 and t not in _STOPWORDS}


def _title_match_score(claimed: str, actual: str) -> float:
    """
    Mide cuánto se parecen dos títulos, entre 0 (nada) y 1 (uno contiene al otro).

    Containment en lugar de Jaccard: PubMed a veces devuelve el título con
    subtítulo completo y el agente cita solo la primera parte (o al revés).
    """
    a, b = _normalize_tokens(claimed), _normalize_tokens(actual)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _verify_one(source: Source, metadata: dict[str, dict]) -> SourceVerification:
    """Emite el veredicto de una fuente contra los metadatos traídos de PubMed."""
    if not source.pmid:
        return SourceVerification(
            pmid=None, status=SourceStatus.SIN_PMID, claimed_title=source.title
        )

    real = metadata.get(source.pmid)
    if real is None:
        return SourceVerification(
            pmid=source.pmid,
            status=SourceStatus.INEXISTENTE,
            claimed_title=source.title,
        )

    actual_title = real.get("title", "")
    score = _title_match_score(source.title, actual_title)
    status = (
        SourceStatus.VERIFICADA if score >= _MIN_TITLE_MATCH else SourceStatus.DISCORDANTE
    )
    publication_types = (
        list(real.get("pubtypes", [])) if status is SourceStatus.VERIFICADA else []
    )
    return SourceVerification(
        pmid=source.pmid,
        status=status,
        claimed_title=source.title,
        actual_title=actual_title,
        match_score=round(score, 2),
        publication_types=publication_types,
    )


def collect_sources(report: Report) -> list[Source]:
    """Devuelve todas las fuentes citadas en las hipótesis finales del reporte."""
    return [source for h in report.hypotheses for source in h.sources]


async def verify_report_sources(report: Report) -> dict[str, SourceVerification]:
    """
    Verifica contra PubMed todas las fuentes citadas en el reporte.

    Hace una sola llamada a esummary con todos los PMIDs (batch), así que el
    costo es constante y no proporcional a la cantidad de referencias.

    Args:
        report: Report final del motor de debate, con sus hipótesis y fuentes.

    Returns:
        Dict {clave de fuente → SourceVerification}. La clave es el PMID cuando
        existe, y el título cuando la fuente no declaró PMID. Ante un fallo de
        red devuelve todas las fuentes como NO_VERIFICABLE: nunca se descarta
        una referencia por un problema de infraestructura.
    """
    return await verify_sources(collect_sources(report))


async def verify_sources(sources: Sequence[Source]) -> dict[str, SourceVerification]:
    """
    Verifica un conjunto cualquiera de fuentes contra PubMed.

    Es el cuerpo de `verify_report_sources()`, extraído para poder re-verificar
    solo las fuentes que produjo la ronda de recitación sin rehacer el reporte
    entero ni volver a consultar por los PMIDs que ya se verificaron.

    Args:
        sources: Fuentes a verificar. Pueden repetirse: se deduplican.

    Returns:
        Dict {clave de fuente → SourceVerification}, igual que
        `verify_report_sources()`.
    """
    if not sources:
        return {}

    pmids = sorted({s.pmid for s in sources if s.pmid})

    metadata: dict[str, dict] = {}
    fallo_consulta = False
    if pmids:
        try:
            async with PubMedClient() as client:
                metadata = await client.fetch_metadata(pmids)
        except Exception as exc:
            fallo_consulta = True
            causa = clasificar_fallo(exc)
            _anotar(ResultadoConsulta(ok=False, causa=causa))
            print(
                f"[NEXUS] Verificación bibliográfica no disponible "
                f"(causa: {causa.value}; {type(exc).__name__}: {exc}). "
                f"{len(pmids)} PMIDs quedan sin verificar.",
                file=sys.stderr,
            )
        else:
            _anotar(ResultadoConsulta(ok=True))

    verificaciones: dict[str, SourceVerification] = {}
    for source in sources:
        clave = source.pmid or source.title
        if not clave or clave in verificaciones:
            continue
        if fallo_consulta and source.pmid:
            verificaciones[clave] = SourceVerification(
                pmid=source.pmid,
                status=SourceStatus.NO_VERIFICABLE,
                claimed_title=source.title,
            )
        else:
            verificaciones[clave] = _verify_one(source, metadata)

    return verificaciones


def source_key(source: Source) -> str:
    """Clave con la que una fuente se busca en el dict de verificaciones."""
    return source.pmid or source.title
