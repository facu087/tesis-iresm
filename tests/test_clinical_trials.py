"""
Tests del cliente ClinicalTrials.gov (backend/external/clinical_trials.py).
Todos los tests mockean httpx — no realizan llamadas reales a la API.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.external.clinical_trials import (
    _parse_trial,
    search,
    search_by_biomarkers,
)
from backend.models.trial import ClinicalTrial


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_study(
    nct_id: str = "NCT04123456",
    title: str = "Ensayo de prueba para neuropatía axonal",
    status: str = "RECRUITING",
    conditions: list[str] | None = None,
    phase: str = "PHASE3",
    countries: list[str] | None = None,
) -> dict:
    """Construye un dict de study con la estructura real de la API v2."""
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": title,
            },
            "statusModule": {
                "overallStatus": status,
                "startDateStruct": {"date": "2023-06"},
                "primaryCompletionDateStruct": {"date": "2025-12"},
            },
            "descriptionModule": {
                "briefSummary": "Estudio sobre tratamiento de neuropatía axonal progresiva.",
            },
            "conditionsModule": {
                "conditions": conditions or ["Axonal Neuropathy", "CMT Disease"],
            },
            "designModule": {
                "phases": [phase],
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Universidad de Buenos Aires"},
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusión: edad 18-70 años, diagnóstico confirmado.",
                "minimumAge": "18 Years",
                "maximumAge": "70 Years",
                "sex": "ALL",
            },
            "contactsLocationsModule": {
                "locations": [
                    {"country": c, "city": "Ciudad", "facility": "Hospital"}
                    for c in (countries or ["Argentina", "United States"])
                ],
            },
        }
    }


def _make_api_response(studies: list[dict], total: int = None) -> dict:
    return {"studies": studies, "totalCount": total or len(studies)}


# ── Tests: _parse_trial ────────────────────────────────────────────────────────

class TestParseTrial:
    def test_parsea_estudio_completo(self):
        study = _make_study()
        trial = _parse_trial(study)
        assert trial is not None
        assert trial.nct_id == "NCT04123456"
        assert trial.title == "Ensayo de prueba para neuropatía axonal"
        assert trial.status == "RECRUITING"
        assert trial.phase == "PHASE3"
        assert trial.sponsor == "Universidad de Buenos Aires"
        assert trial.min_age == "18 Years"
        assert trial.sex == "ALL"
        assert "Argentina" in trial.locations
        assert "United States" in trial.locations

    def test_parsea_url_correcta(self):
        trial = _parse_trial(_make_study(nct_id="NCT99999999"))
        assert trial.url == "https://clinicaltrials.gov/study/NCT99999999"

    def test_devuelve_none_sin_nct_id(self):
        study = _make_study()
        study["protocolSection"]["identificationModule"]["nctId"] = ""
        assert _parse_trial(study) is None

    def test_devuelve_none_sin_titulo(self):
        study = _make_study()
        study["protocolSection"]["identificationModule"]["briefTitle"] = ""
        assert _parse_trial(study) is None

    def test_parsea_estudio_sin_localizaciones(self):
        study = _make_study()
        study["protocolSection"]["contactsLocationsModule"] = {}
        trial = _parse_trial(study)
        assert trial is not None
        assert trial.locations == []

    def test_parsea_estudio_sin_fase(self):
        study = _make_study()
        study["protocolSection"]["designModule"] = {}
        trial = _parse_trial(study)
        assert trial is not None
        assert trial.phase is None

    def test_no_duplica_paises(self):
        study = _make_study(countries=["Argentina", "Argentina", "Argentina"])
        trial = _parse_trial(study)
        assert trial.locations.count("Argentina") == 1

    def test_summary_line_con_fase(self):
        trial = _parse_trial(_make_study())
        line = trial.summary_line()
        assert "NCT04123456" in line
        assert "PHASE3" in line

    def test_summary_line_sin_fase(self):
        study = _make_study()
        study["protocolSection"]["designModule"] = {}
        trial = _parse_trial(study)
        assert "None" not in trial.summary_line()


# ── Tests: search ─────────────────────────────────────────────────────────────

class TestSearch:
    def _mock_get(self, studies: list[dict]):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_api_response(studies)
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        return mock_client

    def test_search_devuelve_lista_de_trials(self):
        studies = [_make_study("NCT001"), _make_study("NCT002")]
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            MockClient.return_value = self._mock_get(studies)
            results = search("axonal neuropathy")
        assert len(results) == 2
        assert all(isinstance(t, ClinicalTrial) for t in results)

    def test_search_filtra_recruiting_por_defecto(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            mock_client = self._mock_get([_make_study()])
            MockClient.return_value = mock_client
            search("neuropathy")
        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params.get("filter.overallStatus") == "RECRUITING"

    def test_search_sin_filtro_recruiting(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            mock_client = self._mock_get([_make_study()])
            MockClient.return_value = mock_client
            search("neuropathy", recruiting_only=False)
        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert "filter.overallStatus" not in params

    def test_search_incluye_keywords(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            mock_client = self._mock_get([])
            MockClient.return_value = mock_client
            search("neuropathy", keywords="TTR autonomic")
        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params.get("query.term") == "TTR autonomic"

    def test_search_lista_vacia_si_sin_resultados(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            MockClient.return_value = self._mock_get([])
            results = search("condición inexistente xyz")
        assert results == []

    def test_search_omite_estudios_invalidos(self):
        valid = _make_study("NCT001")
        invalid = _make_study("")  # sin NCT ID
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            MockClient.return_value = self._mock_get([valid, invalid])
            results = search("neuropathy")
        assert len(results) == 1
        assert results[0].nct_id == "NCT001"

    def test_search_lanza_error_en_http_500(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            response = MagicMock()
            response.status_code = 500
            response.text = "Internal Server Error"
            mock_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=response
            )
            MockClient.return_value = mock_client
            with pytest.raises(RuntimeError, match="500"):
                search("neuropathy")

    def test_search_lanza_error_en_timeout(self):
        with patch("backend.external.clinical_trials.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            MockClient.return_value = mock_client
            with pytest.raises(RuntimeError, match="conexión"):
                search("neuropathy")


# ── Tests: search_by_biomarkers ───────────────────────────────────────────────

class TestSearchByBiomarkers:
    def test_combina_biomarkers_como_keywords(self):
        with patch("backend.external.clinical_trials.search") as mock_search:
            mock_search.return_value = []
            search_by_biomarkers(["TTR", "ATTR", "anti-Hu"])
        # La primera llamada es la que lleva los biomarcadores como keywords;
        # la segunda (si la hay) es el reintento sin ellos.
        _, kwargs = mock_search.call_args_list[0]
        assert "TTR" in kwargs.get("keywords", "")

    def test_reintenta_sin_keywords_si_la_busqueda_queda_vacia(self):
        """Los biomarcadores negativos del caso vacían la búsqueda (la API usa AND)."""
        with patch("backend.external.clinical_trials.search") as mock_search:
            mock_search.return_value = []
            search_by_biomarkers(["anti-Hu", "anti-Yo"], condition="axonal neuropathy")

        assert mock_search.call_count == 2
        _, retry_kwargs = mock_search.call_args_list[1]
        assert retry_kwargs["condition"] == "axonal neuropathy"
        assert not retry_kwargs.get("keywords")

    def test_no_reintenta_si_ya_hay_resultados(self):
        with patch("backend.external.clinical_trials.search") as mock_search:
            mock_search.return_value = [MagicMock()]
            search_by_biomarkers(["TTR"], condition="amyloidosis")

        assert mock_search.call_count == 1

    def test_usa_condicion_si_se_provee(self):
        with patch("backend.external.clinical_trials.search") as mock_search:
            mock_search.return_value = []
            search_by_biomarkers(["TTR"], condition="neuropatía hereditaria")
        _, kwargs = mock_search.call_args
        assert kwargs["condition"] == "neuropatía hereditaria"

    def test_usa_primeros_biomarkers_como_condicion_si_no_hay_condition(self):
        with patch("backend.external.clinical_trials.search") as mock_search:
            mock_search.return_value = []
            search_by_biomarkers(["TTR", "ATTR"])
        _, kwargs = mock_search.call_args
        assert "TTR" in kwargs["condition"]
