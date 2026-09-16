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
            def get_context_for_agent(self, query, max_results=5):
                rag.query = query
                if rag.busqueda_falla:
                    raise ConnectionError("ChromaDB no disponible (simulado)")
                return _LITERATURA_OK

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

        result = asyncio.run(_enrich_context_with_rag(_make_case(), base))

        assert result.startswith(base)

    def test_agrega_la_literatura_recuperada(self, monkeypatch) -> None:
        """Con la búsqueda funcionando, la literatura recuperada llega al agente."""
        _RagFalso().instalar(monkeypatch)

        result = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert "PMID: 99999901" in result
        assert "No se pudo acceder" not in result

    def test_indexacion_caida_no_impide_buscar(self, monkeypatch) -> None:
        """Si falla indexar, se busca igual sobre lo que ya hay en la base local."""
        rag = _RagFalso(indexacion_falla=True).instalar(monkeypatch)

        result = asyncio.run(_enrich_context_with_rag(_make_case(), "BASE"))

        assert rag.query is not None
        assert "PMID: 99999901" in result

    def test_busqueda_caida_devuelve_fallback_explicito(self, monkeypatch) -> None:
        """
        Si falla la búsqueda, el agente recibe el aviso y la instrucción de usar
        evidencia III — y ninguna referencia, porque no hay ninguna verificada.
        """
        _RagFalso(busqueda_falla=True).instalar(monkeypatch)
        base = "CONTEXTO BASE"

        result = asyncio.run(_enrich_context_with_rag(_make_case(), base))

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

        result = asyncio.run(_enrich_context_with_rag(ClinicalCase(raw_text="texto plano"), base))

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
            def get_context_for_agent(self, query, max_results=5):
                capturado["query"] = query
                return "LITERATURA CIENTÍFICA DISPONIBLE:\n(stub)"

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
