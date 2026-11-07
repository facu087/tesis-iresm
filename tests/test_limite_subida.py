"""
Tests del límite de tamaño de los archivos subidos a POST /api/analyze.

`MAX_FILE_SIZE_MB` estaba documentada en `.env.example` y en CLAUDE.md, pero
ningún módulo la leía: no había límite. Herméticos: el pipeline está mockeado.
"""

from unittest.mock import patch

import pytest

from tests.test_api import _pipeline_patches

_MB = 1024 * 1024


def _subir(client, contenido: bytes):
    """Sube un PDF con el pipeline mockeado; devuelve la respuesta y el mock de extract."""
    patches = _pipeline_patches()
    with (
        patch("backend.api.router.extract", return_value="texto clínico") as extract,
        patches["normalize"],
        patches["pico_build"],
        patches["extract_biomarkers"],
        patches["run_round_1"],
        patches["run_debate"],
        patches["navigate"],
        patches["verify_sources"],
        patches["arbitrate"],
    ):
        respuesta = client.post(
            "/api/analyze",
            files={"file": ("informe.pdf", contenido, "application/pdf")},
        )
    return respuesta, extract


class TestLimiteDeSubida:
    def test_un_archivo_mayor_al_limite_se_rechaza_con_413(
        self, client_medico_verificado, monkeypatch
    ):
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
        respuesta, extract = _subir(client_medico_verificado, b"x" * (_MB + 1))
        assert respuesta.status_code == 413
        assert respuesta.json()["detail"] == "El archivo supera el límite de 1 MB."
        extract.assert_not_called()

    def test_un_archivo_justo_en_el_limite_se_acepta(
        self, client_medico_verificado, monkeypatch
    ):
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
        respuesta, extract = _subir(client_medico_verificado, b"x" * _MB)
        assert respuesta.status_code == 200
        assert extract.call_args.args[1] == b"x" * _MB

    def test_sin_variable_el_limite_es_50_mb(self, client_medico_verificado, monkeypatch):
        monkeypatch.delenv("MAX_FILE_SIZE_MB", raising=False)
        respuesta, _ = _subir(client_medico_verificado, b"x" * (50 * _MB + 1))
        assert respuesta.status_code == 413
        assert respuesta.json()["detail"] == "El archivo supera el límite de 50 MB."

    @pytest.mark.parametrize("valor", ["abc", "0", "-3", ""])
    def test_un_valor_invalido_avisa_y_usa_50_mb(
        self, client_medico_verificado, monkeypatch, capsys, valor
    ):
        monkeypatch.setenv("MAX_FILE_SIZE_MB", valor)
        respuesta, _ = _subir(client_medico_verificado, b"x" * (2 * _MB))
        assert respuesta.status_code == 200
        if valor:
            assert "MAX_FILE_SIZE_MB" in capsys.readouterr().err

    def test_el_texto_pegado_no_pasa_por_el_limite_de_archivo(
        self, client_medico_verificado, monkeypatch
    ):
        """El campo de texto sigue igual: se trunca a 500 KB, no se rechaza."""
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
        patches = _pipeline_patches()
        with (
            patches["normalize"], patches["pico_build"], patches["extract_biomarkers"],
            patches["run_round_1"], patches["run_debate"], patches["navigate"],
            patches["verify_sources"], patches["arbitrate"],
        ):
            respuesta = client_medico_verificado.post(
                "/api/analyze", data={"text": "Paciente masculino de 42 años."})
        assert respuesta.status_code == 200
