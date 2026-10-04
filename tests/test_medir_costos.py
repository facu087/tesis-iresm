"""
Tests de la lógica pura de la medición de costos (`backend/telemetry/medicion.py`)
y de las piezas auxiliares del script `scripts/medir_costos.py`.

Cubre lo que no necesita red ni LLM: comparar particiones, etiquetas y términos,
calcular holgura de techos y casos por día, resumir la telemetría, medir el
cambio entre las Rondas 3 y 4, y el cambio temporal de modelo.

Ningún test de este archivo llama a un LLM real ni a la red.
"""

from __future__ import annotations

import pytest

from backend.agents import model_tasks
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.report import AgentOutput
from backend.models.arbitration import ArbitrationStatus
from backend.telemetry import medicion
from backend.telemetry.usage import CallRecord


def _hip(texto: str, nivel: EvidenceLevel = EvidenceLevel.II,
         prioridad: Priority = Priority.HIGH) -> Hypothesis:
    return Hypothesis(
        text=texto, priority=prioridad, evidence_level=nivel,
        rationale="fundamento", sources=[],
    )


def _salida(agent_id: str, hipotesis: list[Hypothesis]) -> AgentOutput:
    return AgentOutput(agent_id=agent_id, agent_name=f"Agente {agent_id}", hypotheses=hipotesis)


def _llamada(task: str, *, entrada: int | None = 100, salida: int | None = 50,
             ok: bool = True, truncada: bool = False, agente: str | None = "01",
             modelo: str = model_tasks.GROQ_MAIN, latencia: float = 1.0) -> CallRecord:
    return CallRecord(
        task=task, model=modelo, ok=ok, latency_seconds=latencia,
        agent_id=agente, agent_name=f"Agente {agente}" if agente else None,
        prompt_tokens=entrada, completion_tokens=salida, truncated=truncada,
    )


# ── Holgura y casos por día ───────────────────────────────────────────────────

class TestHolgura:
    def test_holgura_es_techo_menos_maximo(self):
        assert medicion.headroom(4096, 1000) == {
            "ceiling": 4096, "max_observed": 1000, "slack": 3096, "slack_pct": 75.6,
        }

    def test_sin_observaciones_no_hay_holgura(self):
        assert medicion.headroom(4096, None) == {
            "ceiling": 4096, "max_observed": None, "slack": None, "slack_pct": None,
        }

    def test_maximo_igual_al_techo_es_holgura_cero(self):
        assert medicion.headroom(512, 512)["slack"] == 0

    def test_maximo_sobre_el_techo_da_holgura_negativa(self):
        assert medicion.headroom(512, 600)["slack"] == -88


class TestCasosPorDia:
    def test_division_entera(self):
        assert medicion.cases_per_day(65_000) == 3

    def test_cuota_configurable(self):
        assert medicion.cases_per_day(50_000, quota=100_000) == 2

    def test_menos_de_un_caso_da_cero(self):
        assert medicion.cases_per_day(250_000) == 0

    def test_sin_tokens_no_se_puede_estimar(self):
        assert medicion.cases_per_day(0) is None


# ── Particiones del Árbitro ───────────────────────────────────────────────────

class TestParticiones:
    def test_iguales_sin_importar_el_orden(self):
        assert medicion.partitions_equal([[0, 2], [1]], [[1], [2, 0]]) is True

    def test_distintas(self):
        assert medicion.partitions_equal([[0, 1], [2]], [[0], [1, 2]]) is False

    def test_vacias_son_iguales(self):
        assert medicion.partitions_equal([], []) is True


class TestClasificarAgrupacion:
    def test_aceptada_si_la_validacion_no_cambio_nada(self):
        assert medicion.classify_grouping(
            [[0, 2], [1]], [[0, 2], [1]], ArbitrationStatus.OK
        ) == "aceptada"

    def test_reparada_si_la_validacion_agrego_huerfanos(self):
        assert medicion.classify_grouping(
            [[0, 2]], [[0, 2], [1]], ArbitrationStatus.OK
        ) == "reparada"

    def test_reparada_si_habia_indices_repetidos(self):
        assert medicion.classify_grouping(
            [[0, 1], [1, 2]], [[0, 1], [2]], ArbitrationStatus.OK
        ) == "reparada"

    def test_fallback_si_el_estado_es_degradado(self):
        assert medicion.classify_grouping(
            None, [[0], [1]], ArbitrationStatus.DEGRADADO
        ) == "fallback"

    def test_fallback_si_no_hubo_propuesta(self):
        assert medicion.classify_grouping(None, [[0], [1]], ArbitrationStatus.OK) == "fallback"


