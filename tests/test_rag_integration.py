"""
Tests de integración RAG → pipeline.

Verifica que _enrich_context_with_rag() enriquece el contexto de los agentes
con literatura PubMed y que el pipeline es resiliente ante fallos del RAG.
"""

import asyncio
import pytest

from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.pipeline.orchestrator import _enrich_context_with_rag
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import RetrievedArticleRef
from backend.pipeline.consensus import rag_overlap
from backend.rag.retriever import RetrievedArticle


def _make_case(with_biomarkers: bool = True) -> ClinicalCase:
    pico = PICOSynthesis(
        patient_profile="Masculino, 42 años",
        chief_complaint="Neuropatía axonal sensitivomotora progresiva",
        relevant_history=["Diabetes mellitus tipo 2"],
        negative_findings=["Panel CMT negativo"],
        disease_duration="18 meses",
        current_treatments=["pregabalina 150 mg/día"],
        procedures_done=["EMG"],
        comparison="Neuropatía diabética vs. amiloidosis hereditaria",
        primary_outcome="Etiología de neuropatía axonal",
        secondary_outcomes=["respuesta a tratamiento"],
        biomarkers=["HbA1c 8.2%"],
        genetic_findings=["Panel CMT negativo"],
        clinical_narrative="Paciente masculino 42 años con neuropatía axonal progresiva.",
    )
    case = ClinicalCase(raw_text="[texto clínico anonimizado]", pico=pico)
    if with_biomarkers:
        case.biomarkers = BiomarkerProfile(
            genes=["TTR"],
            drugs=["pregabalina"],
            lab_biomarkers=["HbA1c 8.2%"],
        )
    return case


# Bloque que devuelve el recuperador cuando la búsqueda funciona. El PMID es
# inventado a propósito: si aparece en el resultado, solo pudo venir de acá.
_LITERATURA_OK = (
    "LITERATURA CIENTÍFICA RELEVANTE (fuente: PubMed):\n"
    "--- Referencia 1 ---\n"
    "PMID: 99999901\n"
    "Título: Hereditary transthyretin amyloidosis presenting as axonal neuropathy\n"
    "\nINSTRUCCIÓN: Cuando cites estas referencias, usá el PMID exacto provisto."
)

# Los mismos artículos, como objetos: el orquestador los conserva en el Report
# para que el Árbitro pueda medir el solapamiento y armar la recitación.
_ARTICULOS_OK = [
    RetrievedArticle(
        pmid="99999901",
        title="Hereditary transthyretin amyloidosis presenting as axonal neuropathy",
        journal="J Peripher Nerv Syst",
        year="2021",
        authors="Autor A, Autor B",
        url="https://pubmed.ncbi.nlm.nih.gov/99999901/",
        excerpt="Hereditary ATTR amyloidosis is an underdiagnosed cause of…",
        relevance_score=0.87,
    )
]


class _RagFalso:
    """
    Sustituye la indexación y la búsqueda del RAG sin tocar la red.

    La versión anterior de estos tests llamaba a PubMed y cargaba PubMedBERT de
    verdad: medido con la red bloqueada, 89 intentos de conexión (39 a
    eutils.ncbi.nlm.nih.gov y 50 a huggingface.co) y 165 s en lugar de 4. Y
    pasaba igual con la red caída, porque el texto de fallback del orquestador
    también dice "LITERATURA CIENTÍFICA" y "evidence_level": las aserciones no
    distinguían un RAG que funciona de uno que no.
    """

    def __init__(self, indexacion_falla: bool = False, busqueda_falla: bool = False) -> None:
        self.indexacion_falla = indexacion_falla
        self.busqueda_falla = busqueda_falla
        self.indexado_con: dict | None = None
        self.query: str | None = None

    def instalar(self, monkeypatch) -> "_RagFalso":
        rag = self

        async def fake_index(genes, conditions, drugs):
            rag.indexado_con = {"genes": genes, "conditions": conditions, "drugs": drugs}
            if rag.indexacion_falla:
                raise ConnectionError("PubMed no disponible (simulado)")
            return {}

        class FakeRetriever:
            def get_context_with_articles(self, query, max_results=5):
                rag.query = query
                if rag.busqueda_falla:
                    raise ConnectionError("ChromaDB no disponible (simulado)")
                return _LITERATURA_OK, list(_ARTICULOS_OK)

        monkeypatch.setattr(
            "backend.pipeline.orchestrator.index_from_clinical_context", fake_index
        )
        monkeypatch.setattr(
            "backend.pipeline.orchestrator.PubMedRetriever", lambda: FakeRetriever()
        )
        return self


