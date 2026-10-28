"""
Tests del cliente Orphadata (backend/external/orphadata.py).

Tests unitarios **herméticos**: no tocan la red. Los payloads copian la forma
real de https://api.orphadata.com/rd-associated-genes, observada el 2026-10-06
(ORPHA:85447 → TTR; ORPHA:586 → 19 asociaciones, una causal y el resto
modificadoras; ORPHA:271861 y ORPHA:64746 → 404 "Query not found").

Verificar que no tocan la red:
    PYTHONPATH=scripts pytest tests/test_orphadata.py -p pytest_sin_red -q

El foco está en la distinción que cuesta caro equivocar: este host devuelve
**dos 404 distintos**. Uno dice "esta enfermedad no tiene asociación génica"
(resultado válido) y el otro dice "esa ruta no existe" (bug nuestro). Tratarlos
igual es lo que hizo que los clientes de Orphanet y PharmGKB parecieran andar
devolviendo vacío.
"""

import httpx
import pytest

from backend.external.orphadata import (
    DiseaseGenes,
    GeneAssociation,
    OrphadataClient,
    _parse_gene_association,
)
from backend.external.orphanet import OrphanetClient, RareDisease
from backend.external.rate_limiter import (
    ApiUnavailableError,
    ExternalApiError,
    orphadata_breaker,
)


# ── Payloads con la forma real de la API ───────────────────────────────────────

def _asociacion(
    simbolo: str = "TTR",
    nombre: str = "transthyretin",
    tipo: str = "Disease-causing germline mutation(s) in",
    estado: str = "Assessed",
    validacion: str | None = "18925456[PMID]",
) -> dict:
    """Un elemento de `DisorderGeneAssociation` tal como lo devuelve Orphadata."""
    return {
        "DisorderGeneAssociationStatus": estado,
        "DisorderGeneAssociationType": tipo,
        "SourceOfValidation": validacion,
        "Gene": {
            "ExternalReference": [
                {"Reference": simbolo, "Source": "ClinVar"},
                {"Reference": "ENSG00000118271", "Source": "Ensembl"},
                {"Reference": "12405", "Source": "HGNC"},
                {"Reference": "176300", "Source": "OMIM"},
            ],
            "GeneType": "gene with protein product",
            "Locus": [{"GeneLocus": "18q12.1", "LocusKey": 1}],
            "Symbol": simbolo,
            "Synonym": ["CTS", "HsT2651"],
            # Ojo: el nombre del gen viene en minúscula.
            "name": nombre,
        },
    }


def _respuesta_200(*asociaciones: dict, orphacode: int = 85447,
                   nombre: str = "ATTRV30M amyloidosis") -> dict:
    """Cuerpo completo de un 200 de /rd-associated-genes/orphacodes/{code}."""
    return {
        "data": {
            "__count": 1,
            "__licence": {
                "identifier": "CC-BY-4.0",
                "link": "https://creativecommons.org/licenses/by/4.0",
                "name": "Creative Commons Attribution 4.0 International",
            },
            "results": {
                "Date": "2026-06-23 07:57:31",
                "DisorderGeneAssociation": list(asociaciones),
                "DisorderGroup": "Subtype of disorder",
                "ORPHAcode": orphacode,
                "OrphanetURL": (
                    "http://www.orpha.net/consor/cgi-bin/OC_Exp.php"
                    f"?lng=en&Expert={orphacode}"
                ),
                "Preferred term": nombre,
                "Typology": "Clinical subtype",
            },
        },
        "datasetCategory": {"lang": "en", "name": "Rare diseases and associated genes"},
        "parameters": {"path": {"ORPHAcode": orphacode}, "query": {}},
        "uri": f"https://api.orphadata.com/rd-associated-genes/orphacodes/{orphacode}",
    }


# 404 de la ruta que existe: ese ORPHAcode no tiene asociación génica cargada.
_404_SIN_ASOCIACION = {
    "error": {"code": 404, "message": "message to define", "type": "Query not found"}
}

