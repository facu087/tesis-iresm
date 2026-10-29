"""
Demo — Estado y causa de la verificación bibliográfica (tarjeta #91, Sprint 4).

Antes, cuando PubMed no respondía, las fuentes quedaban `no_verificable` y el
motivo solo se imprimía por stderr: el reporte no decía si la verificación
había corrido ni por qué no. Ahora el reporte lleva un estado global
(`completa`, `parcial`, `no_disponible`, `sin_consulta`) y, si hubo un fallo,
una causa en categorías (`red`, `limite_velocidad`, `configuracion`,
`error_api`, `desconocida`). Nunca el texto de la excepción.

Este script corre sin red ni cuota. Sobre el caso base (neuropatía axonal
sensitivomotora, varón de 42 años) simula cada situación reemplazando el
cliente de PubMed, y para cada una muestra entrada → salida:

  entrada: qué respondió PubMed en la verificación inicial y en la Ronda 5
  salida:  estado, causa, referencias no verificables y el aviso del PDF

También comprueba que ni la URL consultada ni el valor de la clave, que van
dentro del texto de la excepción simulada, llegan al JSON ni al PDF.

    python scripts/demo_estado_verificacion.py

Artefactos en output/demo_estado_verificacion/:
    resultado.txt              → la corrida completa
    resumen.json               → estado y causa por escenario
    reporte_no_disponible.pdf  → el PDF del escenario con PubMed caído (400)
    reporte_no_disponible.json → el mismo reporte, para cargarlo en /report

Sale con código 1 si alguna comprobación falla.
"""

import asyncio
import io
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
import pdfplumber

from backend.models.case import ClinicalCase
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from backend.models.report import Report
from backend.pipeline import verification
from backend.pipeline.pdf_exporter import generate_pdf
from backend.pipeline.report_builder import build_export
from backend.pipeline.verification import (
    estado_verificacion,
    registro_de_consultas,
    verify_report_sources,
    verify_sources,
)

_SEP = "═" * 78
_SUB = "─" * 78
_OUT_DIR = _RAIZ / "output" / "demo_estado_verificacion"

# La clave y la URL viajan dentro del texto de la excepción simulada: es lo que
# no tiene que aparecer en el reporte.
_CLAVE = "CLAVE-DEMO-NO-REAL-0000"
_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    f"?db=pubmed&id=12345678&api_key={_CLAVE}"
)
_METADATA = {"12345678": {"title": "Vitamin B12 deficiency and axonal neuropathy"}}

_lineas: list[str] = []


def emitir(texto: str = "") -> None:
    """Imprime y guarda la línea para resultado.txt."""
    print(texto)
    _lineas.append(texto)


