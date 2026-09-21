"""
Tests del Agente 04 — Árbitro Verificador (backend/agents/agent_04_arbiter.py).

El LLM está mockeado en todos los tests: ninguno toca la red ni consume cuota
de Groq. Lo que se prueba es que las guardas se sostienen ante cualquier cosa
que devuelva el modelo — incluida una respuesta que intenta descartar una
hipótesis, subir un nivel o inventar referencias.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import asyncio
import json

import pytest

from backend.agents.agent_04_arbiter import ArbiterAgent
from backend.models.arbitration import ArbitrationInput, ArbitrationStatus
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Critique, RetrievedArticleRef
from backend.pipeline.verification import SourceStatus, SourceVerification

ATTR = "Amiloidosis ATTR hereditaria como causa de la neuropatía axonal"
ATTR_OTRA = "Neuropatía axonal secundaria a amiloidosis hereditaria por transtiretina"
B12 = "Déficit de vitamina B12 inducido por metformina"


def _h(text: str, pmids: list[str] | None = None,
       level: EvidenceLevel = EvidenceLevel.II) -> Hypothesis:
    return Hypothesis(
        text=text, priority=Priority.HIGH, evidence_level=level,
        rationale="Fundamento de prueba.",
        sources=[Source(pmid=p, title=f"Artículo {p}") for p in (pmids or [])],
    )


def _entrada(**kwargs) -> ArbitrationInput:
    base = dict(
        hypotheses=[_h(ATTR, ["111"]), _h(ATTR_OTRA, ["222"]), _h(B12, ["333"])],
        hypothesis_agents=["01", "02", "03"],
        agent_names={"01": "Analista de Literatura", "02": "Especialista Genómica",
                     "03": "Consultor Clínico"},
    )
    base.update(kwargs)
    return ArbitrationInput(**base)


class _LlmFalso:
    """
    Sustituye `BaseAgent._call_llm` y registra los prompts que recibió.

    `respuestas` se consume en orden: primero la agrupación, después los
    veredictos. Un elemento que sea una excepción se levanta.
    """

    def __init__(self, *respuestas) -> None:
        self.respuestas = list(respuestas)
        self.prompts: list[str] = []

    def instalar(self, monkeypatch) -> "_LlmFalso":
        def fake(self_agent, prompt):  # noqa: ANN001
            self.prompts.append(prompt)
            if not self.respuestas:
                raise AssertionError("El agente llamó al LLM más veces de las previstas")
            item = self.respuestas.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(
            "backend.agents.base_agent.BaseAgent._call_llm", fake
        )
        return self


def _grupos(*grupos) -> str:
    return json.dumps({"groups": list(grupos)})


def _veredictos(*pares) -> str:
    return json.dumps({
        "verdicts": [{"hypothesis": n, "verdict": v} for n, v in pares]
    })


def _arbitrar(entrada, verifs=None) -> object:
    return asyncio.run(ArbiterAgent().arbitrate(entrada, verifs or {}))


# ── 5.1 Contrato básico ───────────────────────────────────────────────────────

class TestContrato:

    def test_no_participa_del_debate(self):
        with pytest.raises(NotImplementedError, match="arbitrate"):
            ArbiterAgent().run("contexto clínico")

    def test_identidad_del_agente(self):
        assert (ArbiterAgent.AGENT_ID, ArbiterAgent.AGENT_NAME) == ("04", "Árbitro Verificador")

    def test_produce_consenso_desde_el_debate(self, monkeypatch):
        _LlmFalso(_grupos([1, 2], [3]), _veredictos((1, "Respaldo parcial."))).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert len(resultado.consensus) == 2
        assert resultado.summary.input_hypotheses == 3
        assert resultado.summary.consensus_hypotheses == 2
        assert resultado.summary.status is ArbitrationStatus.OK

    def test_sin_hipotesis_no_llama_al_llm(self, monkeypatch):
        llm = _LlmFalso().instalar(monkeypatch)

        resultado = _arbitrar(_entrada(hypotheses=[], hypothesis_agents=[]))

        assert resultado.consensus == []
        assert resultado.summary.status is ArbitrationStatus.SIN_HIPOTESIS
        assert llm.prompts == []


# ── 5.2 Agrupación por índices ────────────────────────────────────────────────

class TestAgrupacion:

    def test_el_prompt_numera_las_hipotesis(self, monkeypatch):
        llm = _LlmFalso(_grupos([1], [2], [3]), _veredictos()).instalar(monkeypatch)

        _arbitrar(_entrada())

        assert "1. [Analista de Literatura]" in llm.prompts[0]
        assert "3. [Consultor Clínico]" in llm.prompts[0]

    def test_indice_inventado_no_rompe(self, monkeypatch):
        """Cae en normalize_partition: el 99 se ignora y nada se pierde."""
        _LlmFalso(_grupos([1, 99], [2], [3]), _veredictos()).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        agrupadas = [h for c in resultado.consensus for h in c.grouped]
        assert len(agrupadas) == 3

    def test_hipotesis_omitida_por_el_modelo_se_conserva(self, monkeypatch):
        _LlmFalso(_grupos([1]), _veredictos()).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert sum(len(c.grouped) for c in resultado.consensus) == 3

    def test_respaldo_multiple_cuando_agrupa(self, monkeypatch):
        _LlmFalso(_grupos([1, 2], [3]), _veredictos()).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.consensus[0].support_count == 2
        assert "Analista de Literatura" in resultado.consensus[0].supporting_agents
        assert "Especialista Genómica" in resultado.consensus[0].supporting_agents


# ── 5.3 Veredictos ────────────────────────────────────────────────────────────

class TestVeredictos:

    def test_el_veredicto_se_asigna_a_su_hipotesis(self, monkeypatch):
        _LlmFalso(
            _grupos([1], [2], [3]),
            _veredictos((2, "Hipótesis sin respaldo verificable.")),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.consensus[1].verdict == "Hipótesis sin respaldo verificable."
        assert resultado.consensus[0].verdict == ""

    def test_el_prompt_informa_estado_y_nivel_ya_calculados(self, monkeypatch):
        """
        Sin veredictos de verificación las hipótesis quedan `pendiente`, no
        `especulativa`: citaron un PMID que no se pudo contrastar, que es un
        problema de infraestructura y no de la cita.
        """
        llm = _LlmFalso(_grupos([1], [2], [3]), _veredictos()).instalar(monkeypatch)

        _arbitrar(_entrada())

        assert "estado: pendiente" in llm.prompts[1]
        assert "nivel de evidencia efectivo: III" in llm.prompts[1]

    def test_el_prompt_informa_una_hipotesis_respaldada(self, monkeypatch):
        llm = _LlmFalso(_grupos([1]), _veredictos()).instalar(monkeypatch)
        entrada = _entrada(hypotheses=[_h(ATTR, ["111"])], hypothesis_agents=["01"])
        verifs = {"111": SourceVerification(
            pmid="111", status=SourceStatus.VERIFICADA, claimed_title="Artículo 111",
            actual_title="Artículo 111", match_score=1.0,
            publication_types=["Randomized Controlled Trial"],
        )}

        _arbitrar(entrada, verifs)

        assert "estado: respaldada" in llm.prompts[1]
        assert "nivel de evidencia efectivo: II" in llm.prompts[1]
        assert "fuentes verificadas: 1" in llm.prompts[1]

    def test_un_veredicto_que_contradice_el_estado_no_altera_el_estado(self, monkeypatch):
        """
        El modelo puede escribir lo que quiera: el estado y el nivel salen de la
        clasificación determinista, que él no toca.
        """
        _LlmFalso(
            _grupos([1], [2], [3]),
            _veredictos((1, "Hipótesis sólidamente respaldada por nivel I de evidencia.")),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        # La hipótesis sigue teniendo el nivel declarado por su agente: el
        # veredicto es texto, no un canal para cambiar la clasificación.
        assert resultado.consensus[0].hypothesis.evidence_level is EvidenceLevel.II

    def test_veredicto_vacio_se_ignora(self, monkeypatch):
        _LlmFalso(_grupos([1], [2], [3]), _veredictos((1, "   "))).instalar(monkeypatch)
        assert _arbitrar(_entrada()).consensus[0].verdict == ""

    def test_indice_de_veredicto_invalido_se_ignora(self, monkeypatch):
        _LlmFalso(_grupos([1], [2], [3]), _veredictos((99, "Algo"))).instalar(monkeypatch)
        resultado = _arbitrar(_entrada())
        assert all(c.verdict == "" for c in resultado.consensus)


# ── 5.4 Guardas de salida del modelo ──────────────────────────────────────────

class TestGuardas:
    """
    Modeladas sobre la guarda anti-invención del Agente 02
    (TestGuardaAntiInvencion en tests/test_agent_02_genomics.py).
    """

    def test_referencia_inventada_descarta_el_veredicto(self, monkeypatch):
        _LlmFalso(
            _grupos([1], [2], [3]),
            _veredictos((1, "Respaldada por el estudio PMID 98765432.")),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.consensus[0].verdict == ""
        assert resultado.summary.discarded_references == 1

    def test_pmid_que_si_estaba_en_la_entrada_se_acepta(self, monkeypatch):
        _LlmFalso(
            _grupos([1], [2], [3]),
            _veredictos((1, "El artículo 111 respalda parcialmente la hipótesis.")),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert "111" in resultado.consensus[0].verdict
        assert resultado.summary.discarded_references == 0

    def test_pmid_del_conjunto_recuperado_se_acepta(self, monkeypatch):
        _LlmFalso(
            _grupos([1], [2], [3]),
            _veredictos((1, "Coincide con el artículo 99999901 recuperado.")),
        ).instalar(monkeypatch)

        entrada = _entrada(
            retrieved_articles=[RetrievedArticleRef(pmid="99999901", title="Artículo")]
        )
        resultado = _arbitrar(entrada)

        assert resultado.summary.discarded_references == 0

    def test_el_modelo_no_puede_descartar_una_hipotesis(self, monkeypatch):
        """Devuelve un grupo de menos: la hipótesis reaparece como grupo propio."""
        _LlmFalso(_grupos([1], [2]), _veredictos()).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        textos = [c.hypothesis.text for c in resultado.consensus]
        assert B12 in textos
        assert sum(len(c.grouped) for c in resultado.consensus) == 3

    def test_el_modelo_no_puede_subir_un_nivel_de_evidencia(self, monkeypatch):
        """
        La hipótesis declara I pero su única fuente verificada es un case report:
        el tope de evidence.py manda, y el Árbitro no lo toca.
        """
        _LlmFalso(
            _grupos([1]),
            _veredictos((1, "Evidencia de nivel I, meta-análisis concluyente.")),
        ).instalar(monkeypatch)

        entrada = _entrada(
            hypotheses=[_h(ATTR, ["111"], EvidenceLevel.I)], hypothesis_agents=["01"]
        )
        verifs = {"111": SourceVerification(
            pmid="111", status=SourceStatus.VERIFICADA, claimed_title="Artículo 111",
            actual_title="Artículo 111", match_score=1.0,
            publication_types=["Case Reports"],
        )}

        resultado = _arbitrar(entrada, verifs)

        from backend.pipeline.evidence import classify_hypothesis
        evaluacion = classify_hypothesis(resultado.consensus[0].hypothesis, verifs)
        assert evaluacion.effective_level is EvidenceLevel.III

    def test_el_enunciado_nunca_sale_del_modelo(self, monkeypatch):
        """Aunque el modelo devuelva texto, el enunciado sale de un agente."""
        _LlmFalso(
            json.dumps({"groups": [[1, 2]], "hypotheses": ["Texto inventado por el LLM"]}),
            _veredictos(),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada(
            hypotheses=[_h(ATTR), _h(ATTR_OTRA)], hypothesis_agents=["01", "02"]
        ))

        assert resultado.consensus[0].hypothesis.text in (ATTR, ATTR_OTRA)


# ── 5.5 Fallbacks ─────────────────────────────────────────────────────────────

class TestFallback:

    def test_llm_caido_devuelve_consenso_degradado(self, monkeypatch):
        _LlmFalso(ConnectionError("Groq no disponible (simulado)")).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.summary.status is ArbitrationStatus.DEGRADADO
        assert len(resultado.consensus) == 3
        assert all(c.verdict == "" for c in resultado.consensus)

    def test_json_no_parseable_devuelve_degradado(self, monkeypatch):
        _LlmFalso("Esto no es JSON en absoluto").instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.summary.status is ArbitrationStatus.DEGRADADO
        assert sum(len(c.grouped) for c in resultado.consensus) == 3

    def test_json_sin_clave_groups_devuelve_degradado(self, monkeypatch):
        _LlmFalso(json.dumps({"resultado": "ok"})).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.summary.status is ArbitrationStatus.DEGRADADO

    def test_fallo_de_veredictos_conserva_el_consenso(self, monkeypatch):
        """Los veredictos son redacción: sin ellos el consenso sigue sirviendo."""
        _LlmFalso(
            _grupos([1, 2], [3]),
            ConnectionError("Groq no disponible (simulado)"),
        ).instalar(monkeypatch)

        resultado = _arbitrar(_entrada())

        assert resultado.summary.status is ArbitrationStatus.OK
        assert len(resultado.consensus) == 2
        assert resultado.consensus[0].support_count == 2

    def test_las_contradicciones_sobreviven_al_fallback(self, monkeypatch):
        """No dependen del LLM: salen de las críticas ya estructuradas."""
        _LlmFalso(ConnectionError("caído")).instalar(monkeypatch)

        entrada = _entrada(
            hypotheses=[_h(ATTR)], hypothesis_agents=["01"],
            critiques=[Critique(
                from_agent_id="03", from_agent_name="Consultor Clínico",
                target_agent_id="01", target_hypothesis=ATTR,
                critique_text="Sin biopsia no se sostiene.", severity="HIGH",
            )],
            final_by_agent={"01": [_h(ATTR)]},
        )
        resultado = _arbitrar(entrada)

        assert len(resultado.consensus[0].contradictions) == 1
        assert resultado.summary.contradictions == 1

    def test_verificacion_no_disponible_no_rompe(self, monkeypatch):
        """PubMed caído: el consenso se arma igual, sin veredictos de respaldo."""
        _LlmFalso(_grupos([1], [2], [3]), _veredictos()).instalar(monkeypatch)

        resultado = _arbitrar(_entrada(), verifs={})

        assert len(resultado.consensus) == 3


# ── 5.6 Privacidad en los logs ────────────────────────────────────────────────

class TestPrivacidad:

    def test_el_log_no_filtra_la_respuesta_del_modelo(self, monkeypatch, capsys):
        secreto = "Paciente masculino de 42 años con neuropatía axonal"
        _LlmFalso(f"No es JSON. {secreto}").instalar(monkeypatch)

        _arbitrar(_entrada())

        stderr = capsys.readouterr().err
        assert "fallback (ValueError)" in stderr
        assert secreto not in stderr
        assert "42 años" not in stderr

    def test_el_log_no_filtra_texto_clinico_ante_una_excepcion(self, monkeypatch, capsys):
        _LlmFalso(ConnectionError("fallo consultando el caso del paciente")).instalar(monkeypatch)

        _arbitrar(_entrada())

        stderr = capsys.readouterr().err
        assert "fallback (ConnectionError)" in stderr
        assert "paciente" not in stderr

    def test_el_log_identifica_el_paso(self, monkeypatch, capsys):
        _LlmFalso(ConnectionError("x")).instalar(monkeypatch)

        _arbitrar(_entrada())

        assert "Agente 04 — agrupación de hipótesis" in capsys.readouterr().err
