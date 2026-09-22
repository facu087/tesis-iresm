"""
Tests de la lógica determinista del Árbitro (backend/pipeline/consensus.py).

Ningún test llama a un LLM, a PubMed ni al RAG: la partición que "propone el
modelo" se escribe a mano y los veredictos de la verificación se construyen
directamente. Eso es justamente lo que se quiere probar — que todo lo que
decide algo es determinista y auditable sin red.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import pytest

from backend.models.arbitration import ArbitrationInput, ArbitrationStatus
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Critique, RetrievedArticleRef
from backend.pipeline.consensus import (
    assemble,
    choose_representative,
    degraded,
    detect_contradictions,
    merge_sources,
    normalize_partition,
    summarize,
    text_match,
)
from backend.pipeline.verification import SourceStatus, SourceVerification

ATTR = "Amiloidosis ATTR hereditaria como causa de la neuropatía axonal"
ATTR_OTRA_REDACCION = "Neuropatía axonal secundaria a amiloidosis hereditaria por transtiretina"
B12 = "Déficit de vitamina B12 inducido por metformina"


def _h(text: str, pmids: list[str] | None = None,
       level: EvidenceLevel = EvidenceLevel.II) -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=Priority.HIGH,
        evidence_level=level,
        rationale="Fundamento de prueba.",
        sources=[Source(pmid=p, title=f"Artículo {p}") for p in (pmids or [])],
    )


def _verificada(pmid: str, tipos: list[str] | None = None) -> SourceVerification:
    return SourceVerification(
        pmid=pmid,
        status=SourceStatus.VERIFICADA,
        claimed_title=f"Artículo {pmid}",
        actual_title=f"Artículo {pmid}",
        match_score=1.0,
        publication_types=tipos or ["Journal Article"],
    )


def _entrada(hypotheses, agents, critiques=None, final_by_agent=None) -> ArbitrationInput:
    return ArbitrationInput(
        hypotheses=hypotheses,
        hypothesis_agents=agents,
        critiques=critiques or [],
        final_by_agent=final_by_agent or {},
        agent_names={
            "01": "Analista de Literatura",
            "02": "Especialista Genómica",
            "03": "Consultor Clínico",
        },
    )


# ── 4.1 Validación de la partición ────────────────────────────────────────────

class TestNormalizePartition:

    def test_particion_valida_se_conserva(self):
        assert normalize_partition([[0, 2], [1]], total=3) == [[0, 2], [1]]

    def test_indice_fuera_de_rango_se_ignora(self):
        assert normalize_partition([[0, 99], [1]], total=2) == [[0], [1]]

    def test_indice_negativo_se_ignora(self):
        assert normalize_partition([[0, -1], [1]], total=2) == [[0], [1]]

    def test_indice_repetido_queda_en_el_primer_grupo(self):
        assert normalize_partition([[0, 1], [1, 2]], total=3) == [[0, 1], [2]]

    def test_indice_omitido_se_agrega_como_grupo_propio(self):
        """Agrupar nunca descarta: lo que el modelo olvidó no se pierde."""
        assert normalize_partition([[0]], total=3) == [[0], [1], [2]]

    def test_grupo_vacio_se_descarta(self):
        assert normalize_partition([[], [0]], total=1) == [[0]]

    def test_particion_vacia_devuelve_una_hipotesis_por_grupo(self):
        assert normalize_partition([], total=3) == [[0], [1], [2]]

    def test_tipos_no_enteros_se_ignoran(self):
        """Un LLM puede devolver strings o nulls entre los índices."""
        assert normalize_partition([["0", None, 1]], total=2) == [[1], [0]]

    def test_booleanos_no_cuentan_como_indices(self):
        """True == 1 en Python: hay que descartarlo explícitamente."""
        assert normalize_partition([[True]], total=2) == [[0], [1]]

    @pytest.mark.parametrize("groups", [
        [[0, 1, 2]], [[0], [1], [2]], [[2, 0], [1]], [], [[0, 0, 0]],
    ])
    def test_conservacion_total(self, groups):
        """Propiedad de la spec: la suma de los grupos es siempre N."""
        resultado = normalize_partition(groups, total=3)
        indices = [i for grupo in resultado for i in grupo]
        assert sorted(indices) == [0, 1, 2]
        assert len(indices) == len(set(indices))


# ── 4.2 Texto representativo ──────────────────────────────────────────────────

class TestChooseRepresentative:

    def test_gana_la_respaldada_sobre_la_especulativa(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION, ["111"])], ["01", "02"])
        verifs = {"111": _verificada("111")}
        assert choose_representative([0, 1], entrada, verifs) == 1

    def test_a_igual_estado_gana_el_mejor_nivel_efectivo(self):
        entrada = _entrada(
            [_h(ATTR, ["111"], EvidenceLevel.III), _h(ATTR_OTRA_REDACCION, ["222"], EvidenceLevel.I)],
            ["01", "02"],
        )
        verifs = {
            "111": _verificada("111", ["Case Reports"]),
            "222": _verificada("222", ["Meta-Analysis"]),
        }
        assert choose_representative([0, 1], entrada, verifs) == 1

    def test_a_igual_nivel_gana_el_agente_de_menor_id(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION)], ["03", "01"])
        assert choose_representative([0, 1], entrada, {}) == 1

    def test_desempate_estable_por_orden_de_entrega(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION)], ["01", "01"])
        assert choose_representative([0, 1], entrada, {}) == 0

    def test_grupo_de_uno(self):
        entrada = _entrada([_h(ATTR)], ["01"])
        assert choose_representative([0], entrada, {}) == 0


# ── 4.3 Consolidación de fuentes ──────────────────────────────────────────────

class TestMergeSources:

    def test_junta_las_fuentes_de_las_agrupadas(self):
        fuentes = merge_sources([_h(ATTR, ["111"]), _h(ATTR_OTRA_REDACCION, ["222"])])
        assert [s.pmid for s in fuentes] == ["111", "222"]

    def test_deduplica_la_fuente_compartida(self):
        fuentes = merge_sources([_h(ATTR, ["111", "222"]), _h(ATTR_OTRA_REDACCION, ["222", "333"])])
        assert [s.pmid for s in fuentes] == ["111", "222", "333"]

    def test_fuente_sin_pmid_se_deduplica_por_titulo(self):
        a = Hypothesis(text=ATTR, priority=Priority.LOW, evidence_level=EvidenceLevel.III,
                       rationale="…", sources=[Source(title="Guía ESMO")])
        b = Hypothesis(text=B12, priority=Priority.LOW, evidence_level=EvidenceLevel.III,
                       rationale="…", sources=[Source(title="Guía ESMO")])
        assert len(merge_sources([a, b])) == 1

    def test_sin_fuentes(self):
        assert merge_sources([_h(ATTR)]) == []


# ── 4.4 Contradicciones ───────────────────────────────────────────────────────

def _critica(severity: str = "HIGH", target_agent: str = "01",
             target: str = ATTR, texto: str = "Sin biopsia no se sostiene.") -> Critique:
    return Critique(
        from_agent_id="03",
        from_agent_name="Consultor Clínico",
        target_agent_id=target_agent,
        target_hypothesis=target,
        critique_text=texto,
        severity=severity,
    )


class TestDetectContradictions:

    def test_critica_high_mantenida_es_contradiccion(self):
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("HIGH")],
            final_by_agent={"01": [_h(ATTR)]},  # el agente no cambió nada
        )
        contradicciones = detect_contradictions([[0]], entrada)
        assert len(contradicciones[0]) == 1
        assert contradicciones[0][0].from_agent_name == "Consultor Clínico"

    def test_critica_high_incorporada_no_es_contradiccion(self):
        """El agente reescribió su hipótesis: la objeción quedó resuelta."""
        entrada = _entrada(
            [_h(B12)], ["01"],
            critiques=[_critica("HIGH", target=ATTR)],
            final_by_agent={"01": [_h(B12)]},
        )
        assert detect_contradictions([[0]], entrada) == {}

    def test_critica_medium_no_se_reporta(self):
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("MEDIUM")],
            final_by_agent={"01": [_h(ATTR)]},
        )
        assert detect_contradictions([[0]], entrada) == {}

    def test_critica_low_no_se_reporta(self):
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("LOW")],
            final_by_agent={"01": [_h(ATTR)]},
        )
        assert detect_contradictions([[0]], entrada) == {}

    def test_critica_inatribuible_no_se_inventa_contra_otro_grupo(self):
        """Si no se puede saber a qué hipótesis apunta, no se adjudica."""
        entrada = _entrada(
            [_h(B12)], ["01"],
            critiques=[_critica("HIGH", target="Otra cosa completamente distinta")],
            final_by_agent={"01": [_h("Otra cosa completamente distinta")]},
        )
        assert detect_contradictions([[0]], entrada) == {}

    def test_sin_rastro_de_la_ronda_final_se_documenta(self):
        """Lado seguro: no se puede afirmar que el agente cedió."""
        entrada = _entrada([_h(ATTR)], ["01"], critiques=[_critica("HIGH")])
        assert len(detect_contradictions([[0]], entrada)[0]) == 1

    def test_solo_mira_al_agente_criticado(self):
        """
        Regresión sobre _detect_divergences(): antes bastaba con que OTRO agente
        dijera algo parecido para dar por mantenida una hipótesis que su autor
        sí había corregido.
        """
        entrada = _entrada(
            [_h(ATTR)], ["02"],
            critiques=[_critica("HIGH", target_agent="01", target=ATTR)],
            final_by_agent={
                "01": [_h(B12)],    # el criticado cedió
                "02": [_h(ATTR)],   # otro agente sigue sosteniéndolo
            },
        )
        assert detect_contradictions([[0]], entrada) == {}


# ── Ensamblado ────────────────────────────────────────────────────────────────

class TestAssemble:

    def test_tres_agentes_una_hipotesis_de_consenso(self):
        entrada = _entrada(
            [_h(ATTR, ["111"]), _h(ATTR_OTRA_REDACCION, ["222"]), _h(B12, ["333"])],
            ["01", "02", "03"],
        )
        consenso = assemble([[0, 1], [2]], entrada, {})

        assert len(consenso) == 2
        assert consenso[0].supporting_agents == ["Analista de Literatura", "Especialista Genómica"]
        assert consenso[0].support_count == 2
        assert consenso[1].supporting_agents == ["Consultor Clínico"]

    def test_la_hipotesis_de_consenso_lleva_las_fuentes_del_grupo(self):
        entrada = _entrada([_h(ATTR, ["111"]), _h(ATTR_OTRA_REDACCION, ["222"])], ["01", "02"])
        consenso = assemble([[0, 1]], entrada, {})
        assert sorted(s.pmid for s in consenso[0].hypothesis.sources) == ["111", "222"]

    def test_grouped_conserva_todas_las_agrupadas(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION)], ["01", "02"])
        consenso = assemble([[0, 1]], entrada, {})
        assert len(consenso[0].grouped) == 2

    def test_el_enunciado_sale_de_un_agente_no_del_modelo(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION)], ["03", "01"])
        consenso = assemble([[0, 1]], entrada, {})
        assert consenso[0].hypothesis.text in (ATTR, ATTR_OTRA_REDACCION)

    def test_refuting_agents_sale_de_las_contradicciones(self):
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("HIGH")],
            final_by_agent={"01": [_h(ATTR)]},
        )
        consenso = assemble([[0]], entrada, {})
        assert consenso[0].refuting_agents == ["Consultor Clínico"]
        assert len(consenso[0].contradictions) == 1

    def test_ninguna_hipotesis_se_pierde(self):
        entrada = _entrada([_h(ATTR), _h(B12), _h("Tercera")], ["01", "02", "03"])
        consenso = assemble(normalize_partition([[0, 1]], 3), entrada, {})
        agrupadas = [h for c in consenso for h in c.grouped]
        assert len(agrupadas) == 3


# ── 4.5 Consenso degradado ────────────────────────────────────────────────────

class TestDegraded:

    def test_cada_hipotesis_es_su_propio_grupo(self):
        entrada = _entrada([_h(ATTR), _h(ATTR_OTRA_REDACCION), _h(B12)], ["01", "02", "03"])
        consenso = degraded(entrada)
        assert len(consenso) == 3
        assert all(len(c.grouped) == 1 for c in consenso)

    def test_conserva_las_n_hipotesis(self):
        entrada = _entrada([_h(ATTR), _h(B12)], ["01", "02"])
        assert len(degraded(entrada)) == len(entrada.hypotheses)

    def test_sin_veredicto(self):
        entrada = _entrada([_h(ATTR)], ["01"])
        assert degraded(entrada)[0].verdict == ""

    def test_igual_detecta_contradicciones(self):
        """Las contradicciones no dependen del LLM: se reportan aunque falle."""
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("HIGH")],
            final_by_agent={"01": [_h(ATTR)]},
        )
        assert len(degraded(entrada)[0].contradictions) == 1

    def test_conserva_el_agente_que_la_propuso(self):
        entrada = _entrada([_h(ATTR)], ["02"])
        assert degraded(entrada)[0].supporting_agents == ["Especialista Genómica"]

    def test_sin_hipotesis(self):
        assert degraded(_entrada([], [])) == []


# ── Resumen ───────────────────────────────────────────────────────────────────

class TestSummarize:

    def test_conteos_de_entrada_y_consenso(self):
        entrada = _entrada([_h(ATTR, ["111"]), _h(ATTR_OTRA_REDACCION, ["222"])], ["01", "02"])
        consenso = assemble([[0, 1]], entrada, {})
        resumen = summarize(consenso, entrada, [])
        assert resumen.input_hypotheses == 2
        assert resumen.consensus_hypotheses == 1

    def test_consenso_nunca_supera_la_entrada(self):
        entrada = _entrada([_h(ATTR), _h(B12)], ["01", "02"])
        consenso = assemble(normalize_partition([], 2), entrada, {})
        resumen = summarize(consenso, entrada, [])
        assert resumen.consensus_hypotheses <= resumen.input_hypotheses

    def test_solapamiento_rag(self):
        entrada = _entrada([_h(ATTR, ["111", "999"])], ["01"])
        resumen = summarize(
            assemble([[0]], entrada, {}), entrada,
            [RetrievedArticleRef(pmid="999", title="Artículo 999")],
        )
        assert (resumen.rag_overlap, resumen.cited_sources) == (1, 2)
        assert resumen.retrieved_articles == 1

    def test_estado_degradado_se_refleja(self):
        entrada = _entrada([_h(ATTR)], ["01"])
        resumen = summarize(degraded(entrada), entrada, [], status=ArbitrationStatus.DEGRADADO)
        assert resumen.status is ArbitrationStatus.DEGRADADO

    def test_cuenta_las_contradicciones(self):
        entrada = _entrada(
            [_h(ATTR)], ["01"],
            critiques=[_critica("HIGH")],
            final_by_agent={"01": [_h(ATTR)]},
        )
        resumen = summarize(assemble([[0]], entrada, {}), entrada, [])
        assert resumen.contradictions == 1


# ── Comparación de enunciados ─────────────────────────────────────────────────

class TestTextMatch:

    def test_identicos(self):
        assert text_match(ATTR, ATTR) == 1.0

    def test_distintos(self):
        assert text_match(ATTR, B12) < 0.6

    def test_ignora_acentos_y_mayusculas(self):
        assert text_match("Neuropatía Axonal", "neuropatia axonal") == 1.0

    def test_texto_vacio(self):
        assert text_match("", ATTR) == 0.0

    def test_containment_tolera_el_detalle_de_mas(self):
        """Un agente redacta la misma hipótesis con más detalle que otro."""
        corto = "Amiloidosis ATTR hereditaria"
        largo = "Amiloidosis ATTR hereditaria con compromiso de fibra fina y disautonomía"
        assert text_match(corto, largo) == 1.0
