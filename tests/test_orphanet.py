"""
Tests del cliente Orphanet (backend/external/orphanet.py).

Tests unitarios: no llaman a la API real. Los payloads copian la forma
verificada de https://api.orphacode.org/EN/ClinicalEntity.

El foco está en lo que la versión anterior no hacía: pegarle al endpoint que
existe, leer los nombres de campo correctos, y distinguir "sin resultados"
(404 con "Query not found") de "la API falló". Antes todo caía en
`except (httpx.HTTPError, Exception)` y devolvía [], así que el cliente
"funcionaba" sin haber traído nunca un resultado real.
"""

import httpx
import pytest

from backend.external.orphadata import OrphadataClient
from backend.external.orphanet import (
    OrphanetClient,
    RareDisease,
)
from backend.external.rate_limiter import ExternalApiError


# ── Payloads con la forma real de la API ───────────────────────────────────────

_APPROXIMATE_NAME = [
    {"ORPHAcode": 444116, "Preferred term": "Hereditary amyloidosis",
     "Date": "2026-07-02 10:13:59"},
    {"ORPHAcode": 271861, "Preferred term": "Hereditary ATTR amyloidosis",
     "Date": "2026-07-02 10:13:59"},
]

_ORPHACODE = {
    "ORPHAcode": 64746,
    "Preferred term": "Autosomal dominant Charcot-Marie-Tooth disease type 2",
    "Status": "Active",
    # Lista de STRINGS. La versión anterior leía "Synonyms" como lista de dicts.
    "Synonym": ["Autosomal dominant axonal Charcot-Marie-Tooth disease", "CMT2"],
    "Definition": "Una neuropatía hereditaria de herencia autosómica dominante.",
    "Date": "2026-07-02 10:14:00",
}


