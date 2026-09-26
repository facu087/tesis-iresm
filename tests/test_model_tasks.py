"""
Tests del mapa tarea → (modelo, techo de tokens) (backend/agents/model_tasks.py).

Control de costos, Sprint 4 — D6: revisar qué modelo y qué techo usa cada
llamada no debe obligar a recorrer los agentes. Ningún test llama a un LLM.
"""

import pytest

from backend.agents import model_tasks


class TestMapaDeTareas:
    def test_todas_las_tareas_conocidas_tienen_presupuesto(self):
        tareas = [
            "agente01_hipotesis", "agente02_hipotesis", "agente03_hipotesis",
            "debate_critica", "debate_revision", "debate_recitacion",
            "arbitro_agrupacion", "arbitro_veredictos",
            "agente05_planificacion_terminos", "agente05_evaluacion_compatibilidad",
            "pico_sintesis", "biomarcadores_extraccion",
        ]
        for tarea in tareas:
            presupuesto = model_tasks.get_budget(tarea)
            assert presupuesto.model in (model_tasks.GROQ_MAIN, model_tasks.GROQ_FAST)
            assert presupuesto.max_tokens > 0

    def test_tarea_desconocida_levanta_key_error(self):
        with pytest.raises(KeyError):
            model_tasks.get_budget("tarea_que_no_existe")

    def test_pico_y_biomarcadores_conservan_su_techo_original(self):
        """No se cambia lo que ya funcionaba sin evidencia de que haga falta."""
        assert model_tasks.get_budget("pico_sintesis").max_tokens == 2048
        assert model_tasks.get_budget("biomarcadores_extraccion").max_tokens == 1024

    def test_arbitro_agrupacion_tiene_techo_acotado(self):
        """Devuelve solo índices: no necesita el techo de un razonamiento completo."""
        presupuesto = model_tasks.get_budget("arbitro_agrupacion")
        assert presupuesto.max_tokens < 2048


class TestTareasDeRazonamiento:
    """
    El razonamiento clínico no se degrada (presupuesto-por-tarea): ninguna
    tarea que produzca hipótesis, críticas, revisiones, veredictos o la
    síntesis del caso usa el modelo rápido.
    """

    def test_ninguna_tarea_de_razonamiento_usa_el_modelo_rapido(self):
        for tarea in model_tasks.REASONING_TASKS:
            assert model_tasks.get_budget(tarea).model == model_tasks.GROQ_MAIN

    def test_el_inventario_de_razonamiento_cubre_las_tareas_esperadas(self):
        esperadas = {
            "agente01_hipotesis", "agente02_hipotesis", "agente03_hipotesis",
            "debate_critica", "debate_revision", "debate_recitacion",
            "arbitro_veredictos", "pico_sintesis",
        }
        assert esperadas <= model_tasks.REASONING_TASKS
