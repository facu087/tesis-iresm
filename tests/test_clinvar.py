"""
Tests del cliente ClinVar (backend/external/clinvar.py). Sin red: los payloads
copian la forma real de esearch/esummary de `db=clinvar` medida el 2026-10-06.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.external import clinvar
from backend.external.clinvar import ClinVarClient, select
from backend.models.genomics import ClinVarStatus


def _registro(uid: str, title: str, gen: str = "TTR", cls: str | None = "Pathogenic",
              fecha: str = "2026/08/20 00:00") -> dict:
    r = {"uid": uid, "accession": f"VCV{int(uid):09d}", "title": title,
         "genes": [{"symbol": gen}]}
    if cls is not None:
        r["germline_classification"] = {
            "description": cls,
            "review_status": "criteria provided, multiple submitters, no conflicts",
            "last_evaluated": fecha,
        }
    return r


TTR_V50M = _registro("13417", "NM_000371.4(TTR):c.148G>A (p.Val50Met)")


class _Fake:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[tuple[str, dict]] = []

    async def get(self, url, params=None):
        self.llamadas.append((url, params))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def aclose(self):
        pass


def _json(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def _esearch(*ids: str) -> httpx.Response:
    return _json({"esearchresult": {"idlist": list(ids)}})


def _esummary(*registros: dict) -> httpx.Response:
    result = {"uids": [r["uid"] for r in registros]} | {r["uid"]: r for r in registros}
    return _json({"result": result})


def _clasificar(fake: _Fake, gen: str = "TTR", variante: str = "c.148G>A"):
    async def run():
        cliente = ClinVarClient()
        cliente._client = fake
        return await cliente.classify(gen, variante)
    return asyncio.run(run())


def test_registro_exacto():
    r = _clasificar(_Fake(_esearch("13417"), _esummary(TTR_V50M)))
    assert r.status == ClinVarStatus.encontrada
    assert r.accession == "VCV000013417"
    assert r.classification == "Pathogenic"
    assert r.url == "https://www.ncbi.nlm.nih.gov/clinvar/variation/13417/"
    assert r.last_evaluated == "2026/08/20"


def test_notacion_proteica_sin_prefijo_coincide():
    assert select("TTR", "Val50Met", {"13417": TTR_V50M}).status == ClinVarStatus.encontrada


def test_notacion_clasica_con_registros_de_otras_variantes_es_ambigua():
    registros = [
        TTR_V50M,
        _registro("13456", "NM_000371.4(TTR):c.157T>C (p.Phe53Leu)"),
        _registro("13450", "NM_000371.4(TTR):c.118G>A (p.Val40Ile)"),
        _registro("1073324", "NM_000371.4(TTR):c.149T>G (p.Val50Gly)"),
        _registro("2920997", "NM_000371.4(TTR):c.147C>T (p.Ala49=)", cls="Benign"),
    ]
    r = _clasificar(_Fake(_esearch(*[x["uid"] for x in registros]), _esummary(*registros)),
                    variante="Val30Met")
    assert r.status == ClinVarStatus.ambigua
    assert r.candidates == 5
    assert r.classification == "" and r.accession == ""


def test_notacion_que_es_parte_de_otra_no_coincide():
    assert select("TTR", "c.48G>A", {"13417": TTR_V50M}).status == ClinVarStatus.ambigua


def test_registro_de_otro_gen_no_se_acepta():
    otro = _registro("99", "NM_000530.8(MPZ):c.148G>A (p.Val50Met)", gen="MPZ")
    assert select("TTR", "c.148G>A", {"99": otro}).status != ClinVarStatus.encontrada


def test_coincidencias_con_clasificaciones_distintas_son_ambiguas():
    a = _registro("1", "X(TTR):c.148G>A (p.Val50Met)", cls="Pathogenic")
    b = _registro("2", "Y(TTR):c.148G>A (p.Val50Met)", cls="Uncertain significance")
    assert select("TTR", "c.148G>A", {"1": a, "2": b}).status == ClinVarStatus.ambigua


def test_sin_ids_es_sin_resultados():
    fake = _Fake(_esearch())
    assert _clasificar(fake).status == ClinVarStatus.sin_resultados
    assert len(fake.llamadas) == 1


@pytest.mark.parametrize("falla", [
    _json({}, status=500),
    httpx.ReadTimeout("timeout"),
    httpx.Response(200, text="<html>no es json</html>"),
])
def test_errores_son_no_disponible(falla):
    assert _clasificar(_Fake(falla)).status == ClinVarStatus.no_disponible


def test_registro_sin_germline_classification_es_no_disponible():
    sin_clase = _registro("13417", TTR_V50M["title"], cls=None)
    r = _clasificar(_Fake(_esearch("13417"), _esummary(sin_clase)))
    assert r.status == ClinVarStatus.no_disponible


def test_solo_viajan_gen_y_notacion(monkeypatch):
    monkeypatch.delenv("PUBMED_API_KEY", raising=False)
    fake = _Fake(_esearch("13417"), _esummary(TTR_V50M))
    _clasificar(fake)
    (_, busqueda), (_, resumen) = fake.llamadas
    assert busqueda == {"db": "clinvar", "retmode": "json",
                        "term": '"TTR"[gene] AND "c.148G>A"', "retmax": "5"}
    assert resumen == {"db": "clinvar", "retmode": "json", "id": "13417"}


def test_usa_el_limitador_de_ncbi_compartido_con_pubmed():
    from backend.external import rate_limiter
    assert clinvar.pubmed_limiter is rate_limiter.pubmed_limiter
    assert clinvar.pubmed_breaker is rate_limiter.pubmed_breaker
