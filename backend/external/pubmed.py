"""
Cliente para PubMed E-utilities (NCBI).

Documentación oficial: https://www.ncbi.nlm.nih.gov/books/NBK25501/
Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
Autenticación: PUBMED_API_KEY en .env (opcional — aumenta rate limit de 3 a 10 req/s)

Endpoints usados:
  - esearch.fcgi  → busca PMIDs por query
  - efetch.fcgi   → trae resumen/abstract de una lista de PMIDs
  - esummary.fcgi → trae metadatos (título, revista, año, autores)
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_PUBMED_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

# Pausa entre reintentos: 2s → 4s → 8s (máx 3 intentos)
_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)


@dataclass
class PubMedArticle:
    """Representa un artículo de PubMed con sus metadatos esenciales."""

    pmid: str
    title: str
    abstract: str
    journal: str
    year: str
    authors: list[str] = field(default_factory=list)
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = _PUBMED_URL_TEMPLATE.format(pmid=self.pmid)

    def citation(self) -> str:
        """Devuelve una cita corta estilo Vancouver."""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += " et al."
        return f"{authors_str}. {self.title}. {self.journal}. {self.year}. PMID: {self.pmid}"


class PubMedClient:
    """
    Cliente asíncrono para PubMed E-utilities.

    Uso básico:
        async with PubMedClient() as client:
            articles = await client.search("TTR amyloidosis neuropathy", max_results=5)
    """

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.getenv("PUBMED_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "PubMedClient":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    def _base_params(self) -> dict[str, str]:
        """Parámetros comunes a todos los endpoints."""
        params: dict[str, str] = {"retmode": "json"}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    @retry(**_RETRY_KWARGS)
    async def _esearch(self, query: str, max_results: int) -> list[str]:
        """
        Busca en PubMed y devuelve lista de PMIDs.

        Args:
            query: Query en formato PubMed (ej: "TTR[Gene] AND neuropathy[MeSH]")
            max_results: Cantidad máxima de resultados

        Returns:
            Lista de PMIDs como strings
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        params = self._base_params()
        params.update({
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "sort": "relevance",
            "retmode": "json",
        })

        response = await self._client.get(f"{_BASE_URL}/esearch.fcgi", params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])

    @retry(**_RETRY_KWARGS)
    async def _efetch_abstracts(self, pmids: list[str]) -> dict[str, str]:
        """
        Trae abstracts de una lista de PMIDs vía efetch (XML).

        Args:
            pmids: Lista de PMIDs

        Returns:
            Dict {pmid: abstract_text}
        """
        assert self._client is not None, "Usar dentro de un bloque async with"
        if not pmids:
            return {}

        params = self._base_params()
        params.update({
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml",
        })
        # efetch devuelve XML — sobreescribimos retmode
        params["retmode"] = "xml"

        response = await self._client.get(f"{_BASE_URL}/efetch.fcgi", params=params)
        response.raise_for_status()

        return _parse_abstracts_xml(response.text)

    @retry(**_RETRY_KWARGS)
    async def _esummary(self, pmids: list[str]) -> dict[str, dict]:
        """
        Trae metadatos (título, revista, año, autores, tipos de publicación)
        de una lista de PMIDs.

        Los tipos de publicación (`pubtype`: "Meta-Analysis", "Case Reports",
        etc.) vienen en la misma respuesta: usarlos no agrega consultas. Los
        consume la clasificación de evidencia (backend/pipeline/evidence.py).

        Args:
            pmids: Lista de PMIDs

        Returns:
            Dict {pmid: {title, journal, year, authors, pubtypes}}
        """
        assert self._client is not None, "Usar dentro de un bloque async with"
        if not pmids:
            return {}

        params = self._base_params()
        params.update({
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
        })

        response = await self._client.get(f"{_BASE_URL}/esummary.fcgi", params=params)
        response.raise_for_status()

        data = response.json()
        result: dict[str, dict] = {}
        for pmid, doc in data.get("result", {}).items():
            if pmid == "uids":
                continue
            authors = [
                a.get("name", "") for a in doc.get("authors", [])
            ]
            result[pmid] = {
                "title": doc.get("title", ""),
                "journal": doc.get("fulljournalname", doc.get("source", "")),
                "year": doc.get("pubdate", "")[:4],
                "authors": authors,
                "pubtypes": [str(t) for t in doc.get("pubtype", []) if t],
            }
        return result

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[PubMedArticle]:
        """
        Busca artículos en PubMed y devuelve lista de PubMedArticle con abstract.

        Args:
            query: Query de búsqueda (texto libre o sintaxis PubMed)
            max_results: Cantidad máxima de artículos a devolver (default: 5)

        Returns:
            Lista de PubMedArticle ordenados por relevancia
        """
        pmids = await self._esearch(query, max_results)
        if not pmids:
            return []

        summaries, abstracts = await _gather(
            self._esummary(pmids),
            self._efetch_abstracts(pmids),
        )

        articles: list[PubMedArticle] = []
        for pmid in pmids:
            meta = summaries.get(pmid, {})
            abstract = abstracts.get(pmid, "")
            articles.append(PubMedArticle(
                pmid=pmid,
                title=meta.get("title", "Sin título"),
                abstract=abstract,
                journal=meta.get("journal", ""),
                year=meta.get("year", ""),
                authors=meta.get("authors", []),
            ))

        return articles

    async def fetch_by_pmid(self, pmid: str) -> Optional[PubMedArticle]:
        """
        Trae un artículo específico por PMID.

        Args:
            pmid: PMID del artículo

        Returns:
            PubMedArticle o None si no existe
        """
        summaries, abstracts = await _gather(
            self._esummary([pmid]),
            self._efetch_abstracts([pmid]),
        )
        meta = summaries.get(pmid)
        if not meta:
            return None

        return PubMedArticle(
            pmid=pmid,
            title=meta.get("title", "Sin título"),
            abstract=abstracts.get(pmid, ""),
            journal=meta.get("journal", ""),
            year=meta.get("year", ""),
            authors=meta.get("authors", []),
        )

    async def verify_pmid(self, pmid: str) -> bool:
        """
        Verifica si un PMID existe en PubMed.

        OJO: la existencia no alcanza para validar una cita. Los LLM alucinan
        PMIDs que existen pero corresponden a otro artículo. Para verificar de
        verdad una referencia usar `fetch_metadata()` y comparar el título
        (ver backend/pipeline/verification.py, Agente 04).

        Args:
            pmid: PMID a verificar

        Returns:
            True si existe, False si no
        """
        result = await self._esummary([pmid])
        return pmid in result

    async def fetch_metadata(self, pmids: list[str]) -> dict[str, dict]:
        """
        Trae metadatos de varios PMIDs en una sola consulta (batch).

        Args:
            pmids: Lista de PMIDs a consultar

        Returns:
            Dict {pmid: {title, journal, year, authors, pubtypes}}. Los PMIDs
            que no existen simplemente no aparecen en el dict devuelto.
        """
        return await self._esummary(pmids)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _parse_abstracts_xml(xml_text: str) -> dict[str, str]:
    """
    Parsea XML de efetch y extrae abstracts por PMID.

    Args:
        xml_text: Respuesta XML de efetch

    Returns:
        Dict {pmid: abstract_text}
    """
    result: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None or pmid_el.text is None:
                continue
            pmid = pmid_el.text.strip()

            # Algunos abstracts tienen múltiples secciones (AbstractText con Label)
            abstract_parts: list[str] = []
            for abstract_el in article.findall(".//AbstractText"):
                label = abstract_el.get("Label")
                text = abstract_el.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)

            result[pmid] = " ".join(abstract_parts).strip()
    except ET.ParseError:
        pass  # XML malformado — devolvemos lo que tengamos
    return result


async def _gather(coro1, coro2):
    """Ejecuta dos coroutines en paralelo."""
    import asyncio
    return await asyncio.gather(coro1, coro2)
