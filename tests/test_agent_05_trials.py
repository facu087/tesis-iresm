"""
Tests del Agente 05 — Navegador de Ensayos (backend/agents/agent_05_trials.py).

El LLM y los clientes de ClinicalTrials.gov y Orphanet están mockeados: ningún
test sale a la red. Los circuit breakers son globales, así que se resetean
antes de cada test.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.agent_05_trials import TrialNavigatorAgent
from backend.external.orphanet import RareDisease
from backend.external.rate_limiter import (
    ApiUnavailableError,
    ExternalApiError,
    clinical_trials_breaker,
    orphanet_breaker,
)
from backend.models.hypothesis import EvidenceLevel, Priority
from backend.models.trial import (
    ClinicalTrial,
    PatientDemographics,
    TrialCandidate,
    TrialNavigationInput,
)

_PERFIL = (
    "Perfil: Paciente masculino de 42 años con DM2 de 10 años de evolución\n"
    "Motivo de consulta: neuropatía axonal sensitivomotora"
)


@pytest.fixture(autouse=True)
def _reset_breakers():
    """Los breakers son globales: sin esto un test contagia al siguiente."""
    clinical_trials_breaker.reset()
    orphanet_breaker.reset()
    yield
    clinical_trials_breaker.reset()
    orphanet_breaker.reset()


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _candidate(
    text: str = "Amiloidosis hereditaria por transtiretina",
    status: str | None = None,
) -> TrialCandidate:
    return TrialCandidate(
        text=text,
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        status=status,
    )


def _input(**overrides) -> TrialNavigationInput:
    datos = dict(
        condition_en="axonal sensorimotor polyneuropathy",
        biomarker_terms=["TTR"],
        demographics=PatientDemographics(age_years=42.0, sex="MALE"),
        eligibility_profile=_PERFIL,
        candidates=[_candidate()],
    )
    datos.update(overrides)
    return TrialNavigationInput(**datos)


def _trial(nct_id: str = "NCT04000001", **overrides) -> ClinicalTrial:
    datos = dict(
        nct_id=nct_id,
        title=f"Ensayo {nct_id}",
        status="RECRUITING",
        brief_summary="Resumen.",
        conditions=["Amyloidosis"],
        min_age="18 Years",
        max_age="75 Years",
        sex="ALL",
        locations=["United States"],
        eligibility_criteria="Inclusión: diagnóstico confirmado.",
    )
    datos.update(overrides)
    return ClinicalTrial(**datos)


_PLAN_OK = json.dumps({
    "terms": [{
        "candidate": 1,
        "condition_en": "hereditary transthyretin amyloidosis",
        "synonyms_en": ["hereditary ATTR amyloidosis"],
    }]
})


def _eval_ok(nct_ids: list[str], compatibility: str = "alta") -> str:
    return json.dumps({
        "evaluations": [
            {
                "nct_id": nct,
                "compatibility": compatibility,
                "rationale": "Coincide con la condición estudiada.",
                "criteria_to_verify": ["Confirmar biopsia", "Revisar función renal"],
            }
            for nct in nct_ids
        ]
    })


def _agent_with_llm(respuestas: list) -> tuple[TrialNavigatorAgent, MagicMock]:
    """
    Devuelve el agente con `_call_llm` mockeado.

    `respuestas` se consume en orden: primero la planificación, después la
    evaluación. Un elemento que sea excepción se lanza.
    """
    agent = TrialNavigatorAgent()
    mock = MagicMock(side_effect=respuestas)
    agent._call_llm = mock  # type: ignore[method-assign]
    return agent, mock


def _patch_search(side_effect):
    return patch("backend.external.clinical_trials.search", side_effect=side_effect)


def _patch_orphanet(side_effect=None, return_value=None):
    """Mockea OrphanetClient como context manager asíncrono."""
    cliente = MagicMock()
    cliente.search = AsyncMock(
        side_effect=side_effect,
        return_value=[] if return_value is None and side_effect is None else return_value,
    )
    contexto = MagicMock()
    contexto.__aenter__ = AsyncMock(return_value=cliente)
    contexto.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "backend.agents.agent_05_trials.OrphanetClient", return_value=contexto
    ), cliente


# ── 4.1 Contrato del agente ────────────────────────────────────────────────────

class TestContratoDelAgente:
    def test_identidad(self):
        agent = TrialNavigatorAgent()
        assert agent.AGENT_ID == "05"
        assert agent.AGENT_NAME == "Navegador de Ensayos"

    def test_run_no_participa_del_debate(self):
        with pytest.raises(NotImplementedError, match="navigate"):
            TrialNavigatorAgent().run("contexto clínico")

    def test_no_instancia_groq_directamente(self):
        """El swap de proveedor se hace en BaseAgent._call_llm(), no acá."""
        import backend.agents.agent_05_trials as modulo

        fuente = open(modulo.__file__, encoding="utf-8").read()
        assert "from groq" not in fuente
        assert "import groq" not in fuente
        assert "Groq(" not in fuente

    def test_system_prompt_prohibe_diagnosticar_y_afirmar_elegibilidad(self):
        prompt = TrialNavigatorAgent.SYSTEM_PROMPT
        assert "NO emitas diagnósticos" in prompt
        assert "elegib" in prompt


# ── 4.2 Planificación ──────────────────────────────────────────────────────────

class TestPlanificacion:
    @pytest.mark.asyncio
    async def test_planificacion_exitosa(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.summary.planificacion == "ok"
        assert "hereditary transthyretin amyloidosis" in resultado.summary.terminos_consultados

    @pytest.mark.asyncio
    async def test_falla_del_llm_en_la_planificacion(self):
        agent, _ = _agent_with_llm([
            RuntimeError("Groq caído"),
            _eval_ok(["NCT04000001"]),
        ])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.summary.planificacion == "fallback"
        # La búsqueda base igual corrió.
        assert len(resultado.trials) == 1

    @pytest.mark.asyncio
    async def test_json_invalido_en_la_planificacion(self):
        agent, _ = _agent_with_llm(["no soy JSON", _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.summary.planificacion == "fallback"

    @pytest.mark.asyncio
    async def test_candidata_inexistente_se_ignora(self):
        plan = json.dumps({
            "terms": [{
                "candidate": 7,
                "condition_en": "inexistent condition",
                "synonyms_en": [],
            }]
        })
        agent, _ = _agent_with_llm([plan, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]) as mock_search, patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.summary.planificacion == "fallback"
        condiciones = [kw["condition"] for _, kw in mock_search.call_args_list]
        assert "inexistent condition" not in condiciones

    @pytest.mark.asyncio
    async def test_termino_con_datos_demograficos_se_descarta(self):
        plan = json.dumps({
            "terms": [{
                "candidate": 1,
                "condition_en": "42-year-old male amyloidosis",
                "synonyms_en": [],
            }]
        })
        agent, _ = _agent_with_llm([plan, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]) as mock_search, patch_orph:
            await agent.navigate(_input())
        condiciones = [kw["condition"] for _, kw in mock_search.call_args_list]
        assert all("42" not in c for c in condiciones)

    @pytest.mark.asyncio
    async def test_sin_candidatas_no_llama_al_llm_para_planificar(self):
        agent, mock_llm = _agent_with_llm([_eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input(candidates=[]))
        assert resultado.summary.planificacion == "sin_candidatas"
        assert mock_llm.call_count == 1  # solo la evaluación


# ── 4.3 Búsqueda en ClinicalTrials.gov ─────────────────────────────────────────

class TestBusqueda:
    @pytest.mark.asyncio
    async def test_consulta_los_dos_estados_de_reclutamiento(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]) as mock_search, patch_orph:
            await agent.navigate(_input())
        for _, kw in mock_search.call_args_list:
            assert kw["statuses"] == ("RECRUITING", "NOT_YET_RECRUITING")

    @pytest.mark.asyncio
    async def test_ensayo_que_todavia_no_abrio_se_incluye(self):
        futuro = _trial("NCT04000002", status="NOT_YET_RECRUITING")
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000002"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [futuro]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials[0].status == "NOT_YET_RECRUITING"

    @pytest.mark.asyncio
    async def test_termino_principal_sin_resultados_prueba_el_sinonimo(self):
        def buscar(**kw):
            if kw["condition"] == "hereditary ATTR amyloidosis":
                return [_trial("NCT04000002")]
            return []

        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000002"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(buscar) as mock_search, patch_orph:
            resultado = await agent.navigate(_input())
        condiciones = [kw["condition"] for _, kw in mock_search.call_args_list]
        assert "hereditary transthyretin amyloidosis" in condiciones
        assert "hereditary ATTR amyloidosis" in condiciones
        assert [t.nct_id for t in resultado.trials] == ["NCT04000002"]

    @pytest.mark.asyncio
    async def test_clinicaltrials_caido(self):
        agent, _ = _agent_with_llm([_PLAN_OK])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(TimeoutError("timeout")), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials == []
        assert resultado.summary.estado_clinicaltrials == "no_disponible"
        assert resultado.summary.evaluacion == "sin_ensayos"

    @pytest.mark.asyncio
    async def test_falla_parcial(self):
        def buscar(**kw):
            if kw["condition"] == "axonal sensorimotor polyneuropathy":
                return [_trial()]
            raise RuntimeError("ClinicalTrials.gov devolvió error 500")

        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(buscar), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.summary.estado_clinicaltrials == "parcial"
        assert [t.nct_id for t in resultado.trials] == ["NCT04000001"]

    @pytest.mark.asyncio
    async def test_sin_condicion_ni_biomarcadores_no_hay_busqueda_base(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        entrada = _input(condition_en="", biomarker_terms=[])
        with _patch_search(lambda **kw: [_trial()]) as mock_search, patch_orph:
            await agent.navigate(entrada)
        condiciones = [kw["condition"] for _, kw in mock_search.call_args_list]
        assert "neuropatía axonal sensitivomotora" not in condiciones
        assert condiciones == ["hereditary transthyretin amyloidosis"]

    @pytest.mark.asyncio
    async def test_sin_consulta_cuando_no_hay_nada_para_buscar(self):
        agent, _ = _agent_with_llm([])
        patch_orph, _ = _patch_orphanet()
        entrada = _input(condition_en="", biomarker_terms=[], candidates=[])
        with _patch_search(lambda **kw: []), patch_orph:
            resultado = await agent.navigate(entrada)
        assert resultado.summary.estado_clinicaltrials == "sin_consulta"

    @pytest.mark.asyncio
    async def test_excluye_por_edad_y_lo_cuenta(self):
        pediatrico = _trial("NCT04000003", min_age="6 Years", max_age="17 Years")
        agent, _ = _agent_with_llm([_PLAN_OK])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [pediatrico]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials == []
        assert resultado.summary.excluidos_por_edad == 1
        assert resultado.summary.encontrados == 1

    @pytest.mark.asyncio
    async def test_excluye_por_sexo_y_lo_cuenta(self):
        femenino = _trial("NCT04000004", sex="FEMALE")
        agent, _ = _agent_with_llm([_PLAN_OK])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [femenino]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials == []
        assert resultado.summary.excluidos_por_sexo == 1


# ── 4.4 Orphanet ───────────────────────────────────────────────────────────────

_ATTR = RareDisease(
    orpha_code="271861",
    name="Hereditary ATTR amyloidosis",
    definition="",
)


class TestOrphanet:
    @pytest.mark.asyncio
    async def test_coincidencia_exacta_con_un_sinonimo(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, cliente = _patch_orphanet(
            side_effect=lambda nombre, *a, **kw: (
                [_ATTR] if nombre == "hereditary ATTR amyloidosis" else []
            )
        )
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert len(resultado.rare_diseases) == 1
        marca = resultado.rare_diseases[0]
        assert marca.orpha_code == "271861"
        assert marca.matched_term == "hereditary ATTR amyloidosis"
        assert marca.url.endswith("/271861")
        assert marca.hypothesis == "Amiloidosis hereditaria por transtiretina"
        assert resultado.summary.estado_orphanet == "ok"

    @pytest.mark.asyncio
    async def test_coincidencia_por_inclusion_no_marca(self):
        parcial = RareDisease(
            orpha_code="64746",
            name="Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy",
            definition="",
        )
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet(return_value=[parcial])
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.rare_diseases == []
        assert resultado.summary.estado_orphanet == "ok"

    @pytest.mark.asyncio
    async def test_entorno_sin_credencial_consulta_igual(self, monkeypatch):
        monkeypatch.delenv("ORPHANET_API_KEY", raising=False)
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, cliente = _patch_orphanet(return_value=[_ATTR])
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert cliente.search.await_count >= 1
        assert len(resultado.rare_diseases) == 1

    @pytest.mark.asyncio
    async def test_credencial_rechazada_deja_no_disponible(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet(
            side_effect=ExternalApiError("Orphanet", "rechazó la credencial", status_code=401)
        )
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.rare_diseases == []
        assert resultado.summary.estado_orphanet == "no_disponible"

    @pytest.mark.asyncio
    async def test_orphanet_caido_no_frena_los_ensayos(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet(
            side_effect=ApiUnavailableError("Orphanet", "503 en todos los intentos")
        )
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert [t.nct_id for t in resultado.trials] == ["NCT04000001"]
        assert resultado.rare_diseases == []
        assert resultado.summary.estado_orphanet == "no_disponible"
        assert resultado.summary.estado_clinicaltrials == "ok"

    @pytest.mark.asyncio
    async def test_sin_planes_no_consulta_orphanet(self):
        agent, _ = _agent_with_llm([_eval_ok(["NCT04000001"])])
        patch_orph, cliente = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input(candidates=[]))
        assert cliente.search.await_count == 0
        assert resultado.summary.estado_orphanet == "sin_consulta"

    @pytest.mark.asyncio
    async def test_no_pide_genes_a_orphanet(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, cliente = _patch_orphanet(return_value=[_ATTR])
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            await agent.navigate(_input())
        cliente.get_genes.assert_not_called()


# ── 4.5 Evaluación de compatibilidad ───────────────────────────────────────────

class TestEvaluacion:
    @pytest.mark.asyncio
    async def test_evaluacion_valida(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        trial = resultado.trials[0]
        assert trial.compatibility == "alta"
        assert trial.compatibility_rationale
        assert len(trial.criteria_to_verify) == 2
        assert resultado.summary.evaluacion == "ok"

    @pytest.mark.asyncio
    async def test_nct_inventado_por_el_llm_se_descarta(self):
        respuesta = json.dumps({
            "evaluations": [
                {"nct_id": "NCT99999999", "compatibility": "alta", "rationale": "x"},
                {"nct_id": "NCT04000001", "compatibility": "media", "rationale": "y"},
            ]
        })
        agent, _ = _agent_with_llm([_PLAN_OK, respuesta])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert [t.nct_id for t in resultado.trials] == ["NCT04000001"]
        assert resultado.trials[0].compatibility == "media"
        assert resultado.summary.evaluaciones_descartadas == 1

    @pytest.mark.asyncio
    async def test_falla_del_llm_en_la_evaluacion(self):
        agent, _ = _agent_with_llm([_PLAN_OK, RuntimeError("Groq caído")])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials[0].compatibility == "sin_evaluar"
        assert resultado.summary.evaluacion == "fallback"

    @pytest.mark.asyncio
    async def test_ensayo_omitido_por_el_llm_queda_sin_evaluar(self):
        def buscar(**kw):
            if kw["condition"] == "axonal sensorimotor polyneuropathy":
                return [_trial("NCT04000001"), _trial("NCT04000002")]
            return []

        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(buscar), patch_orph:
            resultado = await agent.navigate(_input())
        por_id = {t.nct_id: t for t in resultado.trials}
        assert por_id["NCT04000001"].compatibility == "alta"
        assert por_id["NCT04000002"].compatibility == "sin_evaluar"
        assert len(resultado.trials) == 2

    @pytest.mark.asyncio
    async def test_etiqueta_fuera_del_enum_queda_sin_evaluar(self):
        respuesta = json.dumps({
            "evaluations": [
                {"nct_id": "NCT04000001", "compatibility": "excelente", "rationale": "x"}
            ]
        })
        agent, _ = _agent_with_llm([_PLAN_OK, respuesta])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert resultado.trials[0].compatibility == "sin_evaluar"

    @pytest.mark.asyncio
    async def test_compatibilidad_baja_conserva_el_ensayo(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"], "baja")])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        assert len(resultado.trials) == 1
        assert resultado.trials[0].compatibility == "baja"

    @pytest.mark.asyncio
    async def test_criterios_truncados(self):
        respuesta = json.dumps({
            "evaluations": [{
                "nct_id": "NCT04000001",
                "compatibility": "alta",
                "rationale": "x" * 900,
                "criteria_to_verify": ["y" * 400] + [f"criterio {i}" for i in range(9)],
            }]
        })
        agent, _ = _agent_with_llm([_PLAN_OK, respuesta])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        trial = resultado.trials[0]
        assert len(trial.compatibility_rationale) == 600
        assert len(trial.criteria_to_verify) == 5
        assert len(trial.criteria_to_verify[0]) == 200


# ── 4.6 Privacidad y orden final ───────────────────────────────────────────────

class TestPrivacidad:
    @pytest.mark.asyncio
    async def test_las_apis_externas_no_reciben_texto_clinico(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, cliente = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]) as mock_search, patch_orph:
            await agent.navigate(_input())

        enviados = []
        for _, kw in mock_search.call_args_list:
            enviados += [str(kw.get("condition", "")), str(kw.get("keywords", ""))]
        for llamada in cliente.search.await_args_list:
            enviados.append(str(llamada.args[0]) if llamada.args else "")

        for valor in enviados:
            assert "42" not in valor
            assert "masculino" not in valor.lower()
            assert "neuropatía" not in valor.lower()

    @pytest.mark.asyncio
    async def test_el_log_no_repite_la_respuesta_del_llm(self, capsys):
        """`extract_json` mete la respuesta en el mensaje: no puede salir a stderr."""
        eco = f"El paciente {_PERFIL} no es JSON"
        agent, _ = _agent_with_llm([eco, RuntimeError("Groq caído")])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            await agent.navigate(_input())

        capturado = capsys.readouterr()
        assert "masculino" not in capturado.err
        assert "42 años" not in capturado.err
        assert "fallback (ValueError)" in capturado.err

    @pytest.mark.asyncio
    async def test_el_resultado_se_ordena_por_compatibilidad_y_sede(self):
        exterior = _trial("NCT_EXT", locations=["Spain"])
        local = _trial("NCT_LOCAL", locations=["Argentina"])

        def buscar(**kw):
            if kw["condition"] == "axonal sensorimotor polyneuropathy":
                return [exterior, local]
            return []

        respuesta = json.dumps({
            "evaluations": [
                {"nct_id": "NCT_EXT", "compatibility": "alta", "rationale": "x"},
                {"nct_id": "NCT_LOCAL", "compatibility": "alta", "rationale": "y"},
            ]
        })
        agent, _ = _agent_with_llm([_PLAN_OK, respuesta])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(buscar), patch_orph:
            resultado = await agent.navigate(_input())
        assert [t.nct_id for t in resultado.trials] == ["NCT_LOCAL", "NCT_EXT"]

    @pytest.mark.asyncio
    async def test_trazabilidad_de_los_ensayos(self):
        agent, _ = _agent_with_llm([_PLAN_OK, _eval_ok(["NCT04000001"])])
        patch_orph, _ = _patch_orphanet()
        with _patch_search(lambda **kw: [_trial()]), patch_orph:
            resultado = await agent.navigate(_input())
        trial = resultado.trials[0]
        assert "axonal sensorimotor polyneuropathy" in trial.matched_terms
        assert "hereditary transthyretin amyloidosis" in trial.matched_terms
        assert trial.related_hypotheses == ["Amiloidosis hereditaria por transtiretina"]
