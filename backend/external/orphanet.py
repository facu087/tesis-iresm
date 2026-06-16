"""
Cliente para Orphanet API (ORDO — Orphanet Rare Disease Ontology).

Documentación oficial: https://api.orphacode.org/
Base URL: https://api.orphacode.org/EN/ClinicalEntity
Autenticación: ORPHANET_API_KEY en header "apiKey" — requiere registro en orphanet.org

Endpoints usados:
  - /orphacode/{code}          → datos de enfermedad por código ORPHA
  - /approximatelymatching     → búsqueda por nombre aproximado
  - /DisorderGene/{code}       → genes asociados a una enfermedad
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_BASE_URL = "https://api.orphacode.org/EN/ClinicalEntity"
_ORPHANET_URL_TEMPLATE = "https://www.orpha.net/en/disease/detail/{code}"

_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)


@dataclass
class RareDisease:
    """Representa una enfermedad rara de Orphanet."""

    orpha_code: str
    name: str
    definition: str
    genes: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = _ORPHANET_URL_TEMPLATE.format(code=self.orpha_code)

    def summary(self) -> str:
        """Resumen corto para incluir en el contexto de un agente."""
        genes_str = ", ".join(self.genes[:5]) if self.genes else "no especificados"
        return (
            f"{self.name} (ORPHA:{self.orpha_code}). "
            f"Genes asociados: {genes_str}. "
            f"{self.definition[:200]}..."
        )


class OrphanetClient:
    """
    Cliente asíncrono para Orphanet API.

    Uso básico:
        async with OrphanetClient() as client:
            diseases = await client.search("transthyretin amyloidosis")
    """

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.getenv("ORPHANET_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OrphanetClient":
        headers = {}
        if self._api_key:
            headers["apiKey"] = self._api_key
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    @retry(**_RETRY_KWARGS)
    async def search(self, name: str, max_results: int = 5) -> list[RareDisease]:
        """
        Busca enfermedades raras por nombre aproximado.

        Args:
            name: Nombre o término de búsqueda
            max_results: Cantidad máxima de resultados

        Returns:
            Lista de RareDisease ordenada por relevancia
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        try:
            response = await self._client.get(
                f"{_BASE_URL}/approximatelymatching",
                params={"name": name},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, Exception):
            return []

        diseases: list[RareDisease] = []
        items = data if isinstance(data, list) else data.get("data", [])

        for item in items[:max_results]:
            orpha_code = str(item.get("OrphaCode", ""))
            disease_name = item.get("Preferred term", item.get("Name", ""))
            definition = item.get("Definition", "")
            synonyms = [s.get("Synonym", "") for s in item.get("Synonyms", [])]

            diseases.append(RareDisease(
                orpha_code=orpha_code,
                name=disease_name,
                definition=definition,
                synonyms=synonyms,
            ))

        return diseases

    @retry(**_RETRY_KWARGS)
    async def get_by_code(self, orpha_code: str) -> Optional[RareDisease]:
        """
        Trae una enfermedad rara por código ORPHA.

        Args:
            orpha_code: Código ORPHA numérico (ej: "85163" para TTR amiloidosis)

        Returns:
            RareDisease o None si no existe
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        try:
            response = await self._client.get(
                f"{_BASE_URL}/orphacode/{orpha_code}",
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, Exception):
            return None

        if not data:
            return None

        # Busca genes asociados en llamada separada
        genes = await self._get_genes(orpha_code)

        return RareDisease(
            orpha_code=orpha_code,
            name=data.get("Preferred term", ""),
            definition=data.get("Definition", ""),
            synonyms=[s.get("Synonym", "") for s in data.get("Synonyms", [])],
            genes=genes,
        )

    @retry(**_RETRY_KWARGS)
    async def _get_genes(self, orpha_code: str) -> list[str]:
        """
        Trae los genes asociados a una enfermedad por código ORPHA.

        Args:
            orpha_code: Código ORPHA numérico

        Returns:
            Lista de símbolos de genes (ej: ["TTR", "ATTR"])
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        try:
            response = await self._client.get(
                f"{_BASE_URL}/DisorderGene/{orpha_code}",
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, Exception):
            return []

        genes: list[str] = []
        gene_list = data if isinstance(data, list) else data.get("data", [])
        for item in gene_list:
            symbol = item.get("Gene symbol", item.get("Symbol", ""))
            if symbol:
                genes.append(symbol)

        return genes

    async def enrich_with_genes(self, disease: RareDisease) -> RareDisease:
        """
        Enriquece un RareDisease con sus genes asociados si no los tiene.

        Args:
            disease: Objeto RareDisease a enriquecer

        Returns:
            El mismo objeto con genes poblados
        """
        if not disease.genes and disease.orpha_code:
            disease.genes = await self._get_genes(disease.orpha_code)
        return disease
