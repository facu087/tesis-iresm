"""
Tests de la telemetría de costos (backend/telemetry/usage.py y pricing.py).

Control de costos, Sprint 4. Cubre:
  - el registro por análisis vive en un contexto (contextvars), no en un
    acumulador global (D2): dos análisis concurrentes no mezclan sus conteos,
    y el contexto se propaga a asyncio.to_thread();
  - el identificador de análisis es aleatorio, nunca derivado del caso (D3);
  - la escritura JSONL, una línea por análisis (D4);
  - que la telemetría nunca contiene datos clínicos (privacidad);
  - que un fallo al escribir el registro no rompe el análisis;
  - la estimación de costo con tarifas configurables, y su recálculo (D5).

Ningún test llama a un LLM ni a la red.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.telemetry import pricing, usage

CASO_CLINICO = (
    "Paciente masculino de 42 años con neuropatía axonal sensitivomotora "
    "progresiva, panel CMT negativo, anticuerpos anti-Hu anti-Yo anti-Ri negativos."
)


@pytest.fixture(autouse=True)
def _sin_registro_activo():
    """Ningún test hereda un registro abierto de otro."""
    assert usage.current() is None
    yield
    assert usage.current() is None


# ── D2: contexto por análisis, no acumulador global ────────────────────────────

class TestRegistroPorAnalisis:
    def test_sin_registro_abierto_record_call_no_hace_nada(self):
        usage.record_call(task="x", model="m", ok=True, latency_seconds=0.1)
        assert usage.current() is None  # no crea un registro implícito

    def test_abrir_activa_el_registro_en_el_contexto(self):
        token = usage.open_registry()
        try:
            assert usage.current() is not None
        finally:
            usage.close_registry(token, output_path="/dev/null")

    def test_cerrar_desactiva_el_registro(self):
        token = usage.open_registry()
        usage.close_registry(token, output_path="/dev/null")
        assert usage.current() is None

    def test_las_llamadas_quedan_en_el_registro_activo(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="m", ok=True, latency_seconds=0.2)
        usage.record_call(task="agente03_hipotesis", model="m", ok=True, latency_seconds=0.3)
        registro = usage.current()
        assert registro is not None
        assert len(registro.calls) == 2
        usage.close_registry(token, output_path=tmp_path / "costos.jsonl")

    @pytest.mark.asyncio
    async def test_dos_analisis_concurrentes_no_mezclan_conteos(self, tmp_path):
        """
        Dos 'análisis' corren concurrentemente, cada uno en su propia Task de
        asyncio (cada Task copia el contexto al crearse). Ninguno debe ver las
        llamadas del otro.
        """
        resultados = {}

        async def analizar(nombre: str, cantidad: int) -> None:
            token = usage.open_registry()
            for i in range(cantidad):
                usage.record_call(task=f"{nombre}_{i}", model="m", ok=True, latency_seconds=0.01)
                await asyncio.sleep(0)  # cede el control, como haría una llamada real
            resumen = usage.close_registry(token, output_path=tmp_path / f"{nombre}.jsonl")
            resultados[nombre] = resumen

        await asyncio.gather(
            asyncio.create_task(analizar("caso_a", 3)),
            asyncio.create_task(analizar("caso_b", 5)),
        )

        assert resultados["caso_a"]["totals"]["calls"] == 3
        assert resultados["caso_b"]["totals"]["calls"] == 5
        assert resultados["caso_a"]["analysis_id"] != resultados["caso_b"]["analysis_id"]

    @pytest.mark.asyncio
    async def test_el_contexto_se_propaga_a_asyncio_to_thread(self, tmp_path):
        """D2: asyncio.to_thread() debe ver el mismo registro que abrió el análisis."""
        token = usage.open_registry()

        def registrar_desde_un_thread() -> None:
            usage.record_call(task="desde_thread", model="m", ok=True, latency_seconds=0.01)

        await asyncio.to_thread(registrar_desde_un_thread)
        registro = usage.current()
        assert registro is not None
        assert len(registro.calls) == 1
        assert registro.calls[0].task == "desde_thread"
        usage.close_registry(token, output_path=tmp_path / "costos.jsonl")


# ── D3: identificador aleatorio ─────────────────────────────────────────────────

class TestIdentificadorAleatorio:
    def test_dos_analisis_del_mismo_texto_tienen_ids_distintos(self, tmp_path):
        """Analiza 'dos veces' el mismo texto clínico: los ids no deben coincidir."""
        ids = []
        for _ in range(2):
            token = usage.open_registry()
            usage.record_call(task="agente01_hipotesis", model="m", ok=True, latency_seconds=0.1)
            resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
            ids.append(resumen["analysis_id"])
        assert ids[0] != ids[1]

    def test_el_id_no_es_un_hash_del_texto(self, tmp_path):
        """El id no debe poder reconstruirse a partir del texto del caso."""
        import hashlib
        token = usage.open_registry()
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        hash_del_caso = hashlib.sha256(CASO_CLINICO.encode()).hexdigest()
        assert resumen["analysis_id"] != hash_del_caso
        assert CASO_CLINICO not in resumen["analysis_id"]


# ── D4: JSONL, una línea por análisis ────────────────────────────────────────────

class TestEscrituraJsonl:
    def test_tres_analisis_dejan_tres_lineas_parseables(self, tmp_path):
        destino = tmp_path / "costos.jsonl"
        for _ in range(3):
            token = usage.open_registry()
            usage.record_call(task="agente01_hipotesis", model="openai/gpt-oss-120b",
                               ok=True, latency_seconds=0.1,
                               prompt_tokens=100, completion_tokens=50)
            usage.close_registry(token, output_path=destino)

        lineas = destino.read_text(encoding="utf-8").strip().split("\n")
        assert len(lineas) == 3
        registros = [json.loads(linea) for linea in lineas]
        assert all("analysis_id" in r and "totals" in r for r in registros)

    def test_el_resumen_incluye_total_desglose_y_costo(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="openai/gpt-oss-120b",
                           agent_id="01", agent_name="Analista de Literatura",
                           ok=True, latency_seconds=0.1,
                           prompt_tokens=1000, completion_tokens=200)
        usage.record_call(task="arbitro_agrupacion", model="openai/gpt-oss-20b",
                           agent_id="04", agent_name="Árbitro Verificador",
                           ok=True, latency_seconds=0.05,
                           prompt_tokens=300, completion_tokens=20)
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")

        assert resumen["totals"]["calls"] == 2
        assert resumen["totals"]["prompt_tokens"] == 1300
        assert resumen["totals"]["completion_tokens"] == 220
        assert resumen["totals"]["cost_usd"] == 0.0  # Groq: tarifa cero
        agentes = {a["agent_id"] for a in resumen["by_agent"]}
        assert agentes == {"01", "04"}


# ── Llamadas fallidas y sin datos de consumo ─────────────────────────────────────

class TestLlamadasFallidasYSinDatos:
    def test_llamada_fallida_queda_contabilizada(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="m", ok=False, latency_seconds=8.0)
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        assert resumen["totals"]["calls"] == 1
        assert resumen["totals"]["failed_calls"] == 1

    def test_llamada_sin_usage_se_registra_marcada_no_omitida(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="m", ok=True, latency_seconds=1.0,
                           prompt_tokens=None, completion_tokens=None)
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        assert resumen["totals"]["calls"] == 1
        assert resumen["totals"]["calls_without_usage"] == 1

    def test_llamada_truncada_por_techo_queda_marcada(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="arbitro_agrupacion", model="m", ok=True, latency_seconds=1.0,
                           prompt_tokens=10, completion_tokens=5, truncated=True)
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        assert resumen["totals"]["truncated_calls"] == 1


# ── Privacidad: nunca datos clínicos ─────────────────────────────────────────────

class TestPrivacidad:
    def test_el_registro_no_contiene_texto_clinico(self, tmp_path):
        """
        `record_call()` no acepta ni prompt ni respuesta del modelo como
        parámetro: estructuralmente no puede filtrar texto clínico. Este test
        lo prueba con un texto del caso real dando vueltas en el entorno.
        """
        token = usage.open_registry()
        usage.record_call(
            task="agente01_hipotesis", model="openai/gpt-oss-120b",
            agent_id="01", agent_name="Analista de Literatura",
            ok=True, latency_seconds=1.2, prompt_tokens=500, completion_tokens=300,
        )
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")

        volcado = json.dumps(resumen, ensure_ascii=False)
        assert CASO_CLINICO not in volcado
        assert "neuropatía" not in volcado.lower()
        assert "anti-hu" not in volcado.lower()

        linea = (tmp_path / "costos.jsonl").read_text(encoding="utf-8")
        assert CASO_CLINICO not in linea
        assert "neuropatía" not in linea.lower()


# ── Resiliencia: un fallo de escritura no rompe el análisis ──────────────────────

class TestResilenciaDeEscritura:
    def test_ruta_no_escribible_no_rompe_y_avisa(self, tmp_path, capsys):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="m", ok=True, latency_seconds=0.1)
        # tmp_path es un directorio: abrirlo como archivo levanta OSError.
        resumen = usage.close_registry(token, output_path=tmp_path)
        assert resumen is not None  # el análisis sigue, solo falla la escritura
        salida = capsys.readouterr()
        assert "telemetría" in salida.err.lower()


# ── Resumen legible por stderr ────────────────────────────────────────────────

class TestResumenPorConsola:
    def test_emite_un_resumen_legible_al_cerrar(self, tmp_path, capsys):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="openai/gpt-oss-120b",
                           ok=True, latency_seconds=0.1, prompt_tokens=100, completion_tokens=50)
        usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        salida = capsys.readouterr()
        assert "1" in salida.err  # 1 llamada
        assert "150" in salida.err or ("100" in salida.err and "50" in salida.err)


# ── Tarifas configurables (D5) ───────────────────────────────────────────────────

class TestTarifas:
    def test_groq_tiene_tarifa_cero(self):
        precio = pricing.price_for("openai/gpt-oss-120b")
        assert precio is not None
        assert precio.input_per_million == 0.0
        assert precio.output_per_million == 0.0

    def test_modelo_desconocido_sin_tarifa(self):
        precio = pricing.price_for("modelo-que-no-existe")
        assert precio is None

    def test_estimate_cost_con_tarifas_conocidas(self):
        tabla = {"modelo-x": pricing.ModelPrice(input_per_million=1.0, output_per_million=2.0)}
        costo, tiene_tarifa = pricing.estimate_cost(1_000_000, 500_000, "modelo-x", tabla)
        assert tiene_tarifa is True
        assert costo == pytest.approx(1.0 + 1.0)  # 1M*$1 + 0.5M*$2

    def test_modelo_sin_tarifa_da_costo_cero_y_bandera(self):
        costo, tiene_tarifa = pricing.estimate_cost(1000, 500, "modelo-sin-tarifa", {})
        assert costo == 0.0
        assert tiene_tarifa is False

    def test_resumen_senala_modelo_sin_tarifa(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="x", model="modelo-sin-tarifa", ok=True, latency_seconds=0.1,
                           prompt_tokens=100, completion_tokens=50)
        resumen = usage.close_registry(
            token, output_path=tmp_path / "costos.jsonl", price_table={},
        )
        assert resumen["totals"]["unpriced_models"] == ["modelo-sin-tarifa"]
        assert resumen["by_agent"][0]["priced"] is False


# ── Recalcular con otra tabla de tarifas (task 3.4) ──────────────────────────────

class TestRecalcular:
    def test_recalcula_el_costo_de_un_registro_guardado(self, tmp_path):
        token = usage.open_registry()
        usage.record_call(task="agente01_hipotesis", model="openai/gpt-oss-120b",
                           ok=True, latency_seconds=0.1,
                           prompt_tokens=1_000_000, completion_tokens=500_000)
        resumen = usage.close_registry(token, output_path=tmp_path / "costos.jsonl")
        assert resumen["totals"]["cost_usd"] == 0.0  # Groq real

        tabla_opus = {
            "openai/gpt-oss-120b": pricing.ModelPrice(
                input_per_million=15.0, output_per_million=75.0,
            )
        }
        recalculado = usage.recalculate(resumen, tabla_opus)
        assert recalculado["totals"]["cost_usd"] == pytest.approx(15.0 + 37.5)
        # El original no se muta.
        assert resumen["totals"]["cost_usd"] == 0.0
