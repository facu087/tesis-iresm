"""Tests para el cliente Orphanet."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.external.orphanet import OrphanetClient, RareDisease


class TestRareDisease:
    def test_url_se_genera_automaticamente(self):
        d = RareDisease(orpha_code="85163", name="TTR Amyloidosis", definition="Desc")
        assert "85163" in d.url

    def test_summary_con_genes(self):
        d = RareDisease(
            orpha_code="85163",
            name="hATTR amyloidosis",
            definition="Progressive neuropathy caused by TTR mutations.",
            genes=["TTR"],
        )
        s = d.summary()
        assert "TTR" in s
        assert "ORPHA:85163" in s

    def test_summary_sin_genes(self):
        d = RareDisease(orpha_code="1", name="Enfermedad X", definition="Desc.")
        assert "no especificados" in d.summary()


@pytest.mark.asyncio
async def test_search_devuelve_enfermedades():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=[
        {"OrphaCode": "85163", "Preferred term": "TTR amyloidosis", "Definition": "Desc", "Synonyms": []},
    ])

    async def mock_get(url, params=None):
        return mock_resp

    async with OrphanetClient() as client:
        client._client = AsyncMock()
        client._client.get = mock_get
        results = await client.search("TTR amyloidosis")

    assert len(results) == 1
    assert results[0].orpha_code == "85163"


@pytest.mark.asyncio
async def test_search_error_devuelve_lista_vacia():
    async def mock_get(url, params=None):
        raise Exception("Connection error")

    async with OrphanetClient() as client:
        client._client = AsyncMock()
        client._client.get = mock_get
        results = await client.search("query")

    assert results == []
