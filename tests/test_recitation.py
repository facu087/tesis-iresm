"""
Tests de la Ronda 5 — recitación (backend/pipeline/recitation.py y el Agente 04).

Ningún test llama a un LLM ni a PubMed. Lo que se prueba es lo que define si la
ronda sirve o hace daño: a quién se le pide recitar, qué se acepta de lo que
devuelve y que una sola iteración alcance para terminar el análisis.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import asyncio
import json

import pytest

from backend.agents.agent_04_arbiter import ArbiterAgent
from backend.models.arbitration import (
    ArbitrationInput,
    ConsensusHypothesis,
    RecitationOutcome,
)
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import RetrievedArticleRef
from backend.pipeline import recitation
from backend.pipeline.verification import SourceStatus, SourceVerification

ATTR = "Amiloidosis ATTR hereditaria como causa de la neuropatía axonal"
B12 = "Déficit de vitamina B12 inducido por metformina"

# El PMID que el RAG ofreció; el 11111111 es el que el agente inventó.
OFRECIDO = "28712356"
INVENTADO = "11111111"


def _h(text: str, pmids: list[str] | None = None) -> Hypothesis:
    return Hypothesis(
        text=text, priority=Priority.HIGH, evidence_level=EvidenceLevel.II,
        rationale="Fundamento de prueba.",
        sources=[Source(pmid=p, title=f"Artículo {p}") for p in (pmids or [])],
    )


def _consenso(*hypotheses) -> list[ConsensusHypothesis]:
    return [ConsensusHypothesis(hypothesis=h, grouped=[h]) for h in hypotheses]


def _discordante(pmid: str) -> SourceVerification:
    return SourceVerification(
        pmid=pmid, status=SourceStatus.DISCORDANTE,
        claimed_title=f"Artículo {pmid}",
        actual_title="Breeding replacement gilts for organic pig herds",
        match_score=0.0,
    )


def _verificada(pmid: str) -> SourceVerification:
    return SourceVerification(
        pmid=pmid, status=SourceStatus.VERIFICADA, claimed_title=f"Artículo {pmid}",
        actual_title=f"Artículo {pmid}", match_score=1.0,
        publication_types=["Journal Article"],
    )


_ARTICULOS = [RetrievedArticleRef(
    pmid=OFRECIDO,
    title="Fabry disease presenting with peripheral neuropathy",
    journal="Orphanet J Rare Dis", year="2018",
    excerpt="Fabry disease is an underdiagnosed cause of small fiber neuropathy…",
)]


# ── 6.2 Selección ─────────────────────────────────────────────────────────────

class TestSeleccion:

    def test_especulativa_entra(self):
        consenso = _consenso(_h(ATTR, [INVENTADO]))
        assert recitation.select(consenso, {INVENTADO: _discordante(INVENTADO)}) == [0]

    def test_respaldada_no_entra(self):
        consenso = _consenso(_h(ATTR, [OFRECIDO]))
        assert recitation.select(consenso, {OFRECIDO: _verificada(OFRECIDO)}) == []

    def test_sin_fuentes_entra(self):
        assert recitation.select(_consenso(_h(ATTR)), {OFRECIDO: _verificada(OFRECIDO)}) == [0]

    def test_pendiente_por_pubmed_caido_no_entra(self):
        """El problema es de infraestructura: recitar no lo arregla."""
        consenso = _consenso(_h(ATTR, [INVENTADO]))
        verifs = {INVENTADO: SourceVerification(
            pmid=INVENTADO, status=SourceStatus.NO_VERIFICABLE,
            claimed_title=f"Artículo {INVENTADO}",
        )}
        assert recitation.select(consenso, verifs) == []

    def test_should_recite_sin_articulos_es_falso(self):
        """Sin literatura que ofrecer, pedir que citen mejor es pedir que inventen."""
        consenso = _consenso(_h(ATTR, [INVENTADO]))
        verifs = {INVENTADO: _discordante(INVENTADO)}
        assert recitation.should_recite(consenso, verifs, []) is False

    def test_should_recite_sin_verificacion_es_falso(self):
        assert recitation.should_recite(_consenso(_h(ATTR)), {}, _ARTICULOS) is False

    def test_should_recite_con_especulativa_y_articulos(self):
        consenso = _consenso(_h(ATTR, [INVENTADO]))
        verifs = {INVENTADO: _discordante(INVENTADO)}
        assert recitation.should_recite(consenso, verifs, _ARTICULOS) is True


# ── Motivos de fallo ──────────────────────────────────────────────────────────

class TestMotivosDeFallo:

    def test_pmid_discordante(self):
        motivos = recitation.failure_reasons(_h(ATTR, [INVENTADO]), {INVENTADO: _discordante(INVENTADO)})
        assert "corresponde a otro artículo" in motivos[0]
        assert INVENTADO in motivos[0]

    def test_pmid_inexistente(self):
        verifs = {INVENTADO: SourceVerification(
            pmid=INVENTADO, status=SourceStatus.INEXISTENTE,
            claimed_title=f"Artículo {INVENTADO}",
        )}
        assert "no existe en PubMed" in recitation.failure_reasons(_h(ATTR, [INVENTADO]), verifs)[0]

    def test_sin_fuentes(self):
        assert "no citó ninguna referencia" in recitation.failure_reasons(_h(ATTR), {})[0]

    def test_la_fuente_verificada_no_genera_motivo(self):
        motivos = recitation.failure_reasons(_h(ATTR, [OFRECIDO]), {OFRECIDO: _verificada(OFRECIDO)})
        assert motivos == []


# ── 6.3 Validación de los PMIDs recitados ─────────────────────────────────────

class TestValidacionDeRecitado:

    def test_pmid_fuera_del_conjunto_se_descarta(self):
        aceptadas, descartadas = recitation.validate_recited(
            [Source(pmid=INVENTADO, title="Inventado")], {OFRECIDO}
        )
        assert aceptadas == []
        assert descartadas == 1

    def test_pmid_del_conjunto_se_acepta(self):
        aceptadas, descartadas = recitation.validate_recited(
            [Source(pmid=OFRECIDO, title="Fabry disease")], {OFRECIDO}
        )
        assert [s.pmid for s in aceptadas] == [OFRECIDO]
        assert descartadas == 0

    def test_fuente_sin_pmid_se_descarta(self):
        aceptadas, descartadas = recitation.validate_recited(
            [Source(title="Sin PMID")], {OFRECIDO}
        )
        assert (aceptadas, descartadas) == ([], 1)

    def test_deduplica_sin_contar_como_descarte(self):
        aceptadas, descartadas = recitation.validate_recited(
            [Source(pmid=OFRECIDO, title="A"), Source(pmid=OFRECIDO, title="B")], {OFRECIDO}
        )
        assert len(aceptadas) == 1
        assert descartadas == 0


# ── Integración de la ronda en el Árbitro ─────────────────────────────────────

class _AgenteFalso:
    """Agente que devuelve una recitación fija y registra lo que recibió."""

    def __init__(self, respuesta=None, falla=False) -> None:
        self.respuesta = respuesta if respuesta is not None else {}
        self.falla = falla
        self.pedidos: list = []
        self.articulos: list = []

    def recite(self, hypotheses_with_reasons, articles):
        self.pedidos.append(hypotheses_with_reasons)
        self.articulos = articles
        if self.falla:
            raise ConnectionError("Groq no disponible (simulado)")
        return self.respuesta


def _entrada(hypotheses, agents_ids, articulos=None) -> ArbitrationInput:
    return ArbitrationInput(
        hypotheses=hypotheses,
        hypothesis_agents=agents_ids,
        agent_names={"01": "Analista de Literatura", "03": "Consultor Clínico"},
        retrieved_articles=articulos if articulos is not None else _ARTICULOS,
    )


def _instalar_llm(monkeypatch, *respuestas):
    cola = list(respuestas)

    def fake(self_agent, prompt):  # noqa: ANN001
        return cola.pop(0) if cola else json.dumps({"groups": []})

    monkeypatch.setattr("backend.agents.base_agent.BaseAgent._call_llm", fake)


def _correr(entrada, verifs, agents, monkeypatch, verify_result=None):
    """Corre arbitrate() con el LLM y la re-verificación mockeados."""
    _instalar_llm(
        monkeypatch,
        json.dumps({"groups": [[i + 1] for i in range(len(entrada.hypotheses))]}),
        json.dumps({"verdicts": []}),
    )

    async def fake_verify(sources):
        return verify_result if verify_result is not None else {
            s.pmid: _verificada(s.pmid) for s in sources if s.pmid
        }

    monkeypatch.setattr("backend.agents.agent_04_arbiter.verify_sources", fake_verify)
    return asyncio.run(ArbiterAgent().arbitrate(entrada, verifs, agents))


class TestRondaDeRecitacion:

    def test_el_agente_autor_recibe_su_hipotesis_con_el_motivo(self, monkeypatch):
        agente = _AgenteFalso({0: [Source(pmid=OFRECIDO, title="Fabry disease")]})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        _correr(entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch)

        (texto, motivos), = agente.pedidos[0]
        assert texto == ATTR
        assert "corresponde a otro artículo" in motivos[0]

    def test_el_prompt_recibe_los_articulos_reales(self, monkeypatch):
        agente = _AgenteFalso()
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        _correr(entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch)

        assert f"[PMID: {OFRECIDO}]" in agente.articulos[0]
        assert "Fabry disease" in agente.articulos[0]

    def test_recitacion_exitosa_marca_mejorada(self, monkeypatch):
        agente = _AgenteFalso({0: [Source(pmid=OFRECIDO, title="Fabry disease")]})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch
        )

        assert resultado.consensus[0].recitation is RecitationOutcome.MEJORADA
        assert resultado.summary.recitation.improved == 1
        assert resultado.summary.recitation.recited == 1

    def test_pmid_inventado_se_descarta_y_se_cuenta(self, monkeypatch):
        agente = _AgenteFalso({0: [Source(pmid=INVENTADO, title="Otra vez inventado")]})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch
        )

        assert resultado.summary.recitation.rejected_pmids == 1
        assert resultado.summary.recitation.improved == 0
        assert resultado.consensus[0].recitation is RecitationOutcome.SIN_CAMBIO

    def test_recitacion_con_titulo_que_no_corresponde_no_mejora(self, monkeypatch):
        """El PMID es del conjunto ofrecido pero el título no es el del artículo."""
        agente = _AgenteFalso({0: [Source(pmid=OFRECIDO, title="Título que no corresponde")]})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch,
            verify_result={OFRECIDO: _discordante(OFRECIDO)},
        )

        assert resultado.consensus[0].recitation is RecitationOutcome.SIN_CAMBIO
        assert resultado.summary.recitation.improved == 0

    def test_una_sola_iteracion(self, monkeypatch):
        """Después de recitar sin éxito, no se vuelve a llamar al agente."""
        agente = _AgenteFalso({})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        _correr(entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch)

        assert len(agente.pedidos) == 1

    def test_el_analisis_termina_aunque_nada_mejore(self, monkeypatch):
        agente = _AgenteFalso({})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch
        )

        assert len(resultado.consensus) == 1
        assert resultado.summary.recitation.executed is True

    def test_fallo_de_un_agente_no_rompe_el_analisis(self, monkeypatch):
        cae = _AgenteFalso(falla=True)
        ok = _AgenteFalso({0: [Source(pmid=OFRECIDO, title="Fabry disease")]})
        entrada = _entrada([_h(ATTR, [INVENTADO]), _h(B12, [INVENTADO])], ["01", "03"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)},
            {"01": cae, "03": ok}, monkeypatch,
        )

        assert "Analista de Literatura" in resultado.summary.recitation.failed_agents
        assert resultado.consensus[0].recitation is RecitationOutcome.FALLIDA
        assert len(resultado.consensus) == 2

    def test_sin_agentes_no_se_recita(self, monkeypatch):
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(entrada, {INVENTADO: _discordante(INVENTADO)}, None, monkeypatch)

        assert resultado.summary.recitation.executed is False
        assert resultado.summary.recitation.recited == 0

    def test_sin_articulos_recuperados_no_se_recita(self, monkeypatch):
        agente = _AgenteFalso()
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"], articulos=[])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch
        )

        assert agente.pedidos == []
        assert resultado.summary.recitation.executed is False

    def test_la_hipotesis_respaldada_no_se_recita(self, monkeypatch):
        agente = _AgenteFalso()
        entrada = _entrada([_h(ATTR, [OFRECIDO])], ["01"])

        resultado = _correr(entrada, {OFRECIDO: _verificada(OFRECIDO)}, {"01": agente}, monkeypatch)

        assert agente.pedidos == []
        assert resultado.consensus[0].recitation is RecitationOutcome.NO_APLICA

    def test_una_llamada_por_agente_no_por_hipotesis(self, monkeypatch):
        """Con 12k TPM, repetir el bloque de literatura por hipótesis no entra."""
        agente = _AgenteFalso({})
        entrada = _entrada(
            [_h(ATTR, [INVENTADO]), _h(B12, [INVENTADO])], ["01", "01"]
        )

        _correr(entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch)

        assert len(agente.pedidos) == 1
        assert len(agente.pedidos[0]) == 2

    def test_la_fuente_nueva_se_suma_sin_borrar_las_viejas(self, monkeypatch):
        """No se descarta nada: la cita fallida queda, con su veredicto."""
        agente = _AgenteFalso({0: [Source(pmid=OFRECIDO, title="Fabry disease")]})
        entrada = _entrada([_h(ATTR, [INVENTADO])], ["01"])

        resultado = _correr(
            entrada, {INVENTADO: _discordante(INVENTADO)}, {"01": agente}, monkeypatch
        )

        pmids = [s.pmid for s in resultado.consensus[0].hypothesis.sources]
        assert INVENTADO in pmids and OFRECIDO in pmids


# ── El prompt de recitación de BaseAgent ──────────────────────────────────────

class TestPromptDeRecitacion:

    def test_incluye_los_motivos_y_los_pmids_ofrecidos(self):
        from backend.agents.agent_01_literature import LiteratureAnalystAgent

        prompt = LiteratureAnalystAgent()._build_recitation_prompt(
            [(ATTR, [f"PMID {INVENTADO}: ese PMID no existe en PubMed"])],
            [f"[PMID: {OFRECIDO}] Fabry disease"],
        )

        assert ATTR in prompt
        assert INVENTADO in prompt
        assert OFRECIDO in prompt
        assert "NO inventes PMIDs" in prompt

    def test_el_agente_02_agrega_el_contexto_genomico(self):
        """Sin el bloque genómico, el Agente 02 recita a ciegas (tarea 6.1b)."""
        from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
        from backend.models.genomics import GenomicContext

        ctx = GenomicContext(genes=["TTR"], variants=["p.Val30Met"])
        prompt = GenomicsSpecialistAgent(genomic_context=ctx)._build_recitation_prompt(
            [(ATTR, ["motivo"])], [f"[PMID: {OFRECIDO}] Fabry disease"]
        )

        assert "TTR" in prompt
        assert OFRECIDO in prompt

    def test_parseo_descarta_indices_fuera_de_rango(self):
        from backend.agents.agent_01_literature import LiteratureAnalystAgent

        raw = json.dumps({"recitations": [
            {"hypothesis": 99, "sources": [{"pmid": OFRECIDO, "title": "X"}]},
            {"hypothesis": 1, "sources": [{"pmid": OFRECIDO, "title": "Fabry disease"}]},
        ]})
        parseado = LiteratureAnalystAgent()._parse_recitation(raw, total=1)

        assert list(parseado) == [0]

    def test_parseo_sanea_los_campos_de_verificacion(self):
        """El saneamiento del hallazgo G también cubre la recitación."""
        from backend.agents.agent_01_literature import LiteratureAnalystAgent

        raw = json.dumps({"recitations": [{"hypothesis": 1, "sources": [
            {"pmid": OFRECIDO, "title": "Fabry disease", "verified": True}
        ]}]})
        fuentes = LiteratureAnalystAgent()._parse_recitation(raw, total=1)[0]

        assert fuentes[0].verified is None
