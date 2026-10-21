"""
Tests para el cliente PubMed E-utilities.

Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino 42 años.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.external.pubmed import PubMedClient, PubMedArticle, _parse_abstracts_xml


# ---------------------------------------------------------------------------
# Tests unitarios (sin llamadas reales a la API)
# ---------------------------------------------------------------------------

class TestPubMedArticle:
    def test_url_se_genera_automaticamente(self):
        article = PubMedArticle(
            pmid="12345678",
            title="Test title",
            abstract="Test abstract",
            journal="N Engl J Med",
            year="2021",
        )
        assert article.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    def test_citation_con_pocos_autores(self):
        article = PubMedArticle(
            pmid="12345678",
            title="TTR amyloidosis: a review",
            abstract="",
            journal="N Engl J Med",
            year="2019",
            authors=["García J", "López M"],
        )
        citation = article.citation()
        assert "García J" in citation
        assert "TTR amyloidosis" in citation
        assert "PMID: 12345678" in citation

    def test_citation_con_muchos_autores_usa_et_al(self):
        article = PubMedArticle(
            pmid="12345678",
            title="Título",
            abstract="",
            journal="Lancet",
            year="2020",
            authors=["A A", "B B", "C C", "D D", "E E"],
        )
        assert "et al." in article.citation()


class TestParseAbstractsXml:
    def test_parsea_abstract_simple(self):
        xml = """<?xml version="1.0"?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>29470523</PMID>
              <Article>
                <Abstract>
                  <AbstractText>Hereditary TTR amyloidosis causes progressive neuropathy.</AbstractText>
                </Abstract>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""

        result = _parse_abstracts_xml(xml)
        assert "29470523" in result
        assert "TTR amyloidosis" in result["29470523"]

    def test_parsea_abstract_con_secciones(self):
        xml = """<?xml version="1.0"?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>99999999</PMID>
              <Article>
                <Abstract>
                  <AbstractText Label="BACKGROUND">Background text.</AbstractText>
                  <AbstractText Label="RESULTS">Results text.</AbstractText>
                </Abstract>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""

        result = _parse_abstracts_xml(xml)
        assert "BACKGROUND:" in result["99999999"]
        assert "RESULTS:" in result["99999999"]

    def test_xml_malformado_no_explota(self):
        result = _parse_abstracts_xml("<xml malformado<<<")
        assert result == {}

    def test_sin_pmid_no_incluye_articulo(self):
        xml = """<?xml version="1.0"?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <Article>
                <Abstract><AbstractText>Texto sin PMID.</AbstractText></Abstract>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""
        result = _parse_abstracts_xml(xml)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests de integración (con mocks de httpx)
# ---------------------------------------------------------------------------

MOCK_ESEARCH_RESPONSE = {
    "esearchresult": {
        "idlist": ["29470523", "28754644"]
    }
}

MOCK_ESUMMARY_RESPONSE = {
    "result": {
        "uids": ["29470523", "28754644"],
        "29470523": {
            "title": "Hereditary transthyretin amyloidosis: a review",
            "fulljournalname": "New England Journal of Medicine",
            "pubdate": "2019 Jan",
            "authors": [{"name": "Adams D"}, {"name": "Gonzalez-Duarte A"}],
        },
        "28754644": {
            "title": "Autoimmune autonomic ganglionopathy",
            "fulljournalname": "Neurology",
            "pubdate": "2017 Mar",
            "authors": [{"name": "Sandroni P"}],
        },
    }
}

MOCK_EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation><PMID>29470523</PMID>
      <Article><Abstract><AbstractText>TTR amyloidosis causes neuropathy.</AbstractText></Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation><PMID>28754644</PMID>
      <Article><Abstract><AbstractText>AAG is a rare autonomic disorder.</AbstractText></Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


