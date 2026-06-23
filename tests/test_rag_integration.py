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