class TestEnrichContextWithRag:
    """
    Tests para _enrich_context_with_rag(). Herméticos: no tocan PubMed, ChromaDB
    ni HuggingFace.

    Cada test distingue el camino feliz del fallback. El marcador que lo permite
    es el PMID inventado de _LITERATURA_OK: solo puede estar en el resultado si
    la búsqueda funcionó.
    """

    def test_conserva_el_contexto_base(self, monkeypatch) -> None:
        _RagFalso().instalar(monkeypatch)
        base = "CONTEXTO PICO BASE de prueba"

        result, _ = asyncio.run(_enrich_context_with_rag(_make_case(), base))

        assert result.startswith(base)

    def test_agrega_la_literatura_recuperada(self, monkeypatch) -> None:
        """Con la búsqueda funcionando, la literatura recuperada llega al agente."""
        _RagFalso().instalar(monkeypatch)

        result, _ = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert "PMID: 99999901" in result
        assert "No se pudo acceder" not in result

    def test_indexacion_caida_no_impide_buscar(self, monkeypatch) -> None:
        """Si falla indexar, se busca igual sobre lo que ya hay en la base local."""
        rag = _RagFalso(indexacion_falla=True).instalar(monkeypatch)

        result, _ = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert rag.query is not None
        assert "PMID: 99999901" in result

    def test_busqueda_caida_devuelve_fallback_explicito(self, monkeypatch) -> None:
        """
        Si falla la búsqueda, el agente recibe el aviso y la instrucción de usar
        evidencia III — y ninguna referencia, porque no hay ninguna verificada.
        """
        _RagFalso(busqueda_falla=True).instalar(monkeypatch)
        base = "CONTEXTO BASE"

        result, _ = asyncio.run(_enrich_context_with_rag(_make_case(), base))

        assert result.startswith(base)
        assert "No se pudo acceder a la base local de PubMed" in result
        assert "evidence_level: 'III'" in result
        assert "PMID: 99999901" not in result

    def test_sin_biomarkers_indexa_solo_la_condicion(self, monkeypatch) -> None:
        rag = _RagFalso().instalar(monkeypatch)
        case = _make_case(with_biomarkers=False)
        case.pico.condition_en = "axonal neuropathy"

        asyncio.run(_enrich_context_with_rag(case, "BASE"))

        assert rag.indexado_con == {
            "genes": [], "conditions": ["axonal neuropathy"], "drugs": []
        }

    def test_sin_pico_no_rompe_ni_inventa_condicion(self, monkeypatch) -> None:
        """Sin síntesis PICO no hay condición que buscar, pero el pipeline sigue."""
        rag = _RagFalso().instalar(monkeypatch)
        base = "CONTEXTO BASE SIN PICO"

        result, _ = asyncio.run(_enrich_context_with_rag(ClinicalCase(raw_text="texto plano"), base))

        assert result.startswith(base)
        assert rag.indexado_con["conditions"] == []


class TestIdiomaDeLaQueryRag:
    """
    PubMed indexa en inglés: la query del RAG debe usar `condition_en`, no el
    `chief_complaint` en español extraído del documento clínico.

    Medido sobre el caso de prueba (scripts/demo_embeddings_comparacion.py):
    consultar en español baja el score del mejor resultado de 0.866 a 0.781 y
    degrada el orden del diagnóstico diferencial.
    """

    @staticmethod
    def _capturar(case: ClinicalCase, monkeypatch) -> dict:
        """Corre el enriquecido interceptando qué se le manda a PubMed."""
        capturado: dict = {}

        async def fake_index(genes, conditions, drugs):
            capturado["conditions"] = conditions
            return {}

        class FakeRetriever:
            def get_context_with_articles(self, query, max_results=5):
                capturado["query"] = query
                return "LITERATURA CIENTÍFICA DISPONIBLE:\n(stub)", []

        monkeypatch.setattr(
            "backend.pipeline.orchestrator.index_from_clinical_context", fake_index
        )
        monkeypatch.setattr(
            "backend.pipeline.orchestrator.PubMedRetriever", lambda: FakeRetriever()
        )

        asyncio.run(_enrich_context_with_rag(case, "BASE"))
        return capturado

    def test_usa_condition_en_cuando_esta_disponible(self, monkeypatch) -> None:
        case = _make_case()
        case.pico.condition_en = "axonal neuropathy"

        cap = self._capturar(case, monkeypatch)

        assert cap["conditions"] == ["axonal neuropathy"]
        assert "axonal neuropathy" in cap["query"]
        # El término en español no debe llegar a PubMed
        assert "Neuropatía" not in cap["query"]

    def test_cae_a_chief_complaint_si_no_hay_condition_en(self, monkeypatch) -> None:
        """Sin condition_en el comportamiento previo se preserva, no se rompe."""
        case = _make_case()
        case.pico.condition_en = ""

        cap = self._capturar(case, monkeypatch)

        assert cap["conditions"] == ["Neuropatía axonal sensitivomotora progresiva"]

    def test_primary_outcome_no_contamina_la_query(self, monkeypatch) -> None:
        """primary_outcome está en español: no debe entrar a la query semántica."""
        case = _make_case()
        case.pico.condition_en = "axonal neuropathy"
        case.pico.primary_outcome = "Etiología de neuropatía axonal"

        cap = self._capturar(case, monkeypatch)

        assert "Etiología" not in cap["query"]

    def test_los_genes_siguen_en_la_query(self, monkeypatch) -> None:
        """Los símbolos HGNC son idioma-neutros y aportan precisión."""
        case = _make_case()
        case.pico.condition_en = "axonal neuropathy"

        cap = self._capturar(case, monkeypatch)

        assert "TTR" in cap["query"]