# ── Etiquetas de compatibilidad (Agente 05) ───────────────────────────────────

class TestEtiquetas:
    def test_cuenta_coincidencias_por_nct(self):
        r = medicion.compare_labels(
            {"NCT1": "alta", "NCT2": "baja", "NCT3": "media"},
            {"NCT1": "alta", "NCT2": "media", "NCT3": "media"},
        )
        assert r["common"] == 3
        assert r["matching"] == 2
        assert r["differing"] == {"NCT2": {"a": "baja", "b": "media"}}
        assert r["agreement_pct"] == 66.7

    def test_ids_que_solo_evaluo_uno(self):
        r = medicion.compare_labels({"NCT1": "alta", "NCT9": "baja"}, {"NCT1": "alta"})
        assert r["only_a"] == ["NCT9"]
        assert r["only_b"] == []
        assert r["common"] == 1

    def test_sin_ids_en_comun_no_hay_porcentaje(self):
        r = medicion.compare_labels({"NCT1": "alta"}, {"NCT2": "alta"})
        assert r["common"] == 0
        assert r["agreement_pct"] is None

    def test_vacio_contra_vacio(self):
        r = medicion.compare_labels({}, {})
        assert r["common"] == 0 and r["matching"] == 0


class TestTerminos:
    def test_termino_principal_igual_ignora_mayusculas(self):
        r = medicion.compare_terms(
            {0: ["Hereditary Amyloidosis", "ATTR"]},
            {0: ["hereditary amyloidosis"]},
        )
        assert r["main_term_matches"] == 1
        assert r["exact_matches"] == 0
        assert r["candidates_a"] == 1 and r["candidates_b"] == 1

    def test_conjunto_exacto_ignora_el_orden(self):
        r = medicion.compare_terms({0: ["a", "b"]}, {0: ["a", "b"]})
        assert r["exact_matches"] == 1

    def test_candidata_planificada_solo_por_un_modelo(self):
        r = medicion.compare_terms({0: ["a"], 1: ["b"]}, {0: ["a"]})
        assert r["only_a"] == [1]
        assert r["only_b"] == []
        assert r["main_term_matches"] == 1


# ── Resumen de telemetría ─────────────────────────────────────────────────────

class TestResumenPorTarea:
    def test_maximo_techo_holgura_y_truncados(self):
        llamadas = [
            _llamada("agente01_hipotesis", salida=1200),
            _llamada("agente01_hipotesis", salida=3000),
            _llamada("arbitro_agrupacion", salida=512, truncada=True, agente="04"),
        ]
        filas = {f["task"]: f for f in medicion.summarize_tasks(llamadas, model_tasks.TASK_BUDGETS)}

        a = filas["agente01_hipotesis"]
        assert a["calls"] == 2
        assert a["max_completion_tokens"] == 3000
        assert a["ceiling"] == 4096
        assert a["slack"] == 1096
        assert a["truncated_calls"] == 0

        g = filas["arbitro_agrupacion"]
        assert g["truncated_calls"] == 1
        assert g["slack"] == 0

    def test_llamada_fallida_no_aporta_tokens_pero_se_cuenta(self):
        llamadas = [
            _llamada("pico_sintesis", entrada=None, salida=None, ok=False, agente=None),
            _llamada("pico_sintesis", salida=700, agente=None),
        ]
        fila = medicion.summarize_tasks(llamadas, model_tasks.TASK_BUDGETS)[0]
        assert fila["calls"] == 2
        assert fila["failed_calls"] == 1
        assert fila["max_completion_tokens"] == 700

    def test_tarea_sin_techo_registrado_no_rompe(self):
        fila = medicion.summarize_tasks([_llamada("tarea_inventada")], {})[0]
        assert fila["ceiling"] is None
        assert fila["slack"] is None

    def test_sin_llamadas_no_hay_filas(self):
        assert medicion.summarize_tasks([], model_tasks.TASK_BUDGETS) == []