def _error_http(codigo: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", _URL)
    return httpx.HTTPStatusError(
        f"Error {codigo} for url '{_URL}'",
        request=request,
        response=httpx.Response(codigo, request=request),
    )


class _PubMedSimulado:
    """Reemplaza a PubMedClient: cada consulta toma el próximo resultado de la lista."""

    respuestas: list[object] = []

    async def __aenter__(self) -> "_PubMedSimulado":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def fetch_metadata(self, pmids: list[str]) -> dict[str, dict]:
        respuesta = _PubMedSimulado.respuestas.pop(0)
        if isinstance(respuesta, BaseException):
            raise respuesta
        return {p: respuesta[p] for p in pmids if p in respuesta}  # type: ignore[index]


def _caso_base() -> tuple[ClinicalCase, Report]:
    caso = ClinicalCase(
        raw_text="Varón de 42 años con neuropatía axonal sensitivomotora de 2 años de evolución."
    )
    hipotesis = Hypothesis(
        text="Neuropatía axonal por déficit de vitamina B12 asociado a metformina.",
        priority=Priority.HIGH,
        evidence_level=EvidenceLevel.II,
        rationale="Diabetes tipo 2 tratada con metformina; patrón axonal longitud-dependiente.",
        sources=[Source(pmid="12345678", title="Vitamin B12 deficiency and axonal neuropathy")],
    )
    return caso, Report(case_summary="Varón de 42 años, neuropatía axonal.", hypotheses=[hipotesis])


_ESCENARIOS: list[tuple[str, str, list[object], bool]] = [
    # (nombre, descripción de la entrada, respuestas de PubMed, hay Ronda 5)
    ("pubmed_responde", "PubMed responde", [_METADATA], False),
    ("sin_conexion", "Sin conexión (ConnectError)", [httpx.ConnectError(f"refused {_URL}")], False),
    ("limite_velocidad", "HTTP 429 tras los reintentos", [_error_http(429)], False),
    ("clave_mal_configurada", "HTTP 400 (api_key mal formada)", [_error_http(400)], False),
    ("servicio_caido", "HTTP 503", [_error_http(503)], False),
    ("falla_ronda_5", "Inicial responde; la Ronda 5 recibe 503", [_METADATA, _error_http(503)], True),
]

_ESPERADO = {
    "pubmed_responde": ("completa", None),
    "sin_conexion": ("no_disponible", "red"),
    "limite_velocidad": ("no_disponible", "limite_velocidad"),
    "clave_mal_configurada": ("no_disponible", "configuracion"),
    "servicio_caido": ("no_disponible", "error_api"),
    "falla_ronda_5": ("parcial", "error_api"),
}


def _texto_pdf(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as documento:
        texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
    return " ".join(texto.split())


def _aviso_portada(texto: str) -> str:
    for titulo in ("Verificación bibliográfica no disponible:", "Verificación bibliográfica incompleta:"):
        inicio = texto.find(titulo)
        if inicio >= 0:
            fin = texto.find("no invalidadas.", inicio)
            return texto[inicio: fin + len("no invalidadas.")] if fin >= 0 else texto[inicio: inicio + 300]
    return "(sin aviso de verificación incompleta)"


async def _correr(respuestas: list[object], ronda_5: bool):
    _PubMedSimulado.respuestas = list(respuestas)
    caso, reporte = _caso_base()
    with registro_de_consultas() as consultas:
        veredictos = await verify_report_sources(reporte)
        if ronda_5:
            # Lo que hace el Árbitro al re-verificar las fuentes recitadas.
            veredictos.update(await verify_sources(
                [Source(pmid="87654321", title="Cobalamin and peripheral neuropathy")]
            ))
    estructurado = build_export(
        case=caso, report=reporte, trials=[], processing_time=1.0,
        verifications=veredictos, estado_verificacion=estado_verificacion(consultas),
    )
    return estructurado, generate_pdf(estructurado)


def main() -> int:
    verification.PubMedClient = _PubMedSimulado  # type: ignore[misc]
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    emitir(_SEP)
    emitir("NEXUS — Estado y causa de la verificación bibliográfica (tarjeta #91)")
    emitir("Caso base: neuropatía axonal sensitivomotora, varón de 42 años. Sin red ni cuota.")
    emitir(_SEP)

    fallas: list[str] = []
    resumen: dict[str, dict] = {}

    for nombre, entrada, respuestas, ronda_5 in _ESCENARIOS:
        estructurado, pdf = asyncio.run(_correr(respuestas, ronda_5))
        v = estructurado.verification
        json_reporte = estructurado.model_dump_json()
        texto = _texto_pdf(pdf)

        emitir(f"\n{_SUB}\n{nombre}\n{_SUB}")
        emitir(f"  entrada : {entrada}")
        emitir(f"  salida  : estado={v.estado}  causa={v.causa}  no_verificables={v.no_verificables}")
        emitir(f"  PDF     : {_aviso_portada(texto)}")

        if (v.estado, v.causa) != _ESPERADO[nombre]:
            fallas.append(f"{nombre}: se esperaba {_ESPERADO[nombre]}, salió {(v.estado, v.causa)}")
        for secreto, donde in ((_CLAVE, "la clave"), ("eutils.ncbi", "la URL")):
            if secreto in json_reporte or secreto in texto:
                fallas.append(f"{nombre}: {donde} aparece en el reporte")
        resumen[nombre] = {
            "entrada": entrada,
            "estado": v.estado,
            "causa": v.causa,
            "no_verificables": v.no_verificables,
        }

        if nombre == "clave_mal_configurada":
            (_OUT_DIR / "reporte_no_disponible.pdf").write_bytes(pdf)
            (_OUT_DIR / "reporte_no_disponible.json").write_text(
                estructurado.model_dump_json(indent=2), encoding="utf-8"
            )

    emitir(f"\n{_SEP}")
    if fallas:
        emitir("COMPROBACIONES FALLIDAS:")
        for falla in fallas:
            emitir(f"  ✗ {falla}")
    else:
        emitir(f"OK: {len(_ESCENARIOS)} escenarios con el estado y la causa esperados;")
        emitir("ni la URL ni la clave llegan al JSON ni al PDF.")
    emitir(f"Artefactos: {_OUT_DIR}")
    emitir(_SEP)

    (_OUT_DIR / "resultado.txt").write_text("\n".join(_lineas) + "\n", encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps({"escenarios": resumen, "fallas": fallas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