@pytest.mark.asyncio
async def test_search_devuelve_articulos():
    """search() devuelve PubMedArticle con todos los campos poblados."""
    mock_response_json = MagicMock()
    mock_response_json.raise_for_status = MagicMock()

    mock_response_xml = MagicMock()
    mock_response_xml.raise_for_status = MagicMock()
    mock_response_xml.text = MOCK_EFETCH_XML

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if "esearch" in url:
            mock_response_json.json = MagicMock(return_value=MOCK_ESEARCH_RESPONSE)
            return mock_response_json
        elif "esummary" in url:
            mock_response_json.json = MagicMock(return_value=MOCK_ESUMMARY_RESPONSE)
            return mock_response_json
        else:  # efetch
            return mock_response_xml

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.get = mock_get
        mock_http.aclose = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        async with PubMedClient() as client:
            client._client = mock_http
            articles = await client.search("TTR amyloidosis neuropathy", max_results=2)

    assert len(articles) == 2
    assert articles[0].pmid == "29470523"
    assert "amyloidosis" in articles[0].title
    assert articles[0].journal == "New England Journal of Medicine"
    assert articles[0].year == "2019"
    assert "Adams D" in articles[0].authors
    assert "TTR amyloidosis" in articles[0].abstract


@pytest.mark.asyncio
async def test_search_sin_resultados_devuelve_lista_vacia():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"esearchresult": {"idlist": []}})

    async def mock_get(url, params=None):
        return mock_response

    with patch("httpx.AsyncClient"):
        client = PubMedClient()
        client._client = AsyncMock()
        client._client.get = mock_get

        result = await client._esearch("query sin resultados", 5)
        assert result == []


@pytest.mark.asyncio
async def test_verify_pmid_existente():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=MOCK_ESUMMARY_RESPONSE)

    async def mock_get(url, params=None):
        return mock_response

    with patch("httpx.AsyncClient"):
        client = PubMedClient()
        client._client = AsyncMock()
        client._client.get = mock_get

        exists = await client.verify_pmid("29470523")
        assert exists is True


@pytest.mark.asyncio
async def test_verify_pmid_inexistente():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"result": {"uids": []}})

    async def mock_get(url, params=None):
        return mock_response

    with patch("httpx.AsyncClient"):
        client = PubMedClient()
        client._client = AsyncMock()
        client._client.get = mock_get

        exists = await client.verify_pmid("00000000")
        assert exists is False


# ---------------------------------------------------------------------------
# Tipos de publicación (clasificación de evidencia EBM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_metadata_incluye_tipos_de_publicacion_en_una_sola_consulta():
    """esummary ya trae `pubtype`: se exponen como `pubtypes` sin requests extra."""
    respuesta = {
        "result": {
            "uids": ["30000001", "30000002"],
            "30000001": {
                "title": "Metformin and vitamin B12 deficiency: a meta-analysis",
                "fulljournalname": "Diabetes Care",
                "pubdate": "2021 Feb",
                "authors": [],
                "pubtype": ["Journal Article", "Meta-Analysis"],
            },
            # Sin campo pubtype: debe devolver lista vacía, no romper.
            "30000002": {
                "title": "Axonal neuropathy in a 42-year-old man",
                "fulljournalname": "Neurology",
                "pubdate": "2020",
                "authors": [],
            },
        }
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=respuesta)

    urls: list[str] = []

    async def mock_get(url, params=None):
        urls.append(url)
        return mock_response

    client = PubMedClient()
    client._client = AsyncMock()
    client._client.get = mock_get

    result = await client.fetch_metadata(["30000001", "30000002"])

    assert len(urls) == 1
    assert result["30000001"]["pubtypes"] == ["Journal Article", "Meta-Analysis"]
    assert result["30000002"]["pubtypes"] == []


# ---------------------------------------------------------------------------
# Lectura de PUBMED_API_KEY (tarjeta #79)
# ---------------------------------------------------------------------------

from backend.external.pubmed import (  # noqa: E402  (agrupado con el resto del fix)
    _ENV_API_KEY_VAR,
    _leer_api_key,
    _verificar_respuesta,
)