class TestResumenPorAgente:
    def test_agrupa_por_agente_y_suma_tokens(self):
        llamadas = [
            _llamada("agente01_hipotesis", entrada=100, salida=50, agente="01"),
            _llamada("debate_critica", entrada=200, salida=80, agente="01"),
            _llamada("agente03_hipotesis", entrada=300, salida=90, agente="03"),
            _llamada("pico_sintesis", entrada=40, salida=10, agente=None),
        ]
        filas = {f["agent_id"]: f for f in medicion.summarize_agents(llamadas)}
        assert filas["01"]["prompt_tokens"] == 300
        assert filas["01"]["completion_tokens"] == 130
        assert filas["01"]["total_tokens"] == 430
        assert filas["03"]["calls"] == 1
        assert filas[None]["total_tokens"] == 50


class TestTotales:
    def test_total_por_caso_y_casos_por_dia(self):
        llamadas = [_llamada("a", entrada=40_000, salida=10_000),
                    _llamada("b", entrada=15_000, salida=5_000)]
        t = medicion.summarize_totals(llamadas, wall_clock_seconds=12.5)
        assert t["prompt_tokens"] == 55_000
        assert t["completion_tokens"] == 15_000
        assert t["total_tokens"] == 70_000
        assert t["cases_per_day"] == 2
        assert t["wall_clock_seconds"] == 12.5
        assert t["calls"] == 2

    def test_cuenta_llamadas_sin_consumo_informado(self):
        t = medicion.summarize_totals([_llamada("a", entrada=None, salida=None)], 1.0)
        assert t["calls_without_usage"] == 1
        assert t["cases_per_day"] is None


# ── Rondas 3 y 4 ──────────────────────────────────────────────────────────────

class TestRondas:
    def test_ronda_identica_no_cambia_nada(self):
        r3 = [_salida("01", [_hip("A"), _hip("B")])]
        r4 = [_salida("01", [_hip("B"), _hip("A")])]
        r = medicion.compare_rounds(r3, r4)
        assert r["by_agent"]["01"]["identical"] is True
        assert r["totals"]["changed_hypotheses"] == 0

    def test_detecta_cambio_de_nivel_y_prioridad(self):
        r3 = [_salida("01", [_hip("A", EvidenceLevel.II, Priority.HIGH)])]
        r4 = [_salida("01", [_hip("A", EvidenceLevel.III, Priority.LOW)])]
        a = medicion.compare_rounds(r3, r4)["by_agent"]["01"]
        assert a["level_changed"] == 1
        assert a["priority_changed"] == 1
        assert a["text_changed"] == 0
        assert a["identical"] is False

    def test_enunciado_distinto_cuenta_como_retirada_mas_agregada(self):
        r3 = [_salida("01", [_hip("A"), _hip("B")])]
        r4 = [_salida("01", [_hip("A"), _hip("C")])]
        a = medicion.compare_rounds(r3, r4)["by_agent"]["01"]
        assert a["removed"] == 1
        assert a["added"] == 1
        assert a["unchanged"] == 1
        assert a["text_changed"] == 1

    def test_agente_presente_en_una_sola_ronda(self):
        r3 = [_salida("01", [_hip("A")])]
        r4 = [_salida("01", [_hip("A")]), _salida("03", [_hip("Z")])]
        r = medicion.compare_rounds(r3, r4)
        assert r["only_in_round_4"] == ["03"]
        assert "03" not in r["by_agent"]

    def test_totales_suman_agentes(self):
        r3 = [_salida("01", [_hip("A")]), _salida("03", [_hip("X")])]
        r4 = [_salida("01", [_hip("A2")]), _salida("03", [_hip("X")])]
        t = medicion.compare_rounds(r3, r4)["totals"]
        assert t["hypotheses_round_3"] == 2
        assert t["hypotheses_round_4"] == 2
        assert t["changed_hypotheses"] == 1

    def test_sin_hipotesis_en_ninguna_ronda(self):
        assert medicion.compare_rounds([], [])["totals"]["changed_hypotheses"] == 0


# ── Cambio temporal de modelo ─────────────────────────────────────────────────

