"""
Cliente para PharmGKB API.

Documentación oficial: https://api.pharmgkb.org/v1/
Base URL: https://api.pharmgkb.org/v1
Autenticación: ninguna (API pública con rate limit generoso)

PharmGKB relaciona genes, variantes genéticas, fármacos y fenotipos clínicos.
Es clave para el Agente 02 (Especialista Genómica) cuando el caso tiene genes alterados.

Endpoints usados:
  - /gene?symbol={symbol}             → busca un gen por símbolo (ej: TTR, CYP2D6)
  - /chemical?name={name}             → busca un fármaco por nombre
  - /clinicalAnnotation?gene={id}     → anotaciones clínicas por gen
  - /variantAnnotation?gene={id}      → anotaciones de variantes por gen
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_BASE_URL = "https://api.pharmgkb.org/v1"
_PHARMGKB_GENE_URL = "https://www.pharmgkb.org/gene/{id}"
_PHARMGKB_DRUG_URL = "https://www.pharmgkb.org/chemical/{id}"

_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)


@dataclass
class GeneAnnotation:
    """Relación entre un gen y un fármaco con su nivel de evidencia clínica."""

    gene_symbol: str
    drug_name: str
    phenotype: str
    evidence_level: str        # 1A, 1B, 2A, 2B, 3, 4 (PharmGKB scale)
    variant: str = ""
    population: str = ""
    url: str = ""

    def to_context_str(self) -> str:
        """Formatea la anotación para incluir en el contexto de un agente."""
        return (
            f"Gen {self.gene_symbol} + {self.drug_name}: "
            f"{self.phenotype} "
            f"(Variante: {self.variant or 'no especificada'}, "
            f"Evidencia PharmGKB: {self.evidence_level})"
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
            self.url = _PHARMGKB_DRUG_URL.format(id=self.pharmgkb_id)

    def summary(self) -> str:
        """Resumen de interacciones para el contexto de un agente."""
        if not self.annotations:
            return f"{self.drug_name}: sin anotaciones farmacogenómicas en PharmGKB."
        lines = [f"{self.drug_name} — interacciones farmacogenómicas:"]
        for ann in self.annotations[:5]:
            lines.append(f"  • {ann.to_context_str()}")
        return "\n".join(lines)


class PharmGKBClient:
    """
    Cliente asíncrono para PharmGKB API.

    Uso básico:
        async with PharmGKBClient() as client:
            interactions = await client.get_drug_interactions("patisiran")
            annotations = await client.get_gene_annotations("TTR")
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

    @retry(**_RETRY_KWARGS)
    async def _get_gene_id(self, symbol: str) -> Optional[str]:
        """
        Resuelve el símbolo de un gen a su ID interno de PharmGKB.

        Args:
            symbol: Símbolo del gen (ej: "TTR", "CYP2D6")

        Returns:
            PharmGKB Accession ID o None
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        try:
            response = await self._client.get(
                f"{_BASE_URL}/gene",
                params={"symbol": symbol, "view": "base"},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data", [])
            if items:
                return items[0].get("id")
        except (httpx.HTTPError, Exception):
            pass
        return None

    @retry(**_RETRY_KWARGS)
    async def get_gene_annotations(
        self,
        gene_symbol: str,
        max_results: int = 10,
    ) -> list[GeneAnnotation]:
        """
        Trae anotaciones clínicas para un gen (relaciones gen-fármaco-fenotipo).

        Args:
            gene_symbol: Símbolo del gen (ej: "TTR", "CYP2D6", "BRCA1")
            max_results: Cantidad máxima de anotaciones

        Returns:
            Lista de GeneAnnotation ordenadas por nivel de evidencia
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        gene_id = await self._get_gene_id(gene_symbol)
        if not gene_id:
            return []

        try:
            response = await self._client.get(
                f"{_BASE_URL}/clinicalAnnotation",
                params={
                    "gene": gene_id,
                    "view": "base",
                    "pageSize": str(max_results),
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, Exception):
            return []

        annotations: list[GeneAnnotation] = []
        for item in data.get("data", []):
            drug = item.get("relatedChemicals", [{}])[0]
            drug_name = drug.get("name", "")
            phenotype_cats = item.get("phenotypeCategories", [])
            phenotype = ", ".join(phenotype_cats) if phenotype_cats else ""

            annotations.append(GeneAnnotation(
                gene_symbol=gene_symbol,
                drug_name=drug_name,
                phenotype=phenotype,
                evidence_level=item.get("evidenceLevel", ""),
                variant=item.get("variant", {}).get("name", "") if item.get("variant") else "",
                population=item.get("population", ""),
                url=item.get("url", ""),
            ))

        # Ordenar: evidencias 1A y 1B primero
        annotations.sort(key=lambda a: a.evidence_level)
        return annotations

    @retry(**_RETRY_KWARGS)
    async def get_drug_interactions(self, drug_name: str) -> Optional[DrugGeneInteraction]:
        """
        Busca un fármaco y devuelve sus interacciones farmacogenómicas.

        Args:
            drug_name: Nombre INN del fármaco (ej: "patisiran", "tafamidis")

        Returns:
            DrugGeneInteraction o None si no se encontró
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        # 1. Buscar el fármaco
        try:
            response = await self._client.get(
                f"{_BASE_URL}/chemical",
                params={"name": drug_name, "view": "base"},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data", [])
        except (httpx.HTTPError, Exception):
            return None

        if not items:
            return None

        drug = items[0]
        drug_id = drug.get("id", "")

        # 2. Buscar anotaciones clínicas del fármaco
        try:
            ann_response = await self._client.get(
                f"{_BASE_URL}/clinicalAnnotation",
                params={"chemical": drug_id, "view": "base", "pageSize": "10"},
            )
            ann_response.raise_for_status()
            ann_data = ann_response.json()
        except (httpx.HTTPError, Exception):
            ann_data = {"data": []}

        annotations: list[GeneAnnotation] = []
        genes_seen: set[str] = set()

        for item in ann_data.get("data", []):
            gene_list = item.get("relatedGenes", [])
            for gene in gene_list:
                symbol = gene.get("symbol", "")
                if symbol:
                    genes_seen.add(symbol)

            phenotype_cats = item.get("phenotypeCategories", [])
            phenotype = ", ".join(phenotype_cats) if phenotype_cats else ""
            gene_symbol = gene_list[0].get("symbol", "") if gene_list else ""

            annotations.append(GeneAnnotation(
                gene_symbol=gene_symbol,
                drug_name=drug_name,
                phenotype=phenotype,
                evidence_level=item.get("evidenceLevel", ""),
                variant=item.get("variant", {}).get("name", "") if item.get("variant") else "",
            ))

        return DrugGeneInteraction(
            drug_name=drug_name,
            pharmgkb_id=drug_id,
            genes=list(genes_seen),
            annotations=annotations,
        )

    async def get_multi_gene_annotations(
        self,
        gene_symbols: list[str],
    ) -> dict[str, list[GeneAnnotation]]:
        """
        Trae anotaciones para múltiples genes en paralelo.
        Útil para el Agente 02 cuando el caso tiene varios genes alterados.

        Args:
            gene_symbols: Lista de símbolos de genes

        Returns:
            Dict {símbolo: [anotaciones]}
        """
        import asyncio

        results = await asyncio.gather(
            *[self.get_gene_annotations(sym) for sym in gene_symbols],
            return_exceptions=True,
        )

        output: dict[str, list[GeneAnnotation]] = {}
        for symbol, result in zip(gene_symbols, results):
            if isinstance(result, list):
                output[symbol] = result
            else:
                output[symbol] = []

        return output
