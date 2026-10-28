"""
Cliente para la API de Orphadata — genes asociados a enfermedades raras.

Base URL: https://api.orphadata.com/rd-associated-genes
Autenticación: ninguna (medido el 2026-10-06: responde 200 sin `apiKey`).
Licencia de los datos: **CC-BY-4.0**, declarada en cada respuesta
(`data.__licence`). Hay que citar a Orphanet al mostrar estos genes.

## Por qué existe este módulo

`backend/external/orphanet.py` habla con la **ORPHAcodes API**
(`api.orphacode.org`), que es de *nomenclatura*: nombres, sinónimos,
clasificación y mapeos a ICD/OMIM/SNOMED. Expone 32 rutas y **ninguna de
genes** — por eso `_get_genes()` daba 404 contra `/DisorderGene/{code}`, y no
por un path mal escrito.

Los genes están en **Orphadata**, otro producto y otro host, en el dataset
"Rare diseases and associated genes". Este módulo es ese cliente, y
`OrphanetClient.get_genes()` / `enrich_with_genes()` delegan en él: para el
pipeline sigue siendo "los genes que Orphanet asocia a este ORPHAcode", y el
reparto en dos hosts queda acá adentro.

Rutas del dataset (verificadas el 2026-10-06, de las 5 que trae la spec
OpenAPI para `rd-associated-genes`):
  - /orphacodes              → índice del dataset (4.245 entidades con genes)
  - /orphacodes/{orphacode}  → asociaciones génicas de una enfermedad ← la que se usa

## Forma real de la respuesta (200)

    {"data": {"__count": 1,
              "__licence": {"identifier": "CC-BY-4.0", ...},
              "results": {"ORPHAcode": 85447,
                          "Preferred term": "ATTRV30M amyloidosis",
                          "Typology": "Clinical subtype",
                          "DisorderGroup": "Subtype of disorder",
                          "OrphanetURL": "http://www.orpha.net/...",
                          "Date": "2026-06-23 07:57:31",
                          "DisorderGeneAssociation": [
                            {"DisorderGeneAssociationStatus": "Assessed",
                             "DisorderGeneAssociationType":
                                 "Disease-causing germline mutation(s) in",
                             "SourceOfValidation": "18925456[PMID]",   # puede ser null
                             "Gene": {"Symbol": "TTR",
                                      "name": "transthyretin",
                                      "GeneType": "gene with protein product",
                                      "Synonym": ["CTS", "HsT2651"],
                                      "Locus": [{"GeneLocus": "18q12.1", "LocusKey": 1}],
                                      "ExternalReference": [{"Source": "HGNC",
                                                             "Reference": "12405"}, ...]}}]}},
     "datasetCategory": {...}, "parameters": {...}, "uri": "..."}

`results` es un **objeto**, no una lista: una consulta por ORPHAcode devuelve
una enfermedad. `DisorderGeneAssociation` sí es lista y puede traer varias
asociaciones (medido: Cystic fibrosis / ORPHA:586 → 19, una causal y el resto
modificadoras).

## Los dos 404 de este host, que NO significan lo mismo

  1. `application/json` con `{"error": {"code": 404, "type": "Query not
     found"}}` → la ruta existe y el ORPHAcode **no tiene asociación génica**
     en el dataset. Es un resultado válido: devuelve None / [].
  2. `application/problem+json` con `{"title": "Not Found", "detail": "The
     requested URL was not found..."}` → **la ruta no existe**. Eso es un bug
     nuestro (path mal armado, código no numérico) y levanta ExternalApiError.

Confundirlos es exactamente el error que ya se pagó dos veces en este repo
(Orphanet y PharmGKB): tratar "la API no tiene esa ruta" como "no hay datos"
hace que un cliente roto parezca funcionar devolviendo vacío.

## Qué queda fuera del dataset (y por qué el 404 es frecuente)

El dataset cubre 4.245 entidades, no las ~11.000 de la nomenclatura. Medido el
2026-10-06 sobre los códigos que usa el proyecto:

  - ORPHA:85447 (ATTRV30M amyloidosis, subtipo) → 200, gen **TTR**
  - ORPHA:271861 (Hereditary ATTR amyloidosis)  → 404 "Query not found"
  - ORPHA:64746 (Charcot-Marie-Tooth tipo 2 AD, *Group of disorders*) → 404

O sea: la asociación génica suele estar colgada del **subtipo**, no del grupo
ni siempre de la enfermedad. Ojo con la tarjeta #74, que anotaba 271861 → 200
el 2026-09-15: hoy ese código devuelve 404 "Query not found". Un 404 acá nunca
se debe leer como "no hay gen conocido para esta enfermedad", sino como "no
hay asociación cargada para *este* ORPHAcode".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .rate_limiter import ExternalApiError, orphadata_breaker, orphadata_limiter

_API_NAME = "Orphadata"
_BASE_URL = "https://api.orphadata.com/rd-associated-genes"
_ORPHANET_URL_TEMPLATE = "https://www.orpha.net/en/disease/detail/{code}"
_TIMEOUT_S = 30.0

# Licencia de los datos, declarada por la API en `data.__licence`. Se deja como
# default por si una respuesta no la trajera: hay que citar igual.
LICENCIA_POR_DEFECTO = "CC-BY-4.0"

# Prefijo del tipo de asociación que Orphanet usa para los genes causales
# ("Disease-causing germline mutation(s) in", "...(loss of function) in", etc.).
# El resto son modificadoras, candidatas o de susceptibilidad.
_TIPO_CAUSAL = "disease-causing"


@dataclass
class GeneAssociation:
    """
    Una asociación gen–enfermedad de Orphanet, con su tipo y su validación.

    El tipo importa tanto como el símbolo: `TGFB1` aparece en la fibrosis
    quística como gen **modificador**, no como causa. Un cliente que devolviera
    solo los símbolos haría pasar las dos cosas por lo mismo.
    """

    gene_symbol: str
    gene_name: str = ""
    association_type: str = ""      # "Disease-causing germline mutation(s) in", …
    association_status: str = ""    # "Assessed" / "Not yet assessed"
    source_of_validation: str = ""  # "18925456[PMID]" — la API puede traer null
    locus: str = ""                 # "18q12.1"
    gene_type: str = ""             # "gene with protein product"
    synonyms: list[str] = field(default_factory=list)
    external_references: dict[str, str] = field(default_factory=dict)

    @property
    def es_causal(self) -> bool:
        """True si Orphanet la clasifica como asociación causal de la enfermedad."""
        return _TIPO_CAUSAL in self.association_type.lower()

    @property
    def pmid_validacion(self) -> str:
        """PMID de la publicación que valida la asociación, o "" si no hay."""
        fuente = self.source_of_validation
        return fuente[: -len("[PMID]")] if fuente.endswith("[PMID]") else ""

    def to_context_str(self) -> str:
        """Formatea la asociación para el contexto de un agente."""
        return (
            f"{self.gene_symbol}"
            f"{f' ({self.gene_name})' if self.gene_name else ''}"
            f" — {self.association_type or 'tipo de asociación no especificado'}"
            f" [{self.association_status or 'sin estado'}]"
            f"{f', locus {self.locus}' if self.locus else ''}"
            f"{f', validada en PMID {self.pmid_validacion}' if self.pmid_validacion else ''}"
        )


@dataclass
class DiseaseGenes:
    """Genes que Orphadata asocia a un ORPHAcode."""

    orpha_code: str
    name: str = ""
    associations: list[GeneAssociation] = field(default_factory=list)
    typology: str = ""         # "Disease", "Clinical subtype", "Clinical group"
    disorder_group: str = ""   # "Disorder", "Subtype of disorder", "Group of disorders"
    date: str = ""             # fecha de actualización del registro en Orphanet
    url: str = ""
    licence: str = LICENCIA_POR_DEFECTO

    def __post_init__(self) -> None:
        if not self.url:
            self.url = _ORPHANET_URL_TEMPLATE.format(code=self.orpha_code)

    @property
    def gene_symbols(self) -> list[str]:
        """Símbolos de todos los genes asociados, sin repetir y en orden."""
        simbolos: list[str] = []
        for asociacion in self.associations:
            if asociacion.gene_symbol and asociacion.gene_symbol not in simbolos:
                simbolos.append(asociacion.gene_symbol)
        return simbolos

    @property
    def causal_gene_symbols(self) -> list[str]:
        """Solo los símbolos de las asociaciones causales (ver `es_causal`)."""
        simbolos: list[str] = []
        for asociacion in self.associations:
            simbolo = asociacion.gene_symbol
            if asociacion.es_causal and simbolo and simbolo not in simbolos:
                simbolos.append(simbolo)
        return simbolos

    def summary(self) -> str:
        """Resumen corto para incluir en el contexto de un agente."""
        if not self.associations:
            return (
                f"{self.name or 'ORPHA:' + self.orpha_code} (ORPHA:{self.orpha_code}): "
                f"sin asociación génica cargada en Orphadata."
            )
        lineas = [
            f"{self.name or 'ORPHA:' + self.orpha_code} (ORPHA:{self.orpha_code}) — "
            f"genes asociados según Orphanet ({self.licence}):"
        ]
        for asociacion in self.associations[:5]:
            lineas.append(f"  • {asociacion.to_context_str()}")
        if len(self.associations) > 5:
            lineas.append(f"  … y {len(self.associations) - 5} más")
        return "\n".join(lineas)


def _parse_gene_association(item: dict[str, Any]) -> GeneAssociation:
    """
    Construye un GeneAssociation desde un elemento de `DisorderGeneAssociation`.

    Tolera que falten campos: la API trae `SourceOfValidation: null` en
    asociaciones sin publicación de respaldo, y `Locus`, `Synonym` o
    `ExternalReference` pueden no venir. Lo único que no se inventa es el
    símbolo: sin él la asociación se descarta en `_parse_disease_genes()`.
    """
    gene = item.get("Gene") or {}

    locus_items = gene.get("Locus") or []
    locus = ""
    if isinstance(locus_items, list) and locus_items:
        locus = (locus_items[0] or {}).get("GeneLocus", "") or ""

    referencias: dict[str, str] = {}
    for referencia in gene.get("ExternalReference") or []:
        fuente = (referencia or {}).get("Source")
        valor = (referencia or {}).get("Reference")
        if fuente and valor:
            referencias[str(fuente)] = str(valor)

    sinonimos = gene.get("Synonym") or []

    return GeneAssociation(
        gene_symbol=gene.get("Symbol") or "",
        # El nombre del gen viene en minúscula: `name`, no `Name`.
        gene_name=gene.get("name") or "",
        association_type=item.get("DisorderGeneAssociationType") or "",
        association_status=item.get("DisorderGeneAssociationStatus") or "",
        source_of_validation=item.get("SourceOfValidation") or "",
        locus=locus,
        gene_type=gene.get("GeneType") or "",
        synonyms=[s for s in sinonimos if isinstance(s, str)],
        external_references=referencias,
    )


def _parse_disease_genes(
    orpha_code: str,
    data: dict[str, Any],
) -> DiseaseGenes:
    """Construye un DiseaseGenes desde el bloque `data` de una respuesta 200."""
    results = data.get("results")
    if not isinstance(results, dict):
        # La ruta por ORPHAcode devuelve un objeto. Si algún día devolviera una
        # lista, mejor fallar acá que construir un resultado vacío en silencio.
        raise ExternalApiError(
            _API_NAME,
            f"ORPHA:{orpha_code}: `results` no es un objeto "
            f"({type(results).__name__}), la respuesta cambió de forma",
        )

    asociaciones_crudas = results.get("DisorderGeneAssociation") or []
    if not isinstance(asociaciones_crudas, list):
        asociaciones_crudas = [asociaciones_crudas]

    asociaciones = [
        asociacion
        for asociacion in (_parse_gene_association(i) for i in asociaciones_crudas)
        if asociacion.gene_symbol
    ]

    licencia = (data.get("__licence") or {}).get("identifier") or LICENCIA_POR_DEFECTO

    return DiseaseGenes(
        orpha_code=str(results.get("ORPHAcode", orpha_code)),
        name=results.get("Preferred term") or "",
        associations=asociaciones,
        typology=results.get("Typology") or "",
        disorder_group=results.get("DisorderGroup") or "",
        date=results.get("Date") or "",
        url=results.get("OrphanetURL") or "",
        licence=str(licencia),
    )


def _es_consulta_sin_resultados(response: httpx.Response) -> bool:
    """
    Distingue el 404 de "esta enfermedad no tiene genes" del de "ruta inexistente".

    El primero trae `{"error": {"code": 404, "type": "Query not found"}}`; el
    segundo es un problem+json de Connexion con `title`/`detail` y significa
    que la URL no corresponde a ninguna ruta de la API. Ver el docstring del
    módulo: tratarlos igual es lo que hace que un cliente roto parezca andar.
    """
    try:
        cuerpo = response.json()
    except ValueError:
        return False
    return isinstance(cuerpo, dict) and isinstance(cuerpo.get("error"), dict)


class OrphadataClient:
    """
    Cliente asíncrono del dataset "Rare diseases and associated genes".

    No silencia errores: un fallo real levanta ExternalApiError. "Esta
    enfermedad no tiene asociación génica cargada" es un resultado, no un
    fallo, y devuelve None (`get_disease_genes`) o [] (`get_gene_symbols`).

    Uso básico:
        async with OrphadataClient() as client:
            genes = await client.get_disease_genes("85447")
            if genes:
                print(genes.summary())
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OrphadataClient":
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT_S,
            headers={"accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, path: str) -> Optional[dict[str, Any]]:
        """
        Consulta la API y devuelve el bloque `data`, o None si no hubo resultados.

        Raises:
            ExternalApiError: ante un fallo real (401/403, 5xx, red, cuerpo que
                no es JSON, 404 de ruta inexistente). Ver `_es_consulta_sin_resultados`.
        """
        # Breaker compartido por host: tras 3 fallos seguidos las consultas
        # fallan con ApiUnavailableError sin tocar la red.
        async with orphadata_breaker:
            return await self._request_once(path)

    async def _request_once(self, path: str) -> Optional[dict[str, Any]]:
        """Una solicitud, sin circuit breaker (ver `_request`)."""
        assert self._client is not None, "Usar dentro de un bloque async with"

        # Limitador compartido de rate_limiter.py, no uno propio: así el cupo se
        # respeta aunque haya varios OrphadataClient en vuelo a la vez.
        await orphadata_limiter.acquire()

        try:
            response = await self._client.get(f"{_BASE_URL}{path}")
        except httpx.HTTPError as exc:
            raise ExternalApiError(
                _API_NAME, f"No se pudo consultar {path}: {exc}"
            ) from exc

        if response.status_code == 404:
            if _es_consulta_sin_resultados(response):
                return None
            raise ExternalApiError(
                _API_NAME,
                f"{path} no es una ruta de la API (404 de ruteo, no "
                f"'Query not found'): revisar cómo se armó la URL",
                status_code=404,
            )

        if response.status_code in (401, 403):
            # Medido el 2026-10-06: la API responde sin credencial y la spec
            # OpenAPI documenta 403 "Access denied". Se reporta como error en
            # vez de tragarse, para que se note si empieza a exigir clave.
            raise ExternalApiError(
                _API_NAME,
                "rechazó la consulta por credenciales. Orphadata responde sin "
                "clave; si esto persiste, el acceso cambió y hay que registrarse",
                status_code=response.status_code,
            )

        if response.status_code != 200:
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió: {response.text[:120]}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió un cuerpo que no es JSON"
            ) from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió un 200 sin bloque `data`"
            )
        return data

    async def get_disease_genes(self, orpha_code: str) -> Optional[DiseaseGenes]:
        """
        Trae las asociaciones génicas de una enfermedad rara por ORPHAcode.

        Args:
            orpha_code: Código ORPHA numérico (ej: "85447"). Un código no
                numérico no llega a la red: la ruta espera un entero y
                devolvería un 404 de ruteo.

        Returns:
            DiseaseGenes, o None si ese ORPHAcode no tiene asociación génica
            cargada en el dataset (404 "Query not found"). None **no** significa
            "la enfermedad no tiene gen conocido": ver el docstring del módulo.

        Raises:
            ValueError: si `orpha_code` no es un entero positivo.
            ExternalApiError: ante un fallo real de la API.
        """
        codigo = str(orpha_code).strip()
        if not codigo.isdigit() or int(codigo) <= 0:
            raise ValueError(
                f"ORPHAcode inválido: {orpha_code!r}. La ruta espera un entero "
                f"positivo (ej: '85447')."
            )

        data = await self._request(f"/orphacodes/{codigo}")
        if data is None:
            return None
        return _parse_disease_genes(codigo, data)

    async def get_gene_symbols(
        self,
        orpha_code: str,
        *,
        solo_causales: bool = False,
    ) -> list[str]:
        """
        Símbolos de los genes asociados a un ORPHAcode.

        Args:
            orpha_code: Código ORPHA numérico.
            solo_causales: Si es True deja afuera las asociaciones modificadoras,
                candidatas y de susceptibilidad (ver `GeneAssociation.es_causal`).

        Returns:
            Lista de símbolos, sin repetir. Vacía si el ORPHAcode no tiene
            asociación génica cargada — un fallo de la API levanta excepción,
            así que [] nunca encubre un error.

        Raises:
            ValueError: si `orpha_code` no es un entero positivo.
            ExternalApiError: ante un fallo real de la API.
        """
        genes = await self.get_disease_genes(orpha_code)
        if genes is None:
            return []
        return genes.causal_gene_symbols if solo_causales else genes.gene_symbols
