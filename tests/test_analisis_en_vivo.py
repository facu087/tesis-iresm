"""
Tests de `POST /api/analyze/stream`: el análisis con el avance real del
pipeline (backend/pipeline/progreso.py + backend/api/router.py).

El pipeline se mockea igual que en `tests/test_proteccion_analisis.py`: ningún
test llama a un LLM ni a la red.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from backend.api.schemas import StructuredReport
from backend.models.case import ClinicalCase
from backend.pipeline import progreso
from backend.pipeline.debate import run_debate
from tests import test_debate as debate_tests
from tests.test_proteccion_analisis import _pipeline_patches

RUTA = "/api/analyze/stream"


def _eventos(resp) -> list[dict]:
    """Cada línea no vacía del cuerpo es un evento JSON."""
    return [json.loads(linea) for linea in resp.text.splitlines() if linea.strip()]


def _con_pipeline_mockeado(client, ruta: str = RUTA, **request_kwargs):
    patches = _pipeline_patches()
    with (
        patches["normalize"],
        patches["pico_build"],
        patches["extract_biomarkers"],
        patches["run_round_1"],
        patches["run_debate"],
        patches["navigate"],
        patches["verify_sources"],
        patches["arbitrate"],
    ):
        return client.post(ruta, **request_kwargs)


# ── Protección: la misma que POST /api/analyze ─────────────────────────────────

class TestProteccion:
    def test_sin_sesion_devuelve_401_sin_ejecutar_el_pipeline(self, client):
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client.post(RUTA, data={"text": "caso clínico"})
        assert resp.status_code == 401
        mock_round_1.assert_not_called()

    def test_medico_pendiente_recibe_403(self, client, cuenta_medico_pendiente):
        client.post(
            "/api/login",
            json={"email": cuenta_medico_pendiente.email, "password": "ContraseñaSegura123"},
        )
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client.post(RUTA, data={"text": "caso clínico"})
        assert resp.status_code == 403
        mock_round_1.assert_not_called()

    def test_admin_recibe_403(self, client_admin):
        resp = client_admin.post(RUTA, data={"text": "caso clínico"})
        assert resp.status_code == 403

    def test_origen_ajeno_rechaza_sin_ejecutar_el_pipeline(self, client_medico_verificado):
        with patch("backend.api.router.orchestrator.run_round_1") as mock_round_1:
            resp = client_medico_verificado.post(
                RUTA,
                data={"text": "caso clínico"},
                headers={"Origin": "https://sitio-ajeno.example"},
            )
        assert resp.status_code == 403
        mock_round_1.assert_not_called()


# ── Entrada inválida: se rechaza con su código HTTP, antes de transmitir ──────

class TestEntradaInvalida:
    def test_sin_archivo_ni_texto_devuelve_422(self, client_medico_verificado):
        resp = client_medico_verificado.post(RUTA, data={})
        assert resp.status_code == 422

    def test_archivo_vacio_devuelve_422(self, client_medico_verificado):
        resp = client_medico_verificado.post(
            RUTA, files={"file": ("caso.pdf", b"", "application/pdf")}
        )
        assert resp.status_code == 422

    def test_archivo_que_supera_el_limite_devuelve_413(
        self, client_medico_verificado, monkeypatch
    ):
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
        with patch("backend.api.router.extract") as mock_extract:
            resp = client_medico_verificado.post(
                RUTA,
                files={"file": ("caso.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")},
            )
        assert resp.status_code == 413
        mock_extract.assert_not_called()


# ── Transmisión del avance ─────────────────────────────────────────────────────

class TestTransmision:
    def test_responde_200_como_ndjson(self, client_medico_verificado):
        resp = _con_pipeline_mockeado(client_medico_verificado, data={"text": "caso clínico"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")

    def test_emite_los_ocho_pasos_en_orden_y_termina_con_el_reporte(
        self, client_medico_verificado
    ):
        resp = _con_pipeline_mockeado(client_medico_verificado, data={"text": "caso clínico"})
        eventos = _eventos(resp)

        pasos = [e["paso"] for e in eventos if e["evento"] == "paso"]
        assert pasos == ["01", "02", "03", "04", "05", "06", "07", "08"]

        assert eventos[-1]["evento"] == "reporte"
        assert [e["evento"] for e in eventos].count("reporte") == 1
        # El reporte transmitido es un StructuredReport válido.
        reporte = StructuredReport.model_validate(eventos[-1]["reporte"])
        assert reporte.hypotheses

    def test_el_reporte_es_el_mismo_que_devuelve_el_endpoint_sin_transmision(
        self, client_medico_verificado
    ):
        transmitido = _eventos(
            _con_pipeline_mockeado(client_medico_verificado, data={"text": "caso clínico"})
        )[-1]["reporte"]
        directo = _con_pipeline_mockeado(
            client_medico_verificado, ruta="/api/analyze", data={"text": "caso clínico"}
        ).json()

        # Lo único que cambia entre dos corridas es la hora y la duración.
        for reporte in (transmitido, directo):
            reporte["metadata"].pop("generated_at")
            reporte["metadata"].pop("processing_time_seconds")
        assert transmitido == directo

    def test_un_archivo_recorre_los_mismos_pasos(self, client_medico_verificado):
        with patch("backend.api.router.extract", return_value="texto del pdf"):
            resp = _con_pipeline_mockeado(
                client_medico_verificado,
                files={"file": ("caso.pdf", b"%PDF-1.4 contenido", "application/pdf")},
            )
        eventos = _eventos(resp)
        assert [e["paso"] for e in eventos if e["evento"] == "paso"][0] == "01"
        assert eventos[-1]["evento"] == "reporte"

    def test_no_deja_un_registro_de_telemetria_abierto(self, client_medico_verificado):
        from backend.telemetry import usage as usage_telemetry

        _con_pipeline_mockeado(client_medico_verificado, data={"text": "caso clínico"})
        assert usage_telemetry.current() is None


# ── Fallas a mitad del análisis: viajan como evento ───────────────────────────

class TestFallas:
    def test_una_falla_del_pipeline_es_un_evento_de_error_sin_el_texto_de_la_excepcion(
        self, client_medico_verificado
    ):
        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patch(
                "backend.api.router.orchestrator.run_round_1",
                new_callable=AsyncMock,
                side_effect=RuntimeError("paciente Juan Pérez, dato clínico"),
            ),
        ):
            resp = client_medico_verificado.post(RUTA, data={"text": "caso clínico"})

        assert resp.status_code == 200
        eventos = _eventos(resp)
        assert eventos[-1]["evento"] == "error"
        assert eventos[-1]["status"] == 500
        assert "Juan Pérez" not in resp.text
        assert "reporte" not in [e["evento"] for e in eventos]
        # El avance llegó hasta el paso que falló.
        assert [e["paso"] for e in eventos if e["evento"] == "paso"] == ["01", "02", "03", "04"]

    def test_un_formato_no_soportado_es_un_evento_de_error_con_su_codigo(
        self, client_medico_verificado
    ):
        with patch(
            "backend.api.router.extract", side_effect=ValueError("Formato no soportado.")
        ):
            resp = client_medico_verificado.post(
                RUTA, files={"file": ("caso.docx", b"contenido", "application/octet-stream")}
            )
        eventos = _eventos(resp)
        assert eventos[-1] == {
            "evento": "error",
            "status": 415,
            "detail": "Formato no soportado.",
        }


# ── El módulo de progreso ──────────────────────────────────────────────────────

class TestProgreso:
    def test_sin_destino_abierto_emitir_no_hace_nada(self):
        progreso.paso("01")
        progreso.ronda(2)

    def test_entrega_los_eventos_al_destino_y_deja_de_hacerlo_al_cerrar(self):
        recibidos: list[dict] = []
        token = progreso.abrir(recibidos.append)
        progreso.paso("03")
        progreso.ronda(2)
        progreso.cerrar(token)
        progreso.paso("04")

        assert recibidos == [
            {"evento": "paso", "paso": "03"},
            {"evento": "ronda", "ronda": 2},
        ]

    def test_un_destino_que_falla_no_rompe_el_analisis(self, capsys):
        def destino_roto(_evento: dict) -> None:
            raise RuntimeError("dato clínico en el mensaje")

        token = progreso.abrir(destino_roto)
        try:
            progreso.paso("01")
        finally:
            progreso.cerrar(token)

        aviso = capsys.readouterr().err
        assert "RuntimeError" in aviso
        assert "dato clínico" not in aviso


class TestRondasDelDebate:
    def test_run_debate_avisa_cada_ronda_en_orden(self):
        base = debate_tests.TestRunDebate()
        case = ClinicalCase(raw_text="texto", pico=debate_tests._make_pico())
        recibidos: list[dict] = []

        async def correr():
            token = progreso.abrir(recibidos.append)
            try:
                return await run_debate(case, base._make_round1_report())
            finally:
                progreso.cerrar(token)

        with patch("backend.pipeline.debate.LiteratureAnalystAgent") as M01, \
             patch("backend.pipeline.debate.GenomicsSpecialistAgent") as M02, \
             patch("backend.pipeline.debate.ClinicalConsultantAgent") as M03:
            base._mock_agents(M01, M02, M03)
            asyncio.run(correr())

        assert recibidos == [
            {"evento": "ronda", "ronda": 2},
            {"evento": "ronda", "ronda": 3},
            {"evento": "ronda", "ronda": 4},
        ]


# ── Corte de la conexión ───────────────────────────────────────────────────────

class TestCorteDeConexion:
    def test_si_el_cliente_corta_el_pipeline_se_cancela_y_cierra_la_telemetria(self):
        """Sin nadie que lea, el análisis no sigue corriendo ni gastando cuota."""
        from backend.api.router import analyze_stream
        from backend.telemetry import usage as usage_telemetry

        estado = {"cancelado": False, "registro_abierto_al_final": None}

        async def ronda_1_que_no_termina(_case):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                estado["cancelado"] = True
                raise

        async def escenario() -> list[dict]:
            resp = await analyze_stream(file=None, text="caso clínico", _medico=None)
            cuerpo = resp.body_iterator
            recibidos = []
            async for linea in cuerpo:
                recibidos.append(json.loads(linea))
                if recibidos[-1] == {"evento": "paso", "paso": "04"}:
                    break
            # El servidor cierra el generador cuando el cliente se va.
            await cuerpo.aclose()
            # Un turno del loop para que la tarea cancelada termine su `finally`.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            estado["registro_abierto_al_final"] = usage_telemetry.current()
            return recibidos

        patches = _pipeline_patches()
        with (
            patches["normalize"],
            patches["pico_build"],
            patches["extract_biomarkers"],
            patch(
                "backend.api.router.orchestrator.run_round_1",
                side_effect=ronda_1_que_no_termina,
            ),
        ):
            recibidos = asyncio.run(escenario())

        assert [e["paso"] for e in recibidos] == ["01", "02", "03", "04"]
        assert estado["cancelado"] is True
        assert estado["registro_abierto_al_final"] is None
