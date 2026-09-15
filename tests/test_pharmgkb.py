"""
Tests del cliente PharmGKB/ClinPGx (backend/external/pharmgkb.py).

Tests unitarios: no llaman a la API real. Los payloads de ejemplo copian la
forma verificada de la respuesta de https://api.clinpgx.org/v1/data.

El foco está en lo que la versión anterior no hacía: distinguir "sin
resultados" (404) de "la API falló" (400, 429, 5xx, red). Antes todo caía en
`except (httpx.HTTPError, Exception)` y devolvía [], así que un host
inexistente y un gen sin anotaciones eran indistinguibles.
"""

import httpx
import pytest

from backend.external.pharmgkb import (
    DrugGeneInteraction,
    GeneAnnotation,
    PharmGKBClient,
    _parse_annotation,
    _sort_key,
)
from backend.external.rate_limiter import ExternalApiError


# ── Payloads con la forma real de la API ───────────────────────────────────────

def _anotacion(nivel: str, farmaco: str = "tramadol", enfermedad: str = "Pain") -> dict:
    """Un registro de /clinicalAnnotation tal como lo devuelve ClinPGx."""
    return {
        "accessionId": "PA166135161",
        "levelOfEvidence": {"term": nivel, "resource": "Level of Evidence"},
        "relatedChemicals": [{"name": farmaco, "id": "PA451906"}],
        "relatedDiseases": [{"name": enfermedad}],
        "location": {
            "displayName": "CYP2D6*1, CYP2D6*4",
            "genes": [{"symbol": "CYP2D6", "id": "PA128"}],
            "type": "haplotype",
        },
    }