class TestLecturaDeLaApiKey:
    """
    Una clave mal formada apagaba la verificación bibliográfica entera, en
    silencio: viajaba como `api_key`, PubMed devolvía 400 y todas las fuentes
    quedaban `no_verificable`. El caso real fue el comentario del `.env`
    escrito en la misma línea que la variable.
    """

    def test_sin_variable(self, monkeypatch):
        monkeypatch.delenv(_ENV_API_KEY_VAR, raising=False)
        assert _leer_api_key() is None

    @pytest.mark.parametrize("valor", ["", "   ", "\t"])
    def test_vacia_o_en_blanco(self, valor, monkeypatch):
        monkeypatch.setenv(_ENV_API_KEY_VAR, valor)
        assert _leer_api_key() is None

    def test_el_comentario_del_env_no_viaja_como_clave(self, monkeypatch, capsys):
        """El caso que se llevó puesta una corrida de 450 s."""
        monkeypatch.setenv(
            _ENV_API_KEY_VAR,
            "            # Opcional: aumenta rate limit de 3 a 10 req/seg",
        )
        assert _leer_api_key() is None
        assert _ENV_API_KEY_VAR in capsys.readouterr().err

    @pytest.mark.parametrize("valor", [
        "clave con espacios",
        "/ruta/a/un/archivo",
        "abc",                      # demasiado corta para ser una clave
        "clave-con-guiones-1234567890",
    ])
    def test_formatos_que_no_son_clave(self, valor, monkeypatch):
        monkeypatch.setenv(_ENV_API_KEY_VAR, valor)
        assert _leer_api_key() is None

    @pytest.mark.parametrize("valor", [
        "abc123def456abc123def456abc123def456",   # 36 alfanuméricos, formato NCBI
        "A1B2C3D4E5F6",
    ])
    def test_clave_valida_se_conserva(self, valor, monkeypatch):
        monkeypatch.setenv(_ENV_API_KEY_VAR, valor)
        assert _leer_api_key() == valor

    def test_se_recortan_los_espacios(self, monkeypatch):
        monkeypatch.setenv(_ENV_API_KEY_VAR, "  abc123def456abc123  ")
        assert _leer_api_key() == "abc123def456abc123"

    def test_una_clave_invalida_no_llega_a_los_parametros(self, monkeypatch):
        """
        Degradar a 3 req/s es aceptable; apagar la verificación no. El cliente
        tiene que quedar SIN clave, no con una rota.
        """
        monkeypatch.setenv(_ENV_API_KEY_VAR, "# comentario")
        cliente = PubMedClient()
        assert cliente._api_key is None
        assert "api_key" not in cliente._base_params()

    def test_una_clave_valida_si_llega_a_los_parametros(self, monkeypatch):
        monkeypatch.setenv(_ENV_API_KEY_VAR, "abc123def456abc123def456abc123def456")
        assert PubMedClient()._base_params()["api_key"] == "abc123def456abc123def456abc123def456"


class TestAvisoAnte400:
    """Un 400 de E-utilities casi siempre es un parámetro mal formado."""

    def _respuesta(self, status: int):
        import httpx
        return httpx.Response(
            status_code=status,
            request=httpx.Request("GET", "https://eutils.ncbi.nlm.nih.gov/x"),
        )

    def test_400_nombra_la_causa_probable(self, capsys):
        import httpx
        with pytest.raises(httpx.HTTPStatusError):
            _verificar_respuesta(self._respuesta(400))
        assert _ENV_API_KEY_VAR in capsys.readouterr().err

    def test_otros_errores_no_culpan_a_la_clave(self, capsys):
        import httpx
        with pytest.raises(httpx.HTTPStatusError):
            _verificar_respuesta(self._respuesta(503))
        assert _ENV_API_KEY_VAR not in capsys.readouterr().err

    def test_200_no_levanta_ni_avisa(self, capsys):
        _verificar_respuesta(self._respuesta(200))
        assert capsys.readouterr().err == ""
