"""Tests para el cliente PharmGKB."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.external.pharmgkb import PharmGKBClient, GeneAnnotation, DrugGeneInteraction


class TestGeneAnnotation:
    def test_to_context_str(self):
        ann = GeneAnnotation(
            gene_symbol="TTR",
            drug_name="patisiran",
            phenotype="Efficacy",
            evidence_level="1A",
            variant="Val30Met",
        )
        s = ann.to_context_str()
        assert "TTR" in s
        assert "patisiran" in s
        assert "1A" in s
        assert "Val30Met" in s


class TestDrugGeneInteraction:
    def test_url_se_genera(self):
        d = DrugGeneInteraction(drug_name="patisiran", pharmgkb_id="PA166153765")
        assert "PA166153765" in d.url

    def test_summary_sin_anotaciones(self):
        d = DrugGeneInteraction(drug_name="patisiran", pharmgkb_id="abc")
        assert "sin anotaciones" in d.summary()

    def test_summary_con_anotaciones(self):
        d = DrugGeneInteraction(
            drug_name="patisiran",
            pharmgkb_id="abc",
            annotations=[
                GeneAnnotation("TTR", "patisiran", "Efficacy", "1A"),
            ],
        )
        assert "patisiran" in d.summary()
        assert "TTR" in d.summary()


@pytest.mark.asyncio
async def test_get_gene_annotations_sin_id_devuelve_vacio():
    async def mock_get(url, params=None):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json = MagicMock(return_value={"data": []})
        return mock

    async with PharmGKBClient() as client:
        client._client = AsyncMock()
        client._client.get = mock_get
        result = await client.get_gene_annotations("GENE_INEXISTENTE")

    assert result == []


@pytest.mark.asyncio
async def test_get_multi_gene_annotations():
    async def mock_get(url, params=None):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json = MagicMock(return_value={"data": []})
        return mock

    async with PharmGKBClient() as client:
        client._client = AsyncMock()
        client._client.get = mock_get
        result = await client.get_multi_gene_annotations(["TTR", "CYP2D6"])

    assert "TTR" in result
    assert "CYP2D6" in result
    assert isinstance(result["TTR"], list)