# 404 de ruteo (application/problem+json): la URL no es una ruta de la API.
_404_RUTA_INEXISTENTE = {
    "detail": "The requested URL was not found on the server. If you entered the "
              "URL manually please check your spelling and try again.",
    "status": 404,
    "title": "Not Found",
    "type": "about:blank",
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


def _transporte(*respuestas, excepcion: Exception | None = None):
    """Fake de httpx.AsyncClient que responde en orden y registra las URLs."""
    secuencia = list(respuestas)

    class _Fake:
        def __init__(self):
            self.urls: list[str] = []

        async def get(self, url, params=None):
            self.urls.append(url)
            if excepcion is not None:
                raise excepcion
            return secuencia.pop(0) if len(secuencia) > 1 else secuencia[0]

    return _Fake()


@pytest.fixture
def cliente():
    """OrphadataClient listo para inyectarle un transporte falso."""
    return OrphadataClient()


# ── Respuesta con genes ────────────────────────────────────────────────────────

class TestRespuestaConGenes:
    @pytest.mark.asyncio
    async def test_lee_los_campos_reales_de_la_asociacion(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, _respuesta_200(_asociacion())))

        genes = await cliente.get_disease_genes("85447")

        assert genes is not None
        assert genes.orpha_code == "85447"
        assert genes.name == "ATTRV30M amyloidosis"
        assert genes.typology == "Clinical subtype"
        assert genes.disorder_group == "Subtype of disorder"
        assert genes.date == "2026-06-23 07:57:31"
        assert "85447" in genes.url
        # La licencia viaja en la respuesta y hay que citarla: CC-BY-4.0.
        assert genes.licence == "CC-BY-4.0"

        assert len(genes.associations) == 1
        asociacion = genes.associations[0]
        assert asociacion.gene_symbol == "TTR"
        assert asociacion.gene_name == "transthyretin"
        assert asociacion.association_type == "Disease-causing germline mutation(s) in"
        assert asociacion.association_status == "Assessed"
        assert asociacion.source_of_validation == "18925456[PMID]"
        assert asociacion.pmid_validacion == "18925456"
        assert asociacion.locus == "18q12.1"
        assert asociacion.gene_type == "gene with protein product"
        assert asociacion.synonyms == ["CTS", "HsT2651"]
        assert asociacion.external_references["HGNC"] == "12405"
        assert asociacion.external_references["OMIM"] == "176300"
        assert asociacion.es_causal is True

    @pytest.mark.asyncio
    async def test_consulta_la_ruta_por_orphacode(self, cliente):
        transporte = _transporte(_RespuestaFalsa(200, _respuesta_200(_asociacion())))
        cliente._client = transporte

        await cliente.get_disease_genes("85447")

        assert transporte.urls == [
            "https://api.orphadata.com/rd-associated-genes/orphacodes/85447"
        ]

    @pytest.mark.asyncio
    async def test_get_gene_symbols_devuelve_los_simbolos(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, _respuesta_200(_asociacion())))
        assert await cliente.get_gene_symbols("85447") == ["TTR"]

    @pytest.mark.asyncio
    async def test_distingue_gen_causal_de_gen_modificador(self, cliente):
        """
        En la fibrosis quística (ORPHA:586) Orphanet asocia 19 genes: CFTR es la
        causa y los demás son modificadores. Devolver solo los símbolos haría
        pasar las dos cosas por lo mismo.
        """
        payload = _respuesta_200(
            _asociacion("SERPINA1", "alpha-1-antitrypsin",
                        tipo="Modifying germline mutation in"),
            _asociacion("CFTR", "CF transmembrane conductance regulator",
                        tipo="Disease-causing germline mutation(s) (loss of function) in"),
            _asociacion("TGFB1", "transforming growth factor beta 1",
                        tipo="Modifying germline mutation in"),
            orphacode=586, nombre="Cystic fibrosis",
        )
        cliente._client = _transporte(_RespuestaFalsa(200, payload))

        genes = await cliente.get_disease_genes("586")

        assert genes is not None
        assert genes.gene_symbols == ["SERPINA1", "CFTR", "TGFB1"]
        assert genes.causal_gene_symbols == ["CFTR"]
        assert [a.es_causal for a in genes.associations] == [False, True, False]

    @pytest.mark.asyncio
    async def test_solo_causales_recorta(self, cliente):
        payload = _respuesta_200(
            _asociacion("CFTR", tipo="Disease-causing germline mutation(s) in"),
            _asociacion("TGFB1", tipo="Modifying germline mutation in"),
            orphacode=586, nombre="Cystic fibrosis",
        )
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        assert await cliente.get_gene_symbols("586", solo_causales=True) == ["CFTR"]

    @pytest.mark.asyncio
    async def test_simbolo_repetido_no_se_duplica(self, cliente):
        """Un gen con dos asociaciones distintas aparece una sola vez."""
        payload = _respuesta_200(
            _asociacion("TTR", tipo="Disease-causing germline mutation(s) in"),
            _asociacion("TTR", tipo="Candidate gene tested in"),
        )
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        genes = await cliente.get_disease_genes("85447")
        assert genes is not None and genes.gene_symbols == ["TTR"]


