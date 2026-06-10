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