class _RespuestaFalsa:
    """Imita lo justo de httpx.Response que usa el cliente."""

    def __init__(self, status_code: int, payload=None, texto: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = texto

    def json(self):
        if self._payload is None:
            raise ValueError("no es JSON")
        return self._payload


def _transporte(*respuestas):
    """Fake de httpx.AsyncClient que responde en orden y registra las URLs."""
    secuencia = list(respuestas)

    class _Fake:
        def __init__(self):
            self.urls: list[str] = []

        async def get(self, url, params=None):
            self.urls.append(url)
            return secuencia.pop(0) if len(secuencia) > 1 else secuencia[0]

    return _Fake()


class _OrphadataFalso:
    """
    Doble del cliente de Orphadata: registra los códigos consultados.

    La forma real de la respuesta de Orphadata y su taxonomía de errores se
    prueban en `tests/test_orphadata.py`; acá solo interesa la delegación.
    """

    def __init__(self, simbolos: list[str]):
        self._simbolos = simbolos
        self.codigos: list[str] = []

    async def get_gene_symbols(self, orpha_code: str, *, solo_causales: bool = False):
        self.codigos.append(orpha_code)
        return list(self._simbolos)


@pytest.fixture
def cliente():
    return OrphanetClient()


# ── Endpoint correcto ──────────────────────────────────────────────────────────

class TestEndpoint:
    @pytest.mark.asyncio
    async def test_usa_approximatename_no_approximatelymatching(self, cliente):
        """/approximatelymatching no existe: devuelve 404 genérico."""
        fake = _transporte(_RespuestaFalsa(200, _APPROXIMATE_NAME))
        cliente._client = fake
        await cliente.search("amyloidosis")

        url = fake.urls[0]
        assert "/ApproximateName/" in url
        assert "approximatelymatching" not in url

    @pytest.mark.asyncio
    async def test_escapa_espacios_del_termino(self, cliente):
        """El término va en el path, y los nombres médicos llevan espacios."""
        fake = _transporte(_RespuestaFalsa(200, _APPROXIMATE_NAME))
        cliente._client = fake
        await cliente.search("hereditary transthyretin amyloidosis")
        assert " " not in fake.urls[0]
        assert "%20" in fake.urls[0]

    @pytest.mark.asyncio
    async def test_manda_el_header_apikey(self):
        """
        Hoy la API no lo exige (medido), pero mandarlo es gratis y cubre el día
        que empiece a exigirlo. Sin ORPHANET_API_KEY se manda 'test'.
        """
        async with OrphanetClient() as c:
            assert c._client.headers.get("apiKey")


# ── Taxonomía de errores ───────────────────────────────────────────────────────

class TestTaxonomiaDeErrores:
    @pytest.mark.asyncio
    async def test_404_es_sin_resultados(self, cliente):
        """La API usa 404 + "Query not found" cuando no hay coincidencias."""
        cliente._client = _transporte(_RespuestaFalsa(404, "Query not found"))
        assert await cliente.search("noexiste") == []

    @pytest.mark.asyncio
    async def test_404_en_get_by_code_devuelve_none(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(404, "Query not found"))
        assert await cliente.get_by_code("99999999") is None

    @pytest.mark.asyncio
    async def test_401_levanta_en_vez_de_pasar_por_sin_datos(self, cliente):
        """
        Medido: la API responde sin apiKey, pero tira 401 intermitentes al
        sondear rápido. Se reporta como error para que no se confunda con
        "esta enfermedad no está en Orphanet".
        """
        cliente._client = _transporte(_RespuestaFalsa(401, texto="Unauthorized"))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.search("amyloidosis")
        assert exc.value.status_code == 401
        assert "apiKey" in str(exc.value)

    @pytest.mark.asyncio
    async def test_500_levanta(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(500, texto="boom"))
        with pytest.raises(ExternalApiError):
            await cliente.search("amyloidosis")

    @pytest.mark.asyncio
    async def test_fallo_de_red_levanta(self, cliente):
        class _FakeQueFalla:
            async def get(self, url, params=None):
                raise httpx.ConnectError("sin red")

        cliente._client = _FakeQueFalla()
        with pytest.raises(ExternalApiError, match="No se pudo consultar"):
            await cliente.search("amyloidosis")


# ── Parseo de campos ───────────────────────────────────────────────────────────

class TestParseo:
    @pytest.mark.asyncio
    async def test_lee_orphacode_no_orphacode_camel(self, cliente):
        """El campo es ORPHAcode; con "OrphaCode" el código quedaba vacío."""
        cliente._client = _transporte(_RespuestaFalsa(200, _APPROXIMATE_NAME))
        resultados = await cliente.search("amyloidosis")
        assert [d.orpha_code for d in resultados] == ["444116", "271861"]
        assert resultados[1].name == "Hereditary ATTR amyloidosis"

    @pytest.mark.asyncio
    async def test_search_respeta_max_results(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, _APPROXIMATE_NAME))
        assert len(await cliente.search("amyloidosis", max_results=1)) == 1

    @pytest.mark.asyncio
    async def test_search_no_trae_definicion_ni_sinonimos(self, cliente):
        """ApproximateName solo devuelve ORPHAcode y Preferred term."""
        cliente._client = _transporte(_RespuestaFalsa(200, _APPROXIMATE_NAME))
        d = (await cliente.search("amyloidosis"))[0]
        assert d.definition == ""
        assert d.synonyms == []

    @pytest.mark.asyncio
    async def test_get_by_code_lee_synonym_como_lista_de_strings(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, _ORPHACODE))
        d = await cliente.get_by_code("64746")
        assert d.synonyms == [
            "Autosomal dominant axonal Charcot-Marie-Tooth disease", "CMT2"
        ]
        assert "autosómica dominante" in d.definition

    @pytest.mark.asyncio
    async def test_none_available_se_trata_como_vacio(self, cliente):
        """La API devuelve el string 'None available' cuando no hay definición."""
        payload = dict(_ORPHACODE, Definition="None available")
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        assert (await cliente.get_by_code("64746")).definition == ""


# ── Genes: los trae Orphadata, no esta API ─────────────────────────────────────