# ── Los dos 404, que no significan lo mismo ────────────────────────────────────

class TestLosDos404:
    @pytest.mark.asyncio
    async def test_query_not_found_es_sin_asociacion_no_error(self, cliente):
        """
        ORPHA:271861 y ORPHA:64746 responden así: la ruta existe y ese código no
        tiene asociación génica cargada. Es un resultado, no un fallo.
        """
        cliente._client = _transporte(_RespuestaFalsa(404, _404_SIN_ASOCIACION))
        assert await cliente.get_disease_genes("271861") is None

    @pytest.mark.asyncio
    async def test_query_not_found_devuelve_lista_vacia_en_simbolos(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(404, _404_SIN_ASOCIACION))
        assert await cliente.get_gene_symbols("271861") == []

    @pytest.mark.asyncio
    async def test_404_de_ruteo_si_levanta(self, cliente):
        """
        El problem+json de Connexion significa "esa URL no es una ruta". Eso es
        un bug nuestro y no se puede confundir con "no hay datos".
        """
        cliente._client = _transporte(_RespuestaFalsa(404, _404_RUTA_INEXISTENTE))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert "ruta" in str(exc.value).lower()
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_404_sin_cuerpo_json_levanta(self, cliente):
        """Si no se puede leer el cuerpo, no se asume "sin resultados"."""
        cliente._client = _transporte(_RespuestaFalsa(404, None, texto="<html>502</html>"))
        with pytest.raises(ExternalApiError):
            await cliente.get_disease_genes("85447")


# ── Resto de la taxonomía de errores ───────────────────────────────────────────

class TestTaxonomiaDeErrores:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("codigo", [401, 403])
    async def test_credenciales_levantan(self, cliente, codigo):
        cliente._client = _transporte(_RespuestaFalsa(codigo, texto="denied"))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert exc.value.status_code == codigo
        assert "clave" in str(exc.value).lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("codigo", [429, 500, 502, 503])
    async def test_429_y_5xx_levantan(self, cliente, codigo):
        cliente._client = _transporte(_RespuestaFalsa(codigo, texto="boom"))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert exc.value.status_code == codigo

    @pytest.mark.asyncio
    async def test_fallo_de_red_levanta(self, cliente):
        """DNS caído, timeout o conexión rechazada: nunca se devuelve [] por eso."""
        cliente._client = _transporte(excepcion=httpx.ConnectError("sin DNS"))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert "no se pudo consultar" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_levanta(self, cliente):
        cliente._client = _transporte(excepcion=httpx.ReadTimeout("tardó"))
        with pytest.raises(ExternalApiError):
            await cliente.get_gene_symbols("85447")

    @pytest.mark.asyncio
    async def test_200_que_no_es_json_levanta(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, None, texto="<html>"))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert "no es json" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_200_sin_bloque_data_levanta(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(200, {"uri": "..."}))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert "data" in str(exc.value)

    @pytest.mark.asyncio
    async def test_results_que_no_es_objeto_levanta(self, cliente):
        """Si la forma de la respuesta cambia, se avisa en vez de devolver vacío."""
        payload = {"data": {"__count": 0, "results": []}}
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        with pytest.raises(ExternalApiError) as exc:
            await cliente.get_disease_genes("85447")
        assert "results" in str(exc.value)

    @pytest.mark.asyncio
    async def test_codigo_no_numerico_no_llega_a_la_red(self, cliente):
        """La ruta espera un entero: un código inválido es un bug del llamador."""
        transporte = _transporte(_RespuestaFalsa(200, _respuesta_200(_asociacion())))
        cliente._client = transporte
        for invalido in ("ORPHA:85447", "", "abc", "-1", "0"):
            with pytest.raises(ValueError):
                await cliente.get_disease_genes(invalido)
        assert transporte.urls == []


