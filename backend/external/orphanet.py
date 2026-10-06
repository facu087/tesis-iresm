"""
Cliente para la API de Orphanet (ORPHAcodes API — Nomenclature Pack, RD-CODE).

Documentación oficial: https://api.orphacode.org/
Base URL: https://api.orphacode.org/EN/ClinicalEntity

Autenticación: la documentación pide un header `apiKey` con registro en
orphanet.org, pero **medido el 2026-09-15 la API responde 200 sin ninguna
clave** (10 de 10 llamadas, sobre los dos endpoints que se usan). Aparecen 401
de forma intermitente al sondear rápido, así que el header se manda igual —
con `ORPHANET_API_KEY` si está definida y con `test`, que la API acepta, si no.
Cuesta nada y cubre el día que el control se empiece a aplicar de verdad.

Endpoints usados (verificados contra la API real el 2026-09-15):
  - /ApproximateName/{label}        → búsqueda por nombre aproximado
  - /orphacode/{code}               → datos de una enfermedad por código ORPHA
  - /orphacode/{code}/Definition    → solo la definición

Códigos de respuesta:
  - 200 → datos
  - 404 + "Query not found" → **sin resultados, no es un error**
  - 401 → intermitente; se reporta como error de configuración por si alguna vez
          pasa a ser permanente
  - 5xx / red → la API falló

La versión anterior usaba `/approximatelymatching`, que devuelve 404 genérico
porque ese endpoint no existe, y atrapaba `except (httpx.HTTPError, Exception)`
devolviendo `[]`. El cliente "funcionaba" sin haber traído nunca un resultado
real, y `demo_orphanet.py` usaba datos simulados, así que tampoco se notaba ahí.

## Genes: esta API no los tiene, los trae Orphadata

`_get_genes()` apuntaba a `/DisorderGene/{code}`, que da 404. No es un path
equivocado: bajando la especificación OpenAPI, la API expone **32 rutas y
ninguna de genes**. Es una API de *nomenclatura* — nombres, sinónimos,
clasificación, diferenciales y mapeos a ICD-10/11, OMIM y SNOMED.

Los genes viven en otro producto de Orphanet, **Orphadata**, en otro host:

    GET https://api.orphadata.com/rd-associated-genes/orphacodes/{code}

Ese cliente es `backend/external/orphadata.py` (tarjeta #74), y `get_genes()` /
`enrich_with_genes()` **delegan en él**: para el pipeline los genes siguen
siendo "lo que Orphanet asocia a este ORPHAcode", y el reparto en dos hosts
queda como detalle interno. `OrphanetGenesNoDisponibles` ya no existe: la
levantaba este módulo mientras el dato no se podía traer.

Ojo con lo que significa una lista vacía: Orphadata devuelve 404 "Query not
found" cuando *ese* ORPHAcode no tiene asociación cargada, lo cual es habitual
en los grupos de enfermedades (la asociación cuelga del subtipo). No es "no se
conoce gen para esta enfermedad". Ver el docstring de `orphadata.py`.
"""

from __future__ import annotations

import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import httpx

from .orphadata import OrphadataClient
from .rate_limiter import ExternalApiError, orphanet_limiter

_API_NAME = "Orphanet"
_BASE_URL = "https://api.orphacode.org/EN/ClinicalEntity"
_ORPHANET_URL_TEMPLATE = "https://www.orpha.net/en/disease/detail/{code}"

# La API acepta `test` como clave. Ver el docstring: hoy no la exige, pero
# mandarla es gratis y cubre el caso de que empiece a exigirla.
_DEFAULT_API_KEY = "test"


@dataclass
class RareDisease:
    """Representa una enfermedad rara de Orphanet."""

    orpha_code: str
    name: str
    definition: str
    genes: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = _ORPHANET_URL_TEMPLATE.format(code=self.orpha_code)

    def summary(self) -> str:
        """Resumen corto para incluir en el contexto de un agente."""
        genes_str = ", ".join(self.genes[:5]) if self.genes else "no especificados"
        definicion = self.definition or "sin definición disponible"
        if len(definicion) > 200:
            definicion = definicion[:200] + "…"
        return (
            f"{self.name} (ORPHA:{self.orpha_code}). "
            f"Genes asociados: {genes_str}. "
            f"{definicion}"
        )


