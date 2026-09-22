"""
Tests de la clase base de agentes (backend/agents/base_agent.py).

Cubre el parseo de la respuesta del LLM: extracción del JSON, construcción de
hipótesis y, sobre todo, el **saneamiento de las fuentes** (hallazgo G). Ningún
test llama a un LLM ni a la red: las respuestas se construyen a mano.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino de 42 años.
"""

import json

import pytest

from backend.agents.base_agent import BaseAgent
from backend.models.hypothesis import EvidenceLevel, Priority

_HIPOTESIS_BASE = (
    "Déficit de vitamina B12 inducido por metformina en varón de 42 años "
    "con neuropatía axonal sensitivomotora."
)


def _respuesta(sources: list[dict] | None = None) -> str:
    """Arma una respuesta JSON válida del modelo con las fuentes dadas."""
    return json.dumps({
        "hypotheses": [{
            "text": _HIPOTESIS_BASE,
            "priority": "HIGH",
            "evidence_level": "II",
            "rationale": "La metformina interfiere con la absorción ileal de B12.",
            "sources": sources if sources is not None else [],
        }]
    })


# ── Saneamiento de fuentes (hallazgo G) ───────────────────────────────────────

class TestSaneamientoDeFuentes:
    """
    Los campos de verificación son salida de PubMed, nunca entrada del modelo.

    Antes del fix, `Source(**s)` aceptaba lo que el LLM escribiera y el dato
    autodeclarado viajaba en el Report interno hasta que evidence.py lo ignoraba.
    """

    def test_verified_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verified": True,
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.verified is None

    def test_verification_status_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verification_status": "verificada",
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.verification_status is None

    def test_tipos_de_publicacion_inventados_se_descartan(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "publication_types": ["Meta-Analysis", "Randomized Controlled Trial"],
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.publication_types == []

    def test_actual_title_autodeclarado_se_descarta(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "actual_title": "Cualquier cosa que el modelo haya escrito",
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.actual_title is None

    def test_los_cuatro_campos_juntos_se_descartan(self):
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "verified": True,
            "verification_status": "verificada",
            "actual_title": "Otro título",
            "publication_types": ["Meta-Analysis"],
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert (source.verified, source.verification_status, source.actual_title) == (
            None, None, None,
        )
        assert source.publication_types == []

    def test_los_campos_declarables_se_conservan(self):
        """El saneamiento no debe llevarse puesto lo que el agente sí debe citar."""
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "journal": "Diabetes Care",
            "year": 2012,
            "url": "https://pubmed.ncbi.nlm.nih.gov/22439958/",
            "verified": True,
        }])
        source = BaseAgent.parse_hypotheses(raw)[0].sources[0]
        assert source.pmid == "22439958"
        assert source.title == "Metformin-associated vitamin B12 deficiency"
        assert source.journal == "Diabetes Care"
        assert source.year == 2012
        assert source.url == "https://pubmed.ncbi.nlm.nih.gov/22439958/"

    def test_campo_desconocido_no_rompe_el_parseo(self):
        """Un campo de más no invalida la hipótesis: no se descartan hipótesis."""
        raw = _respuesta([{
            "pmid": "22439958",
            "title": "Metformin-associated vitamin B12 deficiency",
            "confianza_del_modelo": 0.97,
        }])
        hypotheses = BaseAgent.parse_hypotheses(raw)
        assert len(hypotheses) == 1
        assert hypotheses[0].sources[0].pmid == "22439958"

    def test_fuente_sin_titulo_sigue_siendo_error(self):
        """Comportamiento previo al fix: una fuente sin título no valida."""
        raw = _respuesta([{"pmid": "22439958"}])
        with pytest.raises(Exception):
            BaseAgent.parse_hypotheses(raw)


# ── Extracción de JSON ────────────────────────────────────────────────────────

class TestExtractJson:

    def test_json_puro(self):
        assert BaseAgent.extract_json('{"a": 1}') == {"a": 1}

    def test_fence_de_markdown_con_lenguaje(self):
        assert BaseAgent.extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fence_de_markdown_sin_lenguaje(self):
        assert BaseAgent.extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_json_embebido_en_texto_libre(self):
        raw = 'Claro, acá va el análisis:\n{"a": 1}\nEspero que sirva.'
        assert BaseAgent.extract_json(raw) == {"a": 1}

    def test_sin_json_lanza_error(self):
        with pytest.raises(ValueError, match="no contiene JSON válido"):
            BaseAgent.extract_json("No encontré nada relevante.")


# ── Parseo de hipótesis ───────────────────────────────────────────────────────

class TestParseHypotheses:

    def test_hipotesis_valida(self):
        hypothesis = BaseAgent.parse_hypotheses(_respuesta())[0]
        assert hypothesis.text == _HIPOTESIS_BASE
        assert hypothesis.priority is Priority.HIGH
        assert hypothesis.evidence_level is EvidenceLevel.II
        assert hypothesis.sources == []

    def test_sin_hipotesis_lanza_error(self):
        with pytest.raises(ValueError, match="ninguna hipótesis"):
            BaseAgent.parse_hypotheses('{"hypotheses": []}')

    def test_hipotesis_sin_campo_obligatorio_lanza_error(self):
        raw = json.dumps({"hypotheses": [{"text": "Algo", "priority": "HIGH"}]})
        with pytest.raises(ValueError, match="malformada"):
            BaseAgent.parse_hypotheses(raw)

    def test_prioridad_invalida_lanza_error(self):
        raw = json.dumps({"hypotheses": [{
            "text": _HIPOTESIS_BASE,
            "priority": "URGENTÍSIMA",
            "evidence_level": "II",
            "rationale": "…",
        }]})
        with pytest.raises(ValueError):
            BaseAgent.parse_hypotheses(raw)

    def test_varias_hipotesis_conservan_el_orden(self):
        raw = json.dumps({"hypotheses": [
            {"text": f"Hipótesis {i}", "priority": "LOW",
             "evidence_level": "III", "rationale": "…"}
            for i in range(3)
        ]})
        textos = [h.text for h in BaseAgent.parse_hypotheses(raw)]
        assert textos == ["Hipótesis 0", "Hipótesis 1", "Hipótesis 2"]