# ── Campos faltantes ──────────────────────────────────────────────────────────

class TestCamposFaltantes:
    def test_source_of_validation_nulo_no_rompe(self):
        """Medido: ORPHA:98896 trae `SourceOfValidation: null` para DMD."""
        asociacion = _parse_gene_association(_asociacion("DMD", validacion=None))
        assert asociacion.gene_symbol == "DMD"
        assert asociacion.source_of_validation == ""
        assert asociacion.pmid_validacion == ""

    def test_asociacion_sin_gene_queda_vacia(self):
        asociacion = _parse_gene_association({"DisorderGeneAssociationType": "x"})
        assert asociacion.gene_symbol == ""
        assert asociacion.synonyms == []
        assert asociacion.external_references == {}

    def test_locus_sinonimos_y_referencias_ausentes(self):
        asociacion = _parse_gene_association({"Gene": {"Symbol": "TTR"}})
        assert asociacion.locus == ""
        assert asociacion.gene_name == ""
        assert asociacion.gene_type == ""
        assert asociacion.external_references == {}

    def test_referencia_externa_incompleta_se_ignora(self):
        crudo = _asociacion()
        crudo["Gene"]["ExternalReference"] = [
            {"Source": "HGNC"}, {"Reference": "176300"}, {"Source": "OMIM", "Reference": "1"},
        ]
        asociacion = _parse_gene_association(crudo)
        assert asociacion.external_references == {"OMIM": "1"}

    @pytest.mark.asyncio
    async def test_asociacion_sin_simbolo_se_descarta(self, cliente):
        """Un registro sin símbolo no se cuenta como gen: no se inventa nada."""
        payload = _respuesta_200({"DisorderGeneAssociationType": "x", "Gene": {}},
                                 _asociacion())
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        genes = await cliente.get_disease_genes("85447")
        assert genes is not None and genes.gene_symbols == ["TTR"]

    @pytest.mark.asyncio
    async def test_sin_disorder_gene_association_devuelve_cero_asociaciones(self, cliente):
        payload = _respuesta_200()
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        genes = await cliente.get_disease_genes("85447")
        assert genes is not None
        assert genes.associations == [] and genes.gene_symbols == []
        assert "sin asociación génica" in genes.summary()

    @pytest.mark.asyncio
    async def test_sin_licencia_declarada_usa_la_de_orphadata(self, cliente):
        payload = _respuesta_200(_asociacion())
        del payload["data"]["__licence"]
        cliente._client = _transporte(_RespuestaFalsa(200, payload))
        genes = await cliente.get_disease_genes("85447")
        assert genes is not None and genes.licence == "CC-BY-4.0"


# ── Circuit breaker ───────────────────────────────────────────────────────────

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_tres_fallos_abren_el_circuito(self, cliente):
        transporte = _transporte(_RespuestaFalsa(500, texto="boom"))
        cliente._client = transporte

        for _ in range(3):
            with pytest.raises(ExternalApiError):
                await cliente.get_disease_genes("85447")

        with pytest.raises(ApiUnavailableError):
            await cliente.get_disease_genes("85447")
        # La cuarta consulta no sale a la red.
        assert len(transporte.urls) == 3

    @pytest.mark.asyncio
    async def test_sin_asociacion_no_cuenta_como_fallo(self, cliente):
        cliente._client = _transporte(_RespuestaFalsa(404, _404_SIN_ASOCIACION))
        for _ in range(5):
            assert await cliente.get_disease_genes("271861") is None
        assert orphadata_breaker.is_available