class TestCambioDeModelo:
    def test_cambia_el_modelo_conservando_el_techo_y_restaura(self):
        tarea = "arbitro_agrupacion"
        original = model_tasks.TASK_BUDGETS[tarea]
        with medicion.swapped_model(tarea, model_tasks.GROQ_MAIN):
            actual = model_tasks.get_budget(tarea)
            assert actual.model == model_tasks.GROQ_MAIN
            assert actual.max_tokens == original.max_tokens
        assert model_tasks.TASK_BUDGETS[tarea] == original

    def test_restaura_aunque_haya_una_excepcion(self):
        tarea = "agente05_planificacion_terminos"
        original = model_tasks.TASK_BUDGETS[tarea]
        with pytest.raises(RuntimeError):
            with medicion.swapped_model(tarea, model_tasks.GROQ_MAIN):
                raise RuntimeError("falla en la rama")
        assert model_tasks.TASK_BUDGETS[tarea] == original

    def test_tarea_desconocida_falla_sin_tocar_nada(self):
        antes = dict(model_tasks.TASK_BUDGETS)
        with pytest.raises(KeyError):
            with medicion.swapped_model("tarea_inventada", model_tasks.GROQ_MAIN):
                pass
        assert model_tasks.TASK_BUDGETS == antes

    def test_acepta_un_mapa_alternativo(self):
        mapa = {"t": model_tasks.TaskBudget(model_tasks.GROQ_FAST, 100)}
        with medicion.swapped_model("t", model_tasks.GROQ_MAIN, budgets=mapa):
            assert mapa["t"].model == model_tasks.GROQ_MAIN
        assert mapa["t"].model == model_tasks.GROQ_FAST


# ── Resumen legible ───────────────────────────────────────────────────────────

class TestResumenLegible:
    def test_modo_mock_se_marca_arriba_del_todo(self):
        texto = medicion.render_summary({"mock": True})
        assert texto.startswith("*")
        assert "MODO MOCK" in texto
        assert "NO son una medición" in texto

    def test_medicion_real_no_lleva_aviso_de_mock(self):
        assert "MODO MOCK" not in medicion.render_summary({"mock": False})

    def test_tolera_un_dict_parcial(self):
        texto = medicion.render_summary({
            "mock": False,
            "stages": {"base": {"status": "error", "seconds": 1.5, "error": "RuntimeError"}},
        })
        assert "RuntimeError" in texto

    def test_incluye_tablas_de_tokens_y_casos_por_dia(self):
        llamadas = [_llamada("agente01_hipotesis", entrada=1000, salida=500)]
        base = {
            "totals": medicion.summarize_totals(llamadas, 3.0),
            "tasks": medicion.summarize_tasks(llamadas, model_tasks.TASK_BUDGETS),
            "agents": medicion.summarize_agents(llamadas),
        }
        texto = medicion.render_summary({"mock": False, "base": base})
        assert "agente01_hipotesis" in texto
        assert "casos por cuota diaria de 200000 tokens: 133" in texto

    def test_ronda_no_disponible_se_explica(self):
        texto = medicion.render_summary({
            "debate_rounds_3_4": {"available": False, "reason": "el debate se omitió"},
        })
        assert "el debate se omitió" in texto

    def test_tabla_alinea_columnas(self):
        t = medicion.format_table(["a", "bb"], [["xxx", 1], ["y", None]])
        lineas = t.splitlines()
        assert lineas[0].startswith("a    bb")
        assert lineas[3].endswith("-")


# ── Guardas del script ────────────────────────────────────────────────────────

class TestGuardasDelScript:
    """Sin red ni LLM: el script tiene que negarse antes de hacer nada."""

    @staticmethod
    def _correr(env_extra: dict[str, str]):
        import os
        import subprocess
        import sys
        from pathlib import Path

        raiz = Path(__file__).parent.parent
        env = {**os.environ, **env_extra}
        return subprocess.run(
            [sys.executable, str(raiz / "scripts" / "medir_costos.py")],
            capture_output=True, text=True, env=env, cwd=raiz, timeout=120,
        )

    def test_sin_api_key_y_sin_mock_falla_claro(self):
        r = self._correr({"GROQ_API_KEY": "", "NEXUS_MOCK_LLM": ""})
        assert r.returncode == 2
        assert "GROQ_API_KEY" in r.stderr
        assert "--mock" in r.stderr

    def test_mock_en_el_entorno_sin_flag_no_se_confunde_con_una_corrida_real(self):
        r = self._correr({"GROQ_API_KEY": "x", "NEXUS_MOCK_LLM": "1"})
        assert r.returncode == 2
        assert "NEXUS_MOCK_LLM" in r.stderr
