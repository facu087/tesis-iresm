"""
Tests de la clasificación de evidencia EBM (backend/pipeline/evidence.py).

Reglas puras: ningún test llama a PubMed ni a un LLM. Los veredictos de la
verificación se construyen a mano. Caso de prueba base: neuropatía axonal
sensitivomotora, paciente masculino de 42 años.
"""

import pytest

from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.pipeline.evidence import (
    HypothesisStatus,
    classify_hypothesis,
    prioritize,
    source_ceiling,
)
from backend.pipeline.verification import SourceStatus, SourceVerification

I, II, III = EvidenceLevel.I, EvidenceLevel.II, EvidenceLevel.III


# ── Fixtures del caso base ─────────────────────────────────────────────────────

def _source(pmid: str | None, title: str = "Estudio", **extra: object) -> Source:
    return Source(pmid=pmid, title=title, **extra)


def _hypothesis(
    text: str = "Déficit de vitamina B12 por metformina en varón de 42 años con neuropatía axonal.",
    declared: EvidenceLevel = I,
    priority: Priority = Priority.HIGH,
    sources: list[Source] | None = None,
) -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=priority,
        evidence_level=declared,
        rationale="Razonamiento de prueba.",
        sources=[] if sources is None else sources,
    )


def _verdict(
    pmid: str | None,
    status: SourceStatus = SourceStatus.VERIFICADA,
    types: list[str] | None = None,
    title: str = "Estudio",
) -> SourceVerification:
    return SourceVerification(
        pmid=pmid,
        status=status,
        claimed_title=title,
        publication_types=types or [],
    )


def _verifications(*verdicts: SourceVerification) -> dict[str, SourceVerification]:
    return {(v.pmid or v.claimed_title): v for v in verdicts}


# ── Tope por tipo de publicación ───────────────────────────────────────────────

class TestSourceCeiling:
    def test_meta_analisis_habilita_nivel_i(self):
        assert source_ceiling(["Journal Article", "Meta-Analysis"]) is I

    @pytest.mark.parametrize("tipo", [
        "Network Meta-Analysis", "Systematic Review", "Randomized Controlled Trial",
    ])
    def test_otros_tipos_de_nivel_i(self, tipo):
        assert source_ceiling([tipo]) is I

    def test_observacional_topea_en_ii(self):
        assert source_ceiling(["Journal Article", "Observational Study"]) is II

    @pytest.mark.parametrize("tipo", [
        "Clinical Trial", "Clinical Trial, Phase III", "Controlled Clinical Trial",
        "Pragmatic Clinical Trial", "Comparative Study", "Multicenter Study", "Guideline",
    ])
    def test_otros_tipos_de_nivel_ii(self, tipo):
        assert source_ceiling([tipo]) is II

    def test_guia_de_practica_clinica_topea_en_ii(self):
        assert source_ceiling(["Practice Guideline", "Journal Article"]) is II

    def test_articulo_sin_diseno_identificable_topea_en_ii(self):
        assert source_ceiling(["Journal Article"]) is II

    def test_sin_tipos_topea_en_ii(self):
        assert source_ceiling([]) is II

    def test_reporte_de_caso_topea_en_iii(self):
        assert source_ceiling(["Case Reports", "Journal Article"]) is III

    @pytest.mark.parametrize("tipo", [
        "Scoping Review", "Letter", "Editorial", "Comment", "News",
        "Consensus Development Conference",
    ])
    def test_otros_tipos_de_nivel_iii(self, tipo):
        assert source_ceiling([tipo]) is III

    def test_revision_sistematica_previa_a_2019_indexada_como_review(self):
        """Limitación documentada: antes de 2019 no existía el tipo Systematic Review."""
        assert source_ceiling(["Journal Article", "Review"]) is III

    def test_mezcla_de_tipos_toma_el_mejor(self):
        assert source_ceiling(["Multicenter Study", "Randomized Controlled Trial"]) is I

    def test_publicacion_retractada_anula_cualquier_otro_tipo(self):
        assert source_ceiling(["Randomized Controlled Trial", "Retracted Publication"]) is III

    def test_insensible_a_mayusculas_y_espacios(self):
        assert source_ceiling(["  meta-ANALYSIS "]) is I
        assert source_ceiling(["CASE REPORTS"]) is III


# ── Nivel efectivo ─────────────────────────────────────────────────────────────