class TestArticulosRecuperadosLleganAlReport:
    """
    El orquestador conserva los artículos que el RAG ofreció (D5 del cambio
    agente-04-arbitro-verificador).

    Antes se llamaba a `get_context_for_agent()` y se guardaba solo el string
    formateado: los objetos con los PMIDs reales se perdían, y sin ellos no hay
    forma de medir si los agentes citaron la literatura que se les dio ni de
    armar la ronda de recitación.
    """

    def test_devuelve_los_articulos_junto_al_contexto(self, monkeypatch) -> None:
        _RagFalso().instalar(monkeypatch)

        _, articulos = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert [a.pmid for a in articulos] == ["99999901"]
        assert articulos[0].journal == "J Peripher Nerv Syst"
        assert articulos[0].excerpt.startswith("Hereditary ATTR amyloidosis")

    def test_busqueda_caida_deja_la_lista_vacia(self, monkeypatch) -> None:
        """El fallo del RAG no rompe el pipeline: sigue sin artículos."""
        _RagFalso(busqueda_falla=True).instalar(monkeypatch)

        contexto, articulos = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert articulos == []
        assert "No se pudo acceder a la base local de PubMed" in contexto

    def test_articulo_sin_pmid_se_descarta(self, monkeypatch) -> None:
        """Sin PMID no sirve para validar una recitación ni para el solapamiento."""
        rag = _RagFalso()

        async def fake_index(genes, conditions, drugs):
            return {}

        class FakeRetriever:
            def get_context_with_articles(self, query, max_results=5):
                sin_pmid = RetrievedArticle(
                    pmid="", title="Artículo sin PMID", journal="", year="",
                    authors="", url="", excerpt="", relevance_score=0.5,
                )
                return _LITERATURA_OK, [*_ARTICULOS_OK, sin_pmid]

        monkeypatch.setattr(
            "backend.pipeline.orchestrator.index_from_clinical_context", fake_index
        )
        monkeypatch.setattr(
            "backend.pipeline.orchestrator.PubMedRetriever", lambda: FakeRetriever()
        )

        _, articulos = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert [a.pmid for a in articulos] == ["99999901"]


class TestSolapamientoRagCitas:
    """
    Métrica que justifica que el Árbitro exista: cuántas de las citas de los
    agentes salieron de la literatura que el RAG les ofreció. Medido 0 de 15 en
    la corrida real del 2026-09-15.
    """

    @staticmethod
    def _hipotesis(pmids: list[str]) -> Hypothesis:
        return Hypothesis(
            text="Amiloidosis ATTR hereditaria",
            priority=Priority.HIGH,
            evidence_level=EvidenceLevel.II,
            rationale="Neuropatía axonal de fibra fina.",
            sources=[Source(pmid=p, title=f"Artículo {p}") for p in pmids],
        )

    @staticmethod
    def _articulos(pmids: list[str]) -> list[RetrievedArticleRef]:
        return [RetrievedArticleRef(pmid=p, title=f"Artículo {p}") for p in pmids]

    def test_los_agentes_ignoran_la_literatura_ofrecida(self) -> None:
        solapan, total = rag_overlap(
            [self._hipotesis(["11111111", "22222222"])],
            self._articulos(["99999901", "99999902"]),
        )
        assert (solapan, total) == (0, 2)

    def test_una_cita_del_conjunto_ofrecido(self) -> None:
        solapan, total = rag_overlap(
            [self._hipotesis(["99999901", "22222222"])],
            self._articulos(["99999901", "99999902"]),
        )
        assert (solapan, total) == (1, 2)

    def test_sin_articulos_recuperados_el_solapamiento_es_cero(self) -> None:
        solapan, total = rag_overlap([self._hipotesis(["11111111"])], [])
        assert (solapan, total) == (0, 1)

    def test_sin_citas_no_divide_por_cero(self) -> None:
        assert rag_overlap([self._hipotesis([])], self._articulos(["99999901"])) == (0, 0)

    def test_pmids_repetidos_cuentan_una_vez(self) -> None:
        """Dos hipótesis que citan el mismo PMID no inflan el total."""
        solapan, total = rag_overlap(
            [self._hipotesis(["99999901"]), self._hipotesis(["99999901"])],
            self._articulos(["99999901"]),
        )
        assert (solapan, total) == (1, 1)