# ── Dataclasses ───────────────────────────────────────────────────────────────

class TestDataclasses:
    def test_url_se_genera_si_la_api_no_la_trae(self):
        genes = DiseaseGenes(orpha_code="85447", name="ATTRV30M amyloidosis")
        assert "85447" in genes.url

    def test_to_context_str_incluye_tipo_estado_y_pmid(self):
        asociacion = GeneAssociation(
            gene_symbol="TTR", gene_name="transthyretin",
            association_type="Disease-causing germline mutation(s) in",
            association_status="Assessed", source_of_validation="18925456[PMID]",
            locus="18q12.1",
        )
        texto = asociacion.to_context_str()
        assert "TTR" in texto and "transthyretin" in texto
        assert "Disease-causing" in texto and "Assessed" in texto
        assert "18q12.1" in texto and "18925456" in texto

    def test_validacion_que_no_es_pmid_no_se_recorta(self):
        asociacion = GeneAssociation(gene_symbol="TTR", source_of_validation="ORPHA:1")
        assert asociacion.pmid_validacion == ""

    def test_summary_cita_la_licencia_y_recorta(self):
        genes = DiseaseGenes(
            orpha_code="586", name="Cystic fibrosis",
            associations=[GeneAssociation(gene_symbol=f"G{i}") for i in range(7)],
        )
        resumen = genes.summary()
        assert "CC-BY-4.0" in resumen and "ORPHA:586" in resumen
        assert "y 2 más" in resumen


# ── OrphanetClient delega en este cliente ─────────────────────────────────────

class TestDelegacionDesdeOrphanet:
    """
    `OrphanetClient.get_genes()` ya no levanta: delega en OrphadataClient. Acá se
    ejercita el camino completo con el transporte falso puesto en el cliente
    delegado, que es lo que el pipeline va a recorrer.
    """

    @pytest.mark.asyncio
    async def test_get_genes_trae_los_simbolos(self):
        cliente = OrphanetClient()
        cliente._orphadata = OrphadataClient()
        cliente._orphadata._client = _transporte(
            _RespuestaFalsa(200, _respuesta_200(_asociacion()))
        )
        assert await cliente.get_genes("85447") == ["TTR"]

    @pytest.mark.asyncio
    async def test_enrich_with_genes_completa_la_enfermedad(self):
        cliente = OrphanetClient()
        cliente._orphadata = OrphadataClient()
        cliente._orphadata._client = _transporte(
            _RespuestaFalsa(200, _respuesta_200(_asociacion()))
        )
        enfermedad = RareDisease(orpha_code="85447", name="ATTRV30M amyloidosis",
                                 definition="")
        resultado = await cliente.enrich_with_genes(enfermedad)
        assert resultado is enfermedad
        assert enfermedad.genes == ["TTR"]
        assert "TTR" in enfermedad.summary()

    @pytest.mark.asyncio
    async def test_sin_asociacion_deja_la_enfermedad_sin_genes(self):
        cliente = OrphanetClient()
        cliente._orphadata = OrphadataClient()
        cliente._orphadata._client = _transporte(
            _RespuestaFalsa(404, _404_SIN_ASOCIACION)
        )
        enfermedad = RareDisease(orpha_code="271861", name="Hereditary ATTR amyloidosis",
                                 definition="")
        assert (await cliente.enrich_with_genes(enfermedad)).genes == []

    @pytest.mark.asyncio
    async def test_un_fallo_de_orphadata_se_propaga(self):
        cliente = OrphanetClient()
        cliente._orphadata = OrphadataClient()
        cliente._orphadata._client = _transporte(_RespuestaFalsa(500, texto="boom"))
        with pytest.raises(ExternalApiError):
            await cliente.get_genes("85447")