class TestNivelEfectivo:
    def test_nivel_declarado_respaldado_por_rct_se_conserva(self):
        h = _hypothesis(declared=I, sources=[_source("30000001")])
        v = _verifications(_verdict("30000001", types=["Randomized Controlled Trial"]))
        assert classify_hypothesis(h, v).effective_level is I

    def test_nivel_declarado_mayor_que_el_tope_se_baja(self):
        h = _hypothesis(declared=I, sources=[_source("30000002")])
        v = _verifications(_verdict("30000002", types=["Observational Study"]))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.effective_level is II
        assert evaluacion.capped

    def test_el_tope_no_sube_un_nivel_declarado_conservador(self):
        h = _hypothesis(declared=III, sources=[_source("30000001")])
        v = _verifications(_verdict("30000001", types=["Meta-Analysis"]))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.effective_level is III
        assert evaluacion.ceiling is I
        assert not evaluacion.capped

    def test_se_usa_la_mejor_fuente_verificada(self):
        h = _hypothesis(declared=I, sources=[_source("30000003"), _source("30000001")])
        v = _verifications(
            _verdict("30000003", types=["Case Reports"]),
            _verdict("30000001", types=["Meta-Analysis"]),
        )
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.effective_level is I
        assert evaluacion.best_source_pmid == "30000001"

    def test_sin_fuentes_verificadas_el_nivel_es_iii(self):
        h = _hypothesis(declared=I, sources=[
            _source("16512345"), _source("99999999"), _source(None, "Guía AAN sin PMID"),
        ])
        v = _verifications(
            _verdict("16512345", SourceStatus.DISCORDANTE),
            _verdict("99999999", SourceStatus.INEXISTENTE),
            _verdict(None, SourceStatus.SIN_PMID, title="Guía AAN sin PMID"),
        )
        assert classify_hypothesis(h, v).effective_level is III

    def test_hipotesis_sin_fuentes(self):
        h = _hypothesis(declared=II, sources=[])
        assert classify_hypothesis(h, {}).effective_level is III


# ── Estado bibliográfico ───────────────────────────────────────────────────────

class TestEstado:
    def test_una_fuente_verificada_alcanza_para_quedar_respaldada(self):
        h = _hypothesis(sources=[_source("30000001"), _source("16512345")])
        v = _verifications(
            _verdict("30000001", types=["Meta-Analysis"]),
            _verdict("16512345", SourceStatus.DISCORDANTE),
        )
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.status is HypothesisStatus.RESPALDADA
        assert evaluacion.verified_sources == 1

    def test_pmid_alucinado_deja_la_hipotesis_especulativa(self):
        h = _hypothesis(sources=[_source("16512345")])
        v = _verifications(_verdict("16512345", SourceStatus.DISCORDANTE))
        assert classify_hypothesis(h, v).status is HypothesisStatus.ESPECULATIVA

    def test_caida_de_pubmed_deja_la_hipotesis_pendiente(self):
        h = _hypothesis(declared=I, sources=[_source("30000001")])
        v = _verifications(_verdict("30000001", SourceStatus.NO_VERIFICABLE))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.status is HypothesisStatus.PENDIENTE
        assert evaluacion.effective_level is III

    def test_reporte_armado_sin_verificacion(self):
        h = _hypothesis(sources=[_source("30000001")])
        assert classify_hypothesis(h, {}).status is HypothesisStatus.PENDIENTE

    def test_fuente_sin_pmid_no_deja_pendiente(self):
        h = _hypothesis(sources=[_source(None, "Guía EFNS de neuropatía")])
        assert classify_hypothesis(h, {}).status is HypothesisStatus.ESPECULATIVA

    def test_hipotesis_sin_fuentes_es_especulativa(self):
        assert classify_hypothesis(_hypothesis(sources=[]), {}).status is HypothesisStatus.ESPECULATIVA


# ── Solo cuentan los veredictos ────────────────────────────────────────────────

class TestSoloVeredictos:
    def test_el_llm_declara_su_fuente_como_verificada(self):
        fuente = _source("30000001", verified=True, verification_status="verificada")
        h = _hypothesis(sources=[fuente])
        evaluacion = classify_hypothesis(h, {})
        assert evaluacion.status is not HypothesisStatus.RESPALDADA
        assert evaluacion.verified_sources == 0

    def test_el_llm_inventa_tipos_de_publicacion(self):
        fuente = _source("30000004", publication_types=["Meta-Analysis"])
        h = _hypothesis(declared=I, sources=[fuente])
        v = _verifications(_verdict("30000004", types=["Case Reports"]))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.ceiling is III
        assert evaluacion.effective_level is III


# ── Trazabilidad ───────────────────────────────────────────────────────────────

class TestNota:
    def test_nivel_topeado_menciona_tope_y_tipo(self):
        h = _hypothesis(declared=I, sources=[_source("30000002")])
        v = _verifications(_verdict("30000002", types=["Journal Article", "Observational Study"]))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.declared_level is I
        assert evaluacion.effective_level is II
        assert "topeado" in evaluacion.note
        assert "Observational Study" in evaluacion.note
        assert "30000002" in evaluacion.note

    def test_nivel_sin_cambios_es_compatible(self):
        h = _hypothesis(declared=II, sources=[_source("30000001")])
        v = _verifications(_verdict("30000001", types=["Meta-Analysis"]))
        evaluacion = classify_hypothesis(h, v)
        assert evaluacion.effective_level is II
        assert "compatible" in evaluacion.note

    def test_verificacion_no_disponible(self):
        h = _hypothesis(declared=I, sources=[_source("30000001")])
        v = _verifications(_verdict("30000001", SourceStatus.NO_VERIFICABLE))
        nota = classify_hypothesis(h, v).note
        assert "III hasta poder confirmar" in nota
        assert "declarado I" in nota

    def test_retractada_se_nombra_en_la_nota(self):
        h = _hypothesis(declared=I, sources=[_source("30000005")])
        v = _verifications(_verdict("30000005", types=["Randomized Controlled Trial", "Retracted Publication"]))
        assert "retractada" in classify_hypothesis(h, v).note


