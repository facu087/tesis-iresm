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


class TestEnrichContextWithRag:
    """Tests para _enrich_context_with_rag()."""

    def test_retorna_string_con_contexto_base(self) -> None:
        """El contexto enriquecido siempre contiene el contexto PICO base."""
        case = _make_case()
        base = "CONTEXTO PICO BASE de prueba"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        assert isinstance(result, str)
        assert base in result

    def test_agrega_seccion_literatura(self) -> None:
        """El contexto enriquecido incluye una sección de literatura científica."""
        case = _make_case()
        base = "CONTEXTO PICO BASE"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        assert "LITERATURA CIENTÍFICA" in result

    def test_resiliente_sin_biomarkers(self) -> None:
        """Funciona aunque el caso no tenga biomarkers extraídos."""
        case = _make_case(with_biomarkers=False)
        base = "CONTEXTO BASE SIN BIOMARCADORES"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        assert isinstance(result, str)
        assert base in result

    def test_resiliente_sin_pico(self) -> None:
        """Si case.pico es None, devuelve el contexto base sin crashear."""
        case = ClinicalCase(raw_text="texto plano")
        base = "CONTEXTO BASE SIN PICO"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        assert isinstance(result, str)
        assert base in result

    def test_contexto_enriquecido_es_mas_largo(self) -> None:
        """El contexto enriquecido es siempre más largo que el base."""
        case = _make_case()
        base = "CONTEXTO PICO BASE"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        assert len(result) > len(base)

    def test_instruccion_pmid_incluida(self) -> None:
        """El contexto incluye instrucción sobre el uso de PMIDs o fallback de evidence_level."""
        case = _make_case()
        base = "CONTEXTO BASE"
        result = asyncio.run(_enrich_context_with_rag(case, base))
        tiene_instruccion = "PMID" in result or "evidence_level" in result
        assert tiene_instruccion


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
