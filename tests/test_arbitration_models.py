"""
Tests de los modelos del Agente 04 (backend/models/arbitration.py).

Solo validación de contratos: ningún test llama a un LLM, a PubMed ni al RAG.
Lo que se comprueba es que los campos nuevos tienen default (el contrato de
exportación es aditivo) y que el consenso envuelve a `Hypothesis` sin
reemplazarla.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

from backend.models.arbitration import (
    ArbitrationInput,
    ArbitrationResult,
    ArbitrationStatus,
    ArbitrationSummary,
    ConsensusHypothesis,
    Contradiction,
    RecitationOutcome,
    RecitationSummary,
)
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Critique, Report, RetrievedArticleRef


def _hypothesis(text: str = "Amiloidosis ATTR hereditaria") -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        rationale="Neuropatía axonal de fibra fina con compromiso autonómico.",
        sources=[Source(pmid="12345678", title="ATTR amyloidosis")],
    )


class TestConsensusHypothesis:

    def test_defaults_minimos(self):
        """Con solo la hipótesis representativa el modelo ya valida."""
        c = ConsensusHypothesis(hypothesis=_hypothesis())
        assert c.grouped == []
        assert c.supporting_agents == []
        assert c.refuting_agents == []
        assert c.contradictions == []
        assert c.verdict == ""
        assert c.recitation is RecitationOutcome.NO_APLICA

    def test_support_count(self):
        c = ConsensusHypothesis(
            hypothesis=_hypothesis(),
            supporting_agents=["Analista de Literatura", "Especialista Genómica"],
        )
        assert c.support_count == 2

    def test_support_count_sin_agentes(self):
        assert ConsensusHypothesis(hypothesis=_hypothesis()).support_count == 0

    def test_envuelve_la_hipotesis_sin_reemplazarla(self):
        """evidence.py sigue recibiendo Hypothesis: el consenso no la transforma."""
        h = _hypothesis()
        c = ConsensusHypothesis(hypothesis=h, grouped=[h])
        assert isinstance(c.hypothesis, Hypothesis)
        assert c.hypothesis.evidence_level is EvidenceLevel.II
        assert c.hypothesis.sources[0].pmid == "12345678"

    def test_grouped_conserva_todas(self):
        a, b = _hypothesis("A"), _hypothesis("B")
        c = ConsensusHypothesis(hypothesis=a, grouped=[a, b])
        assert [h.text for h in c.grouped] == ["A", "B"]


class TestContradiction:

    def test_se_construye_desde_los_datos_de_una_critica(self):
        contra = Contradiction(
            from_agent_id="03",
            from_agent_name="Consultor Clínico",
            severity="HIGH",
            critique_text="Sin biopsia no se sostiene.",
            target_hypothesis="Amiloidosis ATTR hereditaria",
        )
        assert contra.alternative is None
        assert contra.severity == "HIGH"


class TestArbitrationInput:

    def test_todo_opcional(self):
        entrada = ArbitrationInput()
        assert entrada.hypotheses == []
        assert entrada.critiques == []
        assert entrada.round_1_by_agent == {}
        assert entrada.final_by_agent == {}
        assert entrada.agent_names == {}

    def test_acepta_criticas_y_rondas_por_agente(self):
        critique = Critique(
            from_agent_id="03",
            from_agent_name="Consultor Clínico",
            target_agent_id="01",
            target_hypothesis="Amiloidosis ATTR hereditaria",
            critique_text="Falta confirmación histológica.",
            severity="HIGH",
        )
        entrada = ArbitrationInput(
            hypotheses=[_hypothesis()],
            critiques=[critique],
            round_1_by_agent={"01": [_hypothesis()]},
            final_by_agent={"01": [_hypothesis()]},
            agent_names={"01": "Analista de Literatura"},
        )
        assert entrada.critiques[0].severity == "HIGH"
        assert entrada.agent_names["01"] == "Analista de Literatura"


class TestArbitrationSummary:

    def test_defaults_en_cero(self):
        s = ArbitrationSummary()
        assert s.status is ArbitrationStatus.OK
        assert (s.input_hypotheses, s.consensus_hypotheses, s.contradictions) == (0, 0, 0)
        assert (s.cited_sources, s.rag_overlap, s.retrieved_articles) == (0, 0, 0)
        assert s.discarded_references == 0

    def test_recitacion_anidada_tiene_default(self):
        s = ArbitrationSummary()
        assert isinstance(s.recitation, RecitationSummary)
        assert s.recitation.executed is False
        assert s.recitation.recited == 0
        assert s.recitation.failed_agents == []

    def test_estado_degradado(self):
        s = ArbitrationSummary(status=ArbitrationStatus.DEGRADADO)
        assert s.status is ArbitrationStatus.DEGRADADO


class TestArbitrationResult:

    def test_default_vacio(self):
        r = ArbitrationResult()
        assert r.consensus == []
        assert r.summary.status is ArbitrationStatus.OK

    def test_serializa_a_json(self):
        """El resultado viaja al reporte: tiene que serializar sin ayuda."""
        r = ArbitrationResult(
            consensus=[ConsensusHypothesis(hypothesis=_hypothesis())],
            summary=ArbitrationSummary(input_hypotheses=3, consensus_hypotheses=1),
        )
        data = r.model_dump()
        assert data["summary"]["consensus_hypotheses"] == 1
        assert data["consensus"][0]["hypothesis"]["text"] == "Amiloidosis ATTR hereditaria"


class TestRetrievedArticleRefEnReport:

    def test_report_sin_articulos_sigue_validando(self):
        """Contrato aditivo: un Report armado antes del cambio sigue siendo válido."""
        report = Report(case_summary="Varón de 42 años con neuropatía axonal.")
        assert report.retrieved_articles == []

    def test_report_con_articulos(self):
        report = Report(
            case_summary="Varón de 42 años con neuropatía axonal.",
            retrieved_articles=[
                RetrievedArticleRef(pmid="28712356", title="Fabry disease and neuropathy")
            ],
        )
        assert report.retrieved_articles[0].pmid == "28712356"
        assert report.retrieved_articles[0].journal == ""

    def test_campos_opcionales_del_articulo(self):
        art = RetrievedArticleRef(
            pmid="28712356",
            title="Fabry disease and neuropathy",
            journal="Orphanet J Rare Dis",
            year="2018",
            excerpt="Fabry disease presenting with peripheral neuropathy…",
        )
        assert art.year == "2018"


def test_los_modelos_no_arrastran_chromadb():
    """
    backend.models no debe depender del RAG.

    RetrievedArticleRef existe justamente para que importar modelos no cargue
    ChromaDB ni sentence-transformers.
    """
    import subprocess
    import sys

    codigo = (
        "import sys; import backend.models.report, backend.models.arbitration; "
        "print('chromadb' in sys.modules)"
    )
    salida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    )
    assert salida.stdout.strip() == "False"
