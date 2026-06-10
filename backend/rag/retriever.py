"""
Motor RAG: búsqueda semántica y formateo para prompts de agentes.

Este módulo es el corazón del sistema RAG de NEXUS. Dado un query clínico,
busca los artículos más relevantes en ChromaDB y los formatea como contexto
listo para incluir en el prompt de un agente.

Flujo:
  1. Query semántico → ChromaDB devuelve top-K artículos por similitud coseno
  2. Filtrado por score mínimo de relevancia
  3. Formateo en texto estructurado para el prompt del agente

Ejemplo de uso:
    retriever = PubMedRetriever()
    context = retriever.get_context_for_agent(
        query="TTR amyloidosis neuropathy patisiran treatment",
        max_results=5,
    )
    # context es un string listo para pegar en el prompt del agente
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import chromadb

from backend.rag.chroma_store import get_pubmed_collection

# Score mínimo de similitud coseno (0–1). Por debajo de este umbral,
# el artículo se considera irrelevante para el query.
_MIN_RELEVANCE_SCORE = 0.3


@dataclass
class RetrievedArticle:
    """Artículo recuperado de ChromaDB con su score de relevancia."""

    pmid: str
    title: str
    journal: str
    year: str
    authors: str
    url: str
    excerpt: str          # Primeros N caracteres del abstract indexado
    relevance_score: float  # 0.0 (irrelevante) → 1.0 (idéntico)

    def to_citation(self) -> str:
        """Cita corta estilo Vancouver para incluir en el reporte."""
        return f"{self.authors}. {self.title}. {self.journal}. {self.year}. PMID: {self.pmid}"

    def to_prompt_block(self) -> str:
        """Bloque de texto formateado para incluir en el prompt de un agente."""
        return (
            f"[PMID: {self.pmid}] {self.title}\n"
            f"Revista: {self.journal} ({self.year})\n"
            f"Relevancia: {self.relevance_score:.2f}\n"
            f"Resumen: {self.excerpt[:400]}"
        )


class PubMedRetriever:
    """
    Motor de recuperación semántica sobre la colección ChromaDB de PubMed.

    Provee métodos para buscar artículos relevantes y formatear el contexto
    listo para ser incluido en prompts de agentes.

    Uso:
        retriever = PubMedRetriever()
        articles = retriever.search("TTR amyloidosis treatment", max_results=5)
        context = retriever.get_context_for_agent("TTR neuropathy", max_results=3)
    """

    def __init__(self, collection: Optional[chromadb.Collection] = None) -> None:
        self._collection = collection

    def _get_collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = get_pubmed_collection()
        return self._collection

    def search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = _MIN_RELEVANCE_SCORE,
    ) -> list[RetrievedArticle]:
        """
        Busca artículos relevantes en ChromaDB por similitud semántica.

        Args:
            query: Texto de búsqueda (puede ser lenguaje natural o términos médicos)
            max_results: Máximo de resultados a devolver
            min_score: Score mínimo de relevancia (0–1)

        Returns:
            Lista de RetrievedArticle ordenados por relevancia descendente
        """
        collection = self._get_collection()

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(max_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        articles: list[RetrievedArticle] = []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, distance in zip(documents, metadatas, distances):
            # ChromaDB devuelve distancia coseno (0=idéntico, 2=opuesto)
            # Convertir a score de similitud (0–1)
            score = 1.0 - (distance / 2.0)

            if score < min_score:
                continue

            articles.append(RetrievedArticle(
                pmid=meta.get("pmid", ""),
                title=meta.get("title", ""),
                journal=meta.get("journal", ""),
                year=meta.get("year", ""),
                authors=meta.get("authors", ""),
                url=meta.get("url", ""),
                excerpt=doc[:500],
                relevance_score=round(score, 3),
            ))

        return articles

    def get_context_for_agent(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = _MIN_RELEVANCE_SCORE,
    ) -> str:
        """
        Genera un bloque de contexto bibliográfico listo para un prompt de agente.

        Si no hay artículos relevantes, devuelve un mensaje indicando que
        no hay evidencia disponible en la base local (no bloquea al agente).

        Args:
            query: Query clínico para buscar literatura relevante
            max_results: Máximo de artículos a incluir en el contexto
            min_score: Score mínimo de relevancia

        Returns:
            String con los artículos formateados para el prompt
        """
        articles = self.search(query, max_results=max_results, min_score=min_score)

        if not articles:
            return (
                "LITERATURA CIENTÍFICA DISPONIBLE:\n"
                "No se encontraron artículos relevantes en la base local de PubMed. "
                "Basá tus hipótesis en tu conocimiento clínico y marcá las fuentes "
                "con evidence_level: 'III' si no tenés respaldo bibliográfico verificado."
            )

        lines = ["LITERATURA CIENTÍFICA RELEVANTE (fuente: PubMed):"]
        for i, article in enumerate(articles, 1):
            lines.append(f"\n--- Referencia {i} ---")
            lines.append(article.to_prompt_block())

        lines.append(
            "\nINSTRUCCIÓN: Cuando cites estas referencias, usá el PMID exacto "
            "provisto. No inventes PMIDs adicionales."
        )

        return "\n".join(lines)

    def get_pmids_for_hypothesis(
        self,
        hypothesis_text: str,
        max_results: int = 3,
    ) -> list[str]:
        """
        Devuelve PMIDs reales para respaldar una hipótesis específica.

        Útil para el Árbitro Verificador (Agente 04) cuando necesita
        asignar referencias verificables a cada hipótesis.

        Args:
            hypothesis_text: Texto de la hipótesis a respaldar
            max_results: Máximo de PMIDs a devolver

        Returns:
            Lista de PMIDs reales (pueden ser vacía si no hay evidencia)
        """
        articles = self.search(
            hypothesis_text,
            max_results=max_results,
            min_score=0.35,  # Umbral más alto para hipótesis específicas
        )
        return [a.pmid for a in articles]

    def collection_size(self) -> int:
        """Devuelve la cantidad de artículos indexados."""
        return self._get_collection().count()