class OrphanetClient:
    """
    Cliente asíncrono para la API de Orphanet.

    No silencia los errores: un fallo real levanta ExternalApiError. "Sin
    resultados" (404 con "Query not found") devuelve lista vacía o None.

    Los genes salen de Orphadata, otro host: el cliente mantiene un
    `OrphadataClient` propio mientras está abierto y le delega `get_genes()` y
    `enrich_with_genes()`. Para quien lo usa sigue siendo un solo cliente de
    Orphanet.

    Uso básico:
        async with OrphanetClient() as client:
            diseases = await client.search("hereditary transthyretin amyloidosis")
            genes = await client.get_genes(diseases[0].orpha_code)
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("ORPHANET_API_KEY") or _DEFAULT_API_KEY
        self._client: Optional[httpx.AsyncClient] = None
        self._orphadata: Optional[OrphadataClient] = None
        self._pila: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "OrphanetClient":
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"apiKey": self._api_key, "accept": "application/json"},
        )
        self._pila = AsyncExitStack()
        self._orphadata = await self._pila.enter_async_context(OrphadataClient())
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
        if self._pila:
            await self._pila.aclose()
            self._pila = None
            self._orphadata = None

    async def _request(self, path: str) -> Any:
        """
        Consulta la API y devuelve el JSON, o None si no hubo resultados.

        Raises:
            ExternalApiError: ante un fallo real (401, 5xx, red). Un 404 NO es
                              un fallo: la API lo usa para "Query not found".
        """
        assert self._client is not None, "Usar dentro de un bloque async with"

        await orphanet_limiter.acquire()

        try:
            response = await self._client.get(f"{_BASE_URL}{path}")
        except httpx.HTTPError as exc:
            raise ExternalApiError(
                _API_NAME, f"No se pudo consultar {path}: {exc}"
            ) from exc

        if response.status_code == 404:
            return None

        if response.status_code == 401:
            # Medido: la API responde sin apiKey, pero devuelve 401 de forma
            # intermitente al sondear rápido. Se reporta como error en vez de
            # tragarse, para que se note si alguna vez pasa a ser permanente.
            raise ExternalApiError(
                _API_NAME,
                "rechazó la credencial. La API suele responder sin apiKey, así "
                "que puede ser intermitente; si persiste, definir ORPHANET_API_KEY",
                status_code=401,
            )

        if response.status_code != 200:
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió: {response.text[:120]}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ExternalApiError(
                _API_NAME, f"{path} devolvió un cuerpo que no es JSON"
            ) from exc

    async def search(self, name: str, max_results: int = 5) -> list[RareDisease]:
        """
        Busca enfermedades raras por nombre aproximado.

        `ApproximateName` devuelve solo ORPHAcode y "Preferred term": no trae
        definición ni sinónimos. Para completarlos hay que llamar a
        `get_by_code()`, que es una consulta por enfermedad — por eso no se hace
        automáticamente acá.

        Args:
            name: Nombre o término de búsqueda, en inglés médico
            max_results: Cantidad máxima de resultados

        Returns:
            Lista de RareDisease, vacía si no hubo coincidencias.

        Raises:
            ExternalApiError: ante un fallo real de la API.
        """
        # El término va en el path, no en la query: los nombres médicos llevan
        # espacios y comas, así que hay que escaparlos.
        data = await self._request(f"/ApproximateName/{quote(name, safe='')}")
        if not data:
            return []

        items = data if isinstance(data, list) else [data]
        diseases: list[RareDisease] = []
        for item in items[:max_results]:
            # El campo es ORPHAcode, no OrphaCode: con el nombre anterior el
            # código habría construido códigos vacíos aun con el path correcto.
            codigo = item.get("ORPHAcode", "")
            if codigo == "":
                continue
            diseases.append(RareDisease(
                orpha_code=str(codigo),
                name=item.get("Preferred term", ""),
                definition="",
                synonyms=[],
            ))
        return diseases

    async def get_by_code(self, orpha_code: str) -> Optional[RareDisease]:
        """
        Trae una enfermedad rara por código ORPHA, con definición y sinónimos.

        Args:
            orpha_code: Código ORPHA numérico (ej: "64746")

        Returns:
            RareDisease, o None si el código no existe.

        Raises:
            ExternalApiError: ante un fallo real de la API.
        """
        data = await self._request(f"/orphacode/{orpha_code}")
        if not data:
            return None

        # `Synonym` es una lista de strings. La versión anterior leía `Synonyms`
        # como lista de dicts con clave "Synonym": no existe ninguno de los dos.
        sinonimos = data.get("Synonym") or []
        definicion = data.get("Definition", "") or ""
        if definicion == "None available":
            definicion = ""

        return RareDisease(
            orpha_code=str(data.get("ORPHAcode", orpha_code)),
            name=data.get("Preferred term", ""),
            definition=definicion,
            synonyms=[s for s in sinonimos if isinstance(s, str)],
        )

    async def get_genes(self, orpha_code: str) -> list[str]:
        """
        Trae los símbolos de los genes asociados a un código ORPHA.

        El dato no está en la ORPHAcodes API: se delega en `OrphadataClient`
        (ver el docstring del módulo). Dentro de un `async with` reusa la
        conexión que el cliente mantiene abierta; fuera de él abre una para la
        consulta, así los tests y los usos puntuales siguen funcionando.

        Args:
            orpha_code: Código ORPHA numérico (ej: "85447")

        Returns:
            Lista de símbolos (ej: ["TTR"]). Vacía si **ese** ORPHAcode no tiene
            asociación génica cargada en Orphadata, que es frecuente en grupos
            de enfermedades: la asociación suele colgar del subtipo. No se debe
            leer como "no se conoce gen para esta enfermedad".

        Raises:
            ValueError: si el código no es un entero positivo.
            ExternalApiError: ante un fallo real de Orphadata.
        """
        if self._orphadata is not None:
            return await self._orphadata.get_gene_symbols(orpha_code)
        async with OrphadataClient() as orphadata:
            return await orphadata.get_gene_symbols(orpha_code)

    async def enrich_with_genes(self, disease: RareDisease) -> RareDisease:
        """
        Completa `disease.genes` con los genes que Orphadata asocia a su código.

        Modifica y devuelve la misma instancia, como hacía la versión original.

        Raises:
            ValueError: si el código de la enfermedad no es un entero positivo.
            ExternalApiError: ante un fallo real de Orphadata.
        """
        disease.genes = await self.get_genes(disease.orpha_code)
        return disease