class _RespuestaFalsa:
    """Imita lo justo de httpx.Response que usa el cliente."""

    def __init__(self, status_code: int, payload: dict | None = None, texto: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = texto

    def json(self):
        if self._payload is None:
            raise ValueError("no es JSON")
        return self._payload


def _cliente_que_responde(*respuestas):
    """Devuelve un fake de httpx.AsyncClient que responde en orden."""
    secuencia = list(respuestas)

    class _Fake:
        def __init__(self):
            self.llamadas = []

        async def get(self, url, params=None):
            self.llamadas.append((url, params))
            return secuencia.pop(0) if len(secuencia) > 1 else secuencia[0]

    return _Fake()


@pytest.fixture
def cliente():
    """PharmGKBClient listo para inyectarle un transporte falso."""
    return PharmGKBClient()


# ── Taxonomía de errores: el corazón de este fix ───────────────────────────────

class TestTaxonomiaDeErrores:
    @pytest.mark.asyncio
    async def test_404_es_sin_resultados_no_error(self, cliente):
        """La API devuelve 404 + 'No results matching criteria.' cuando no hay datos."""
        cliente._client = _cliente_que_responde(
            _RespuestaFalsa(404, {"status": "fail", "data": {
                "errors": [{"message": "No results matching criteria."}]}})
        )
        assert await cliente.get_gene_annotations("NOEXISTE") == []

    @pytest.mark.asyncio
    async def test_400_es_error_y_levanta(self, cliente):
        """400 'No such property' es un bug nuestro en la query: no puede pasar callado."""
        cliente._client = _cliente_que_responde(
            _RespuestaFalsa(400, {"status": "fail", "data": {
                "errors": [{"message": "No such property: 'pageSize'"}]}})
        )
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_gene_annotations("CYP2D6")
        assert "No such property" in str(exc.value)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_429_levanta(self, cliente):
        cliente._client = _cliente_que_responde(
            _RespuestaFalsa(429, None, texto="429 Too Many Requests")
        )
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_gene_annotations("CYP2D6")
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_500_levanta(self, cliente):
        cliente._client = _cliente_que_responde(_RespuestaFalsa(500, None, texto="oops"))
        with pytest.raises(ExternalApiError):
            await cliente.get_gene_annotations("CYP2D6")

    @pytest.mark.asyncio
    async def test_fallo_de_red_levanta(self, cliente):
        """El host inexistente (api.pharmgkb.org) entraba por acá y se tragaba."""
        class _FakeQueFalla:
            async def get(self, url, params=None):
                raise httpx.ConnectError("getaddrinfo failed")

        cliente._client = _FakeQueFalla()
        with pytest.raises(ExternalApiError, match="No se pudo consultar"):
            await cliente.get_gene_annotations("CYP2D6")

    @pytest.mark.asyncio
    async def test_json_invalido_levanta(self, cliente):
        cliente._client = _cliente_que_responde(_RespuestaFalsa(200, None, texto="<html>"))
        with pytest.raises(ExternalApiError, match="no es JSON"):
            await cliente.get_gene_annotations("CYP2D6")


# ── Parseo de campos ───────────────────────────────────────────────────────────

class TestParseo:
    def test_lee_los_campos_reales(self):
        ann = _parse_annotation(_anotacion("1A"))
        assert ann.gene_symbol == "CYP2D6"
        assert ann.drug_name == "tramadol"
        assert ann.phenotype == "Pain"
        assert ann.evidence_level == "1A"
        assert ann.variant == "CYP2D6*1, CYP2D6*4"
        assert "PA166135161" in ann.url

    def test_tolera_campos_ausentes(self):
        """Un registro incompleto no debe romper el parseo."""
        ann = _parse_annotation({})
        assert ann.gene_symbol == ""
        assert ann.evidence_level == ""

    def test_relatedchemicals_vacio_no_rompe(self):
        """La versión anterior hacía [0] sobre una lista vacía -> IndexError."""
        ann = _parse_annotation({"relatedChemicals": [], "location": {}})
        assert ann.drug_name == ""

    def test_simbolo_explicito_gana(self):
        ann = _parse_annotation(_anotacion("1A"), gene_symbol="TTR")
        assert ann.gene_symbol == "TTR"


class TestOrden:
    def test_orden_por_fuerza_de_evidencia(self):
        niveles = ["3", "1A", "4", "2A", "1B", "2B"]
        anotaciones = [_parse_annotation(_anotacion(n)) for n in niveles]
        anotaciones.sort(key=_sort_key)
        assert [a.evidence_level for a in anotaciones] == ["1A", "1B", "2A", "2B", "3", "4"]

    def test_nivel_desconocido_va_al_final(self):
        anotaciones = [
            _parse_annotation(_anotacion("")),
            _parse_annotation(_anotacion("1A")),
        ]
        anotaciones.sort(key=_sort_key)
        assert anotaciones[0].evidence_level == "1A"


class TestMaxResults:
    @pytest.mark.asyncio
    async def test_recorta_del_lado_del_cliente(self, cliente):
        """La API no pagina: pageSize da HTTP 400, así que el recorte es acá."""
        payload = {"data": [_anotacion("1A") for _ in range(25)]}
        cliente._client = _cliente_que_responde(_RespuestaFalsa(200, payload))
        assert len(await cliente.get_gene_annotations("CYP2D6", max_results=4)) == 4

    @pytest.mark.asyncio
    async def test_no_manda_pagesize(self, cliente):
        """Mandar pageSize haría fallar la query con 400."""
        fake = _cliente_que_responde(_RespuestaFalsa(200, {"data": []}))
        cliente._client = fake
        await cliente.get_gene_annotations("CYP2D6")
        _, params = fake.llamadas[0]
        assert "pageSize" not in params
        assert params["location.genes.symbol"] == "CYP2D6"


# ── Fármacos ───────────────────────────────────────────────────────────────────

class TestFarmacos:
    @pytest.mark.asyncio
    async def test_farmaco_inexistente_devuelve_none(self, cliente):
        cliente._client = _cliente_que_responde(_RespuestaFalsa(404, {"data": {}}))
        assert await cliente.get_drug_interactions("NOEXISTE") is None

    @pytest.mark.asyncio
    async def test_farmaco_real_junta_genes(self, cliente):
        cliente._client = _cliente_que_responde(
            _RespuestaFalsa(200, {"data": [{"id": "PA451906", "name": "warfarin"}]}),
            _RespuestaFalsa(200, {"data": [_anotacion("1A", farmaco="warfarin")]}),
        )
        di = await cliente.get_drug_interactions("warfarin")
        assert di is not None
        assert di.pharmgkb_id == "PA451906"
        assert di.genes == ["CYP2D6"]
        assert "clinpgx.org" in di.url


# ── Varios genes ───────────────────────────────────────────────────────────────

class TestMultiGene:
    @pytest.mark.asyncio
    async def test_un_gen_que_falla_no_tumba_a_los_demas(self, cliente, capsys):
        """Acá sí interesa el resultado parcial: es la excepción deliberada."""
        class _FakeSelectivo:
            async def get(self, url, params=None):
                if params.get("location.genes.symbol") == "ROTO":
                    raise httpx.ConnectError("boom")
                return _RespuestaFalsa(200, {"data": [_anotacion("1A")]})

        cliente._client = _FakeSelectivo()
        resultado = await cliente.get_multi_gene_annotations(["CYP2D6", "ROTO"])

        assert len(resultado["CYP2D6"]) == 1
        assert resultado["ROTO"] == []
        assert "ROTO" in capsys.readouterr().err


# ── Dataclasses ────────────────────────────────────────────────────────────────

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
        for esperado in ("TTR", "patisiran", "1A", "Val30Met"):
            assert esperado in s


class TestDrugGeneInteraction:
    def test_url_se_genera(self):
        d = DrugGeneInteraction(drug_name="patisiran", pharmgkb_id="PA166153765")
        assert "PA166153765" in d.url
        assert "clinpgx.org" in d.url

    def test_summary_sin_anotaciones(self):
        d = DrugGeneInteraction(drug_name="patisiran", pharmgkb_id="abc")
        assert "sin anotaciones" in d.summary()

    def test_summary_con_anotaciones(self):
        d = DrugGeneInteraction(
            drug_name="patisiran",
            pharmgkb_id="abc",
            annotations=[GeneAnnotation("TTR", "patisiran", "Efficacy", "1A")],
        )
        assert "patisiran" in d.summary()
        assert "TTR" in d.summary()
