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

import os
import sys
from dataclasses import dataclass
from typing import Optional

import chromadb

from backend.rag.chroma_store import get_pubmed_collection

_ENV_MIN_SCORE_VAR = "NEXUS_RAG_MIN_SCORE"

# Score mínimo por debajo del cual un artículo se descarta por irrelevante.
#
# OJO con la escala: el score NO es la similitud coseno. ChromaDB devuelve
# distancia coseno en [0, 2] y acá se convierte con `1 - distancia/2`, o sea
# `score = (1 + coseno) / 2`. Un score de 0,5 es coseno 0, y el 0,3 que estaba
# antes equivale a un coseno de **-0,4**: para texto biomédico eso no filtraba
# absolutamente nada (medido: 0 de 15 resultados quedaban por debajo).
#
# Medido el 2026-10-06 con scripts/demo_umbral_relevancia.py sobre el corpus de
# scripts/demo_embeddings_comparacion.py (7 artículos de neuropatía + 1 fuera de
# dominio como control) y las tres queries del caso de la tesis:
#
#   modelo                         control (máx)   relevante (mín)
#   NeuML/pubmedbert-base-embed.       0,536            0,606
#   all-MiniLM-L6-v2 (fallback)        0,549            0,571
#
# 0,55 es el único valor que separa con los dos modelos: descarta el artículo
# fuera de dominio en las tres queries y no pierde ni un artículo relevante.
#
# Limitación: la banda sale de UN artículo de control. Es evidencia suficiente
# para dejar de usar un umbral inerte, no para afinarlo. Por eso se puede
# sobreescribir sin tocar código:
#
#     NEXUS_RAG_MIN_SCORE=0.6 python3 scripts/demo_motor_rag.py
#
# Al cambiar de modelo de embeddings hay que volver a medir: el umbral depende
# del modelo, igual que los vectores.
_DEFAULT_MIN_RELEVANCE_SCORE = 0.55


def _resolver_min_score() -> float:
    """
    Lee el umbral del entorno, con el default medido como respaldo.

    Un valor inválido o fuera de [0, 1] no rompe el pipeline: se avisa por
    stderr y se usa el default, igual que hace chroma_store con el modelo.
    """
    crudo = os.getenv(_ENV_MIN_SCORE_VAR)
    if not crudo:
        return _DEFAULT_MIN_RELEVANCE_SCORE
    try:
        valor = float(crudo)
    except ValueError:
        print(
            f"[NEXUS][RAG] {_ENV_MIN_SCORE_VAR}={crudo!r} no es un número: "
            f"se usa {_DEFAULT_MIN_RELEVANCE_SCORE}.",
            file=sys.stderr,
        )
        return _DEFAULT_MIN_RELEVANCE_SCORE
    if not 0.0 <= valor <= 1.0:
        print(
            f"[NEXUS][RAG] {_ENV_MIN_SCORE_VAR}={valor} está fuera de [0, 1]: "
            f"se usa {_DEFAULT_MIN_RELEVANCE_SCORE}.",
            file=sys.stderr,
        )
        return _DEFAULT_MIN_RELEVANCE_SCORE
    return valor


_MIN_RELEVANCE_SCORE = _resolver_min_score()


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

    def get_context_with_articles(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = _MIN_RELEVANCE_SCORE,
    ) -> tuple[str, list[RetrievedArticle]]:
        """
        Igual que `get_context_for_agent()`, pero devuelve también los artículos.

        El contexto formateado alcanza para el prompt, pero el Árbitro (Agente 04)
        necesita los objetos: con ellos mide cuántas de las citas de los agentes
        salieron de la literatura que se les ofreció, y arma la ronda de
        recitación sobre PMIDs reales. Antes se descartaban.

        Args:
            query: Query clínico para buscar literatura relevante
            max_results: Máximo de artículos a incluir en el contexto
            min_score: Score mínimo de relevancia

        Returns:
            (contexto formateado para el prompt, artículos recuperados). La lista
            queda vacía si no hubo resultados relevantes.
        """
        articles = self.search(query, max_results=max_results, min_score=min_score)

        if not articles:
            return (
                "LITERATURA CIENTÍFICA DISPONIBLE:\n"
                "No se encontraron artículos relevantes en la base local de PubMed. "
                "Basá tus hipótesis en tu conocimiento clínico y marcá las fuentes "
                "con evidence_level: 'III' si no tenés respaldo bibliográfico verificado."
            ), []

        lines = ["LITERATURA CIENTÍFICA RELEVANTE (fuente: PubMed):"]
        for i, article in enumerate(articles, 1):
            lines.append(f"\n--- Referencia {i} ---")
            lines.append(article.to_prompt_block())

        lines.append(
            "\nINSTRUCCIÓN: Cuando cites estas referencias, usá el PMID exacto "
            "provisto. No inventes PMIDs adicionales."
        )

        return "\n".join(lines), articles

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
        context, _ = self.get_context_with_articles(
            query, max_results=max_results, min_score=min_score
        )
        return context

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
        # Usa el mismo umbral medido que el resto del módulo. Antes tenía un
        # 0.35 propio, descrito como "más alto": con la escala real
        # (score = (1 + coseno) / 2) eso era coseno -0,3, aún más permisivo que
        # el default de entonces. Un umbral más estricto para hipótesis
        # puntuales es defendible, pero hay que medirlo antes de elegirlo.
        articles = self.search(
            hypothesis_text,
            max_results=max_results,
            min_score=_MIN_RELEVANCE_SCORE,
        )
        return [a.pmid for a in articles]

    def collection_size(self) -> int:
        """Devuelve la cantidad de artículos indexados."""
        return self._get_collection().count()
