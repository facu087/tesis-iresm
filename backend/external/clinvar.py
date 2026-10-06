"""
Cliente de ClinVar (NCBI E-utilities, base `clinvar`).

Dada una variante y el símbolo de su gen, devuelve la clasificación germinal de
ClinVar con su accession `VCV` verificable. Lo consume el contexto genómico del
Agente 02 (`pipeline/genomic_context.py`) cuando el caso trae variantes.

Coincidencia verificada: ClinVar busca por texto y la notación clásica de una
variante trae registros de otras. Medido el 2026-10-06: `TTR[gene] AND Val30Met`
devuelve 5 registros y uno es `p.Phe53Leu`; `c.148G>A` y `p.Val50Met` devuelven
solo `VCV000013417`. Por eso se acepta un registro únicamente si su título
contiene la notación consultada y su lista de genes contiene el gen; si no, el
resultado es `ambigua` y nunca se elige el primero de la lista.

Cupo: ClinVar y PubMed son el mismo servicio de NCBI, así que comparten
`pubmed_limiter` y `pubmed_breaker`.

Privacidad: a NCBI solo viajan el gen y la notación de la variante. Los logs
registran el tipo de excepción, nunca datos del caso.
"""

from __future__ import annotations

import os
import re
import sys

import httpx

from ..models.genomics import ClinVarStatus, VariantClassification
from .rate_limiter import pubmed_breaker, pubmed_limiter

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_VARIATION_URL = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/"
_MAX_IDS = 5
_TIMEOUT_S = 10.0


class _ClinVarResponseError(Exception):
    """La respuesta de NCBI no tiene la forma esperada."""


def _notation_pattern(variant: str) -> re.Pattern[str]:
    """
    Patrón que encuentra la notación dentro del título de un registro, con o
    sin el prefijo `c.`/`p.`, sin aceptar que sea parte de otra (`48G>A` no
    coincide con `c.148G>A`).
    """
    core = re.sub(r"^[cpgnm]\.", "", variant.strip(), flags=re.IGNORECASE)
    return re.compile(
        rf"(?<![0-9A-Za-z])(?:[cpgnm]\.)?{re.escape(core)}(?![0-9A-Za-z])",
        re.IGNORECASE,
    )


def _matches(record: dict, gene: str, pattern: re.Pattern[str]) -> bool:
    genes = {g.get("symbol", "").upper() for g in record.get("genes", [])}
    return gene.upper() in genes and bool(pattern.search(record.get("title", "")))


def _classification(record: dict) -> dict:
    germline = record.get("germline_classification")
    if not isinstance(germline, dict) or not germline.get("description"):
        raise _ClinVarResponseError("registro sin germline_classification")
    return germline


def select(gene: str, variant: str, records: dict[str, dict]) -> VariantClassification:
    """
    Decide el resultado a partir de los registros de `esummary` (uid → registro).
    Determinista y sin red: es donde vive la coincidencia verificada.
    """
    if not records:
        return VariantClassification(gene=gene, variant=variant, status=ClinVarStatus.sin_resultados)

    pattern = _notation_pattern(variant)
    matching = {uid: r for uid, r in records.items() if _matches(r, gene, pattern)}
    classes = {uid: _classification(r) for uid, r in matching.items()}

    if not matching or len({c["description"] for c in classes.values()}) > 1:
        return VariantClassification(
            gene=gene, variant=variant, status=ClinVarStatus.ambigua,
            candidates=len(records),
            detail="ningún registro coincide con la notación y el gen"
            if not matching else "registros coincidentes con clasificaciones distintas",
        )

    uid = max(classes, key=lambda u: classes[u].get("last_evaluated", ""))
    rec, cls = matching[uid], classes[uid]
    return VariantClassification(
        gene=gene, variant=variant, status=ClinVarStatus.encontrada,
        classification=cls["description"],
        review_status=cls.get("review_status", ""),
        last_evaluated=(cls.get("last_evaluated") or "").split(" ")[0],
        accession=rec.get("accession", ""),
        url=_VARIATION_URL.format(uid=uid),
        title=rec.get("title", ""),
        candidates=len(records),
    )


class ClinVarClient:
    """Cliente async de ClinVar. Usar como `async with ClinVarClient() as c:`."""

    def __init__(self) -> None:
        self._api_key = os.getenv("PUBMED_API_KEY")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ClinVarClient":
        self._client = httpx.AsyncClient(timeout=_TIMEOUT_S)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    def _params(self, **extra: str) -> dict[str, str]:
        params = {"db": "clinvar", "retmode": "json", **extra}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def _get(self, endpoint: str, params: dict[str, str]) -> dict:
        assert self._client is not None, "usar ClinVarClient dentro de `async with`"
        async with pubmed_breaker:
            async with pubmed_limiter:
                response = await self._client.get(f"{_BASE_URL}/{endpoint}", params=params)
            if response.status_code != 200:
                raise _ClinVarResponseError(f"HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise _ClinVarResponseError("respuesta no es JSON") from exc

    async def classify(self, gene: str, variant: str) -> VariantClassification:
        """Clasificación de ClinVar para `variant` de `gene`. Nunca propaga excepciones."""
        try:
            term = f'"{gene}"[gene] AND "{variant}"'
            found = await self._get("esearch.fcgi", self._params(term=term, retmax=str(_MAX_IDS)))
            ids = found["esearchresult"]["idlist"]
            if not ids:
                return select(gene, variant, {})
            summary = await self._get("esummary.fcgi", self._params(id=",".join(ids)))
            result = summary["result"]
            return select(gene, variant, {uid: result[uid] for uid in result.get("uids", [])})
        except Exception as exc:
            print(f"[NEXUS] ClinVar no disponible: {type(exc).__name__}", file=sys.stderr)
            return VariantClassification(
                gene=gene, variant=variant, status=ClinVarStatus.no_disponible,
                detail=type(exc).__name__,
            )