# ── Orden ──────────────────────────────────────────────────────────────────────

class TestPrioritize:
    def _textos(self, resultado):
        return [h.text for h, _ in resultado]

    def test_el_nivel_pesa_mas_que_la_prioridad(self):
        h_ii = _hypothesis("CIDP", declared=II, priority=Priority.LOW, sources=[_source("1")])
        h_iii = _hypothesis("Amiloidosis TTR", declared=III, priority=Priority.HIGH, sources=[_source("2")])
        v = _verifications(_verdict("1", types=["Observational Study"]), _verdict("2", types=["Meta-Analysis"]))
        assert self._textos(prioritize([h_iii, h_ii], v)) == ["CIDP", "Amiloidosis TTR"]

    def test_una_respaldada_precede_a_una_especulativa(self):
        respaldada = _hypothesis("B12", declared=III, priority=Priority.LOW, sources=[_source("1")])
        especulativa = _hypothesis("Tóxica", declared=I, priority=Priority.HIGH, sources=[_source("2")])
        v = _verifications(_verdict("1", types=["Case Reports"]), _verdict("2", SourceStatus.DISCORDANTE))
        assert self._textos(prioritize([especulativa, respaldada], v)) == ["B12", "Tóxica"]

    def test_pendiente_entre_respaldada_y_especulativa(self):
        especulativa = _hypothesis("E", sources=[_source("3")])
        pendiente = _hypothesis("P", sources=[_source("2")])
        respaldada = _hypothesis("R", declared=III, sources=[_source("1")])
        v = _verifications(
            _verdict("1", types=["Case Reports"]),
            _verdict("2", SourceStatus.NO_VERIFICABLE),
            _verdict("3", SourceStatus.INEXISTENTE),
        )
        assert self._textos(prioritize([especulativa, pendiente, respaldada], v)) == ["R", "P", "E"]

    def test_desempate_por_prioridad(self):
        media = _hypothesis("Media", declared=II, priority=Priority.MEDIUM, sources=[_source("1")])
        alta = _hypothesis("Alta", declared=II, priority=Priority.HIGH, sources=[_source("2")])
        v = _verifications(_verdict("1", types=["Meta-Analysis"]), _verdict("2", types=["Meta-Analysis"]))
        assert self._textos(prioritize([media, alta], v)) == ["Alta", "Media"]

    def test_desempate_por_cantidad_de_fuentes_verificadas(self):
        una = _hypothesis("Una", declared=II, sources=[_source("1")])
        dos = _hypothesis("Dos", declared=II, sources=[_source("2"), _source("3")])
        v = _verifications(*(_verdict(p, types=["Observational Study"]) for p in ("1", "2", "3")))
        assert self._textos(prioritize([una, dos], v)) == ["Dos", "Una"]

    def test_desempate_estable(self):
        a = _hypothesis("A", declared=II, sources=[_source("1")])
        b = _hypothesis("B", declared=II, sources=[_source("2")])
        v = _verifications(_verdict("1", types=["Observational Study"]), _verdict("2", types=["Observational Study"]))
        assert self._textos(prioritize([a, b], v)) == ["A", "B"]
        assert self._textos(prioritize([b, a], v)) == ["B", "A"]

    def test_misma_entrada_misma_salida(self):
        hipotesis = [
            _hypothesis("B12", declared=I, sources=[_source("1")]),
            _hypothesis("CIDP", declared=II, priority=Priority.MEDIUM, sources=[_source("2")]),
            _hypothesis("TTR", declared=I, sources=[_source("3")]),
            _hypothesis("Sin fuentes", declared=III),
        ]
        v = _verifications(
            _verdict("1", types=["Observational Study"]),
            _verdict("2", SourceStatus.NO_VERIFICABLE),
            _verdict("3", types=["Meta-Analysis"]),
        )
        primera = [(h.text, e.model_dump()) for h, e in prioritize(hipotesis, v)]
        segunda = [(h.text, e.model_dump()) for h, e in prioritize(hipotesis, v)]
        assert primera == segunda

    def test_no_descarta_ninguna_hipotesis(self):
        hipotesis = [_hypothesis(f"H{i}", sources=[_source(str(i))]) for i in range(5)]
        v = _verifications(*(_verdict(str(i), SourceStatus.DISCORDANTE) for i in range(5)))
        assert len(prioritize(hipotesis, v)) == 5
