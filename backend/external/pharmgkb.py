"""
Cliente para la API de PharmGKB (hoy ClinPGx).

PharmGKB se rebrandeó a ClinPGx y el host de la API anterior,
`api.pharmgkb.org`, **fue dado de baja**: no resuelve por DNS (NXDOMAIN,
confirmado contra 8.8.8.8 y no solo contra el resolver local). El sitio web sí
redirige con 301 de `www.pharmgkb.org` a `www.clinpgx.org`, así que navegando
no se nota nada — pero el cliente moría en la resolución de nombres.

Base URL: https://api.clinpgx.org/v1/data
Autenticación: ninguna (API pública)

PharmGKB relaciona genes, variantes, fármacos y fenotipos clínicos. Es la
fuente del Agente 02 (Especialista Genómica) cuando el caso tiene genes
alterados.

Endpoints usados (verificados contra la API real):
  - /gene?symbol={symbol}                            → gen por símbolo
  - /chemical?name={name}                            → fármaco por nombre
  - /clinicalAnnotation?location.genes.symbol={sym}  → anotaciones por gen
  - /clinicalAnnotation?relatedChemicals.name={name} → anotaciones por fármaco

Códigos de respuesta, y por qué importan:
  - 200 → resultados en `data`
  - 404 + "No results matching criteria." → **sin resultados, no es un error**
  - 400 + "No such property: 'x'"          → query mal formada: es un bug nuestro
  - 429 / 5xx / red                        → la API falló

Esa distinción es la que faltaba. La versión anterior atrapaba
`except (httpx.HTTPError, Exception)` y devolvía `[]` en todos los casos, así
que un host inexistente y un gen sin anotaciones eran indistinguibles: el
cliente "funcionaba" sin haber hablado nunca con PharmGKB.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .rate_limiter import ExternalApiError, pharmgkb_limiter

_API_NAME = "PharmGKB/ClinPGx"
_BASE_URL = "https://api.clinpgx.org/v1/data"
_GENE_URL = "https://www.clinpgx.org/gene/{id}"
_DRUG_URL = "https://www.clinpgx.org/chemical/{id}"
_ANNOTATION_URL = "https://www.clinpgx.org/clinicalAnnotation/{id}"

# Escala de evidencia de PharmGKB, de más fuerte a más débil.
_EVIDENCE_ORDER = {"1A": 0, "1B": 1, "2A": 2, "2B": 3, "3": 4, "4": 5}


@dataclass
class GeneAnnotation:
    """Relación entre un gen y un fármaco con su nivel de evidencia clínica."""

    gene_symbol: str
    drug_name: str
    phenotype: str
    evidence_level: str        # 1A, 1B, 2A, 2B, 3, 4 (escala PharmGKB)
    variant: str = ""
    population: str = ""
    url: str = ""

    def to_context_str(self) -> str:
        """Formatea la anotación para incluir en el contexto de un agente."""
        return (
            f"Gen {self.gene_symbol} + {self.drug_name}: "
            f"{self.phenotype or 'fenotipo no especificado'} "
            f"(Variante: {self.variant or 'no especificada'}, "
            f"Evidencia PharmGKB: {self.evidence_level or 'sin nivel'})"
        )


@dataclass
class DrugGeneInteraction:
    """Resumen de las interacciones fármaco-gen de un medicamento."""

    drug_name: str
    pharmgkb_id: str
    genes: list[str] = field(default_factory=list)
    annotations: list[GeneAnnotation] = field(default_factory=list)
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url and self.pharmgkb_id:
            self.url = _DRUG_URL.format(id=self.pharmgkb_id)

    def summary(self) -> str:
        """Resumen de interacciones para el contexto de un agente."""
        if not self.annotations:
            return f"{self.drug_name}: sin anotaciones farmacogenómicas en PharmGKB."
        lines = [f"{self.drug_name} — interacciones farmacogenómicas:"]
        for ann in self.annotations[:5]:
            lines.append(f"  • {ann.to_context_str()}")
        return "\n".join(lines)


def _sort_key(annotation: GeneAnnotation) -> int:
    """Ordena por fuerza de evidencia; los niveles desconocidos van al final."""
    return _EVIDENCE_ORDER.get(annotation.evidence_level, len(_EVIDENCE_ORDER))


def _parse_annotation(item: dict[str, Any], gene_symbol: str = "") -> GeneAnnotation:
    """
    Construye un GeneAnnotation desde un registro de /clinicalAnnotation.

    Los nombres de campo están verificados contra la API real. La versión
    anterior leía `evidenceLevel`, `phenotypeCategories`, `variant` y `url`, y
    ninguno de los cuatro existe en la respuesta: todas las anotaciones habrían
    salido vacías incluso si el host hubiera resuelto.
    """
    location = item.get("location") or {}
    genes = location.get("genes") or []
    simbolo = gene_symbol or (genes[0].get("symbol", "") if genes else "")

    chemicals = item.get("relatedChemicals") or []
    diseases = item.get("relatedDiseases") or []
    accession = item.get("accessionId", "")

    return GeneAnnotation(
        gene_symbol=simbolo,
        drug_name=chemicals[0].get("name", "") if chemicals else "",
        phenotype=", ".join(d.get("name", "") for d in diseases if d.get("name")),
        evidence_level=(item.get("levelOfEvidence") or {}).get("term", ""),
        variant=location.get("displayName") or "",
        url=_ANNOTATION_URL.format(id=accession) if accession else "",
    )


def _extract_error(response: httpx.Response) -> str:
    """Saca el mensaje de error del cuerpo JSON de la API, si lo trae."""
    try:
        errores = response.json().get("data", {}).get("errors", [])
        if errores:
            return str(errores[0].get("message", ""))
    except ValueError:
        pass
    return response.text[:120]


class PharmGKBClient:
    """
    Cliente asíncrono para la API de PharmGKB/ClinPGx.

    A diferencia de la versión anterior, **no** silencia los errores: un fallo
    real de la API levanta ExternalApiError. "Sin resultados" se distingue de
    "falló" y devuelve una lista vacía.

    Uso básico:
        async with PharmGKBClient() as client:
            annotations = await client.get_gene_annotations("CYP2D6")
            interactions = await client.get_drug_interactions("warfarin")
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "PharmGKBClient":
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """
        Hace una consulta y devuelve la lista `data`, o [] si no hubo resultados.

        Raises:
            ExternalApiError: ante un fallo real de la API (400, 429, 5xx, red).
                              Un 404 NO es un fallo: significa "sin resultados".
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        # Limitador compartido de rate_limiter.py, no uno propio: así el límite
        # se respeta aunque haya varios PharmGKBClient en vuelo a la vez.
        await pharmgkb_limiter.acquire()

        try:
            response = await self._client.get(f"{_BASE_URL}{path}", params=params)
        except httpx.HTTPError as exc:
            # Incluye el caso del host inexistente: httpx.ConnectError por DNS.
            raise ExternalApiError(
                _API_NAME, f"No se pudo consultar {path}: {exc}"
            ) from exc

        if response.status_code == 404:
            return []

        if response.status_code != 200:
            raise ExternalApiError(
                _API_NAME,
                f"{path} devolvió: {_extract_error(response)}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió un cuerpo que no es JSON"
            ) from exc

        data = payload.get("data")
        return data if isinstance(data, list) else []

    async def get_gene_annotations(
        self,
        gene_symbol: str,
        max_results: int = 10,
    ) -> list[GeneAnnotation]:
        """
        Trae anotaciones clínicas de un gen (relaciones gen-fármaco-fenotipo).

        Args:
            gene_symbol: Símbolo del gen (ej: "TTR", "CYP2D6")
            max_results: Máximo de anotaciones a devolver. La API no pagina del
                         lado del servidor (`pageSize` da HTTP 400), así que el
                         recorte se hace acá, después de ordenar por evidencia.

        Returns:
            Lista ordenada por fuerza de evidencia. Vacía si el gen no tiene
            anotaciones, que no es lo mismo que un fallo: eso levanta excepción.
        """
        items = await self._request(
            "/clinicalAnnotation",
            {"location.genes.symbol": gene_symbol, "view": "max"},
        )
        annotations = [_parse_annotation(item, gene_symbol) for item in items]
        annotations.sort(key=_sort_key)
        return annotations[:max_results]

    async def get_drug_interactions(
        self,
        drug_name: str,
        max_results: int = 10,
    ) -> Optional[DrugGeneInteraction]:
        """
        Busca un fármaco y devuelve sus interacciones farmacogenómicas.

        Args:
            drug_name: Nombre INN del fármaco (ej: "warfarin", "patisiran")
            max_results: Máximo de anotaciones a incluir.

        Returns:
            DrugGeneInteraction, o None si el fármaco no está en PharmGKB.

        Raises:
            ExternalApiError: ante un fallo real de la API.
        """
        chemicals = await self._request("/chemical", {"name": drug_name, "view": "base"})
        if not chemicals:
            return None

        drug_id = chemicals[0].get("id", "")

        items = await self._request(
            "/clinicalAnnotation",
            {"relatedChemicals.name": drug_name, "view": "max"},
        )

        annotations: list[GeneAnnotation] = []
        genes_seen: set[str] = set()
        for item in items:
            annotation = _parse_annotation(item)
            if annotation.gene_symbol:
                genes_seen.add(annotation.gene_symbol)
            # El nombre con el que se consultó manda si la cita no trae ninguno.
            annotation.drug_name = annotation.drug_name or drug_name
            annotations.append(annotation)

        annotations.sort(key=_sort_key)

        return DrugGeneInteraction(
            drug_name=drug_name,
            pharmgkb_id=drug_id,
            genes=sorted(genes_seen),
            annotations=annotations[:max_results],
        )

    async def get_gene_id(self, symbol: str) -> Optional[str]:
        """
        Resuelve el símbolo de un gen a su Accession ID de PharmGKB.

        Args:
            symbol: Símbolo del gen (ej: "TTR", "CYP2D6")

        Returns:
            El ID (ej: "PA128" para CYP2D6), o None si el gen no existe.

        Raises:
            ExternalApiError: ante un fallo real de la API.
        """
        genes = await self._request("/gene", {"symbol": symbol, "view": "base"})
        return genes[0].get("id") if genes else None

    async def get_gene_url(self, symbol: str) -> Optional[str]:
        """Devuelve la URL pública del gen en ClinPGx, o None si no existe."""
        gene_id = await self.get_gene_id(symbol)
        return _GENE_URL.format(id=gene_id) if gene_id else None

    async def get_multi_gene_annotations(
        self,
        gene_symbols: list[str],
    ) -> dict[str, list[GeneAnnotation]]:
        """
        Trae anotaciones de varios genes en paralelo.

        Útil para el Agente 02 cuando el caso tiene varios genes alterados. Acá
        sí interesa el resultado parcial: un gen que falla no tumba a los demás,
        queda con lista vacía y el error se reporta por stderr. Es la única
        excepción a "los fallos se propagan", y es deliberada.

        Returns:
            Dict {símbolo: [anotaciones]}
        """
        results = await asyncio.gather(
            *[self.get_gene_annotations(sym) for sym in gene_symbols],
            return_exceptions=True,
        )

        output: dict[str, list[GeneAnnotation]] = {}
        for symbol, result in zip(gene_symbols, results):
            if isinstance(result, BaseException):
                print(
                    f"[NEXUS][PharmGKB] Anotaciones de {symbol} no disponibles: {result}",
                    file=sys.stderr,
                )
                output[symbol] = []
            else:
                output[symbol] = result
        return output