class TestGenes:
    """
    La ORPHAcodes API no expone genes (32 rutas, ninguna de genes), así que
    `get_genes()` delega en `OrphadataClient` (tarjeta #74). Acá se verifica la
    delegación: que no vaya nunca al host de nomenclatura y que devuelva lo que
    trae el cliente de Orphadata. La forma real de esa respuesta y su taxonomía
    de errores se ejercitan en `tests/test_orphadata.py`.
    """

    @pytest.mark.asyncio
    async def test_get_genes_delega_en_orphadata(self, cliente):
        nomenclatura = _transporte(_RespuestaFalsa(200, _ORPHACODE))
        cliente._client = nomenclatura
        cliente._orphadata = _OrphadataFalso(["TTR"])

        assert await cliente.get_genes("85447") == ["TTR"]
        assert cliente._orphadata.codigos == ["85447"]
        # El host de nomenclatura no se toca: no tiene este dato.
        assert nomenclatura.urls == []

    @pytest.mark.asyncio
    async def test_enrich_with_genes_completa_la_enfermedad(self, cliente):
        cliente._orphadata = _OrphadataFalso(["TTR"])
        disease = RareDisease(orpha_code="85447", name="ATTRV30M amyloidosis",
                              definition="")

        resultado = await cliente.enrich_with_genes(disease)

        assert resultado is disease
        assert disease.genes == ["TTR"]

    @pytest.mark.asyncio
    async def test_sin_asociacion_genica_deja_la_lista_vacia(self, cliente):
        """
        Orphadata devuelve 404 'Query not found' para los códigos sin asociación
        cargada (ORPHA:64746 es un grupo de enfermedades). El cliente lo traduce
        a [], que acá sí es el dato: no hay asociación para *ese* código.
        """
        cliente._orphadata = _OrphadataFalso([])
        disease = RareDisease(orpha_code="64746", name="CMT2", definition="")
        assert (await cliente.enrich_with_genes(disease)).genes == []

    @pytest.mark.asyncio
    async def test_fuera_del_async_with_abre_su_propio_cliente(self, cliente, monkeypatch):
        """Sin `async with`, `get_genes()` abre un OrphadataClient para la consulta."""
        abiertos: list[str] = []

        class _Efimero(_OrphadataFalso):
            def __init__(self):
                super().__init__(["TTR"])

            async def __aenter__(self):
                abiertos.append("abierto")
                return self

            async def __aexit__(self, *_):
                abiertos.append("cerrado")

        monkeypatch.setattr("backend.external.orphanet.OrphadataClient", _Efimero)

        assert cliente._orphadata is None
        assert await cliente.get_genes("85447") == ["TTR"]
        assert abiertos == ["abierto", "cerrado"]

    @pytest.mark.asyncio
    async def test_el_async_with_abre_y_cierra_el_cliente_de_genes(self):
        """Dentro del contexto hay un OrphadataClient propio, y se cierra al salir."""
        async with OrphanetClient() as abierto:
            assert isinstance(abierto._orphadata, OrphadataClient)
            assert abierto._orphadata._client is not None
        assert abierto._orphadata is None


# ── Dataclass ──────────────────────────────────────────────────────────────────

class TestRareDisease:
    def test_url_se_genera_automaticamente(self):
        d = RareDisease(orpha_code="271861", name="Hereditary ATTR amyloidosis",
                        definition="")
        assert "271861" in d.url

    def test_summary_con_genes(self):
        d = RareDisease(orpha_code="271861", name="ATTRv", definition="Una amiloidosis.",
                        genes=["TTR"])
        s = d.summary()
        assert "TTR" in s and "271861" in s

    def test_summary_sin_genes(self):
        d = RareDisease(orpha_code="271861", name="ATTRv", definition="Una amiloidosis.")
        assert "no especificados" in d.summary()

    def test_summary_sin_definicion(self):
        """El summary anterior hacía definition[:200] + '...' sobre un string vacío."""
        d = RareDisease(orpha_code="64746", name="CMT2", definition="")
        assert "sin definición disponible" in d.summary()
