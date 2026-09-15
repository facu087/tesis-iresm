"""
Demo — Cliente PharmGKB/ClinPGx: relaciones fármaco-genómicas.

Este script **consulta la API real**. La versión anterior usaba datos
simulados, y eso tapaba dos problemas a la vez:

1. El cliente apuntaba a `api.pharmgkb.org`, un host que fue dado de baja y
   hoy no resuelve por DNS. Como atrapaba `except (httpx.HTTPError, Exception)`
   y devolvía `[]`, nunca falló de forma visible: "funcionaba" sin haber
   hablado nunca con PharmGKB.
2. Los datos simulados **contradicen la base real**. Afirmaban que TTR tenía
   anotaciones de nivel 1A/1B con patisiran, tafamidis e inotersen. La API
   devuelve 0 anotaciones clínicas para TTR: es un gen de enfermedad, no un
   farmacogen.

Correrlo necesita conexión. No necesita API key ni GROQ_API_KEY.

    python scripts/demo_pharmgkb.py

Artefactos generados en output/demo_pharmgkb/:
    1. anotaciones.txt → lo que devuelve la API real, gen por gen
    2. resumen.json    → el mismo resultado en JSON
"""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# La consola de Windows usa cp1252 y no puede imprimir los caracteres de caja.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.external.pharmgkb import PharmGKBClient
from backend.external.rate_limiter import ExternalApiError

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_pharmgkb"

# Los cuatro del traspaso: dos genes del caso (neuropatía), uno de la sospecha
# diagnóstica (amiloidosis ATTR) y el farmacogén más anotado de la base.
_GENES = ["PMP22", "MPZ", "TTR", "CYP2D6"]

_ESCALA = """Escala de evidencia PharmGKB:
  1A = Variante en label FDA/EMA + estudios replicados
  1B = Variante en label FDA/EMA
  2A = Variante conocida + estudio único replicado
  2B = Variante conocida + estudio único
  3  = Evidencia limitada
  4  = Caso reporte / anecdótico"""


async def main() -> None:
    print(_SEP)
    print("DEMO — Cliente PharmGKB/ClinPGx contra la API REAL")
    print(_SEP)
    print(f"\nBase URL: https://api.clinpgx.org/v1/data")
    print("(el host anterior, api.pharmgkb.org, ya no resuelve por DNS)")

    resultados: dict[str, list[dict]] = {}
    lineas_txt: list[str] = ["NEXUS — PharmGKB/ClinPGx: consulta a la API real", "=" * 70, ""]

    async with PharmGKBClient() as client:
        print(f"\n{'─' * 78}\n1. Anotaciones clínicas por gen\n{'─' * 78}")
        for gen in _GENES:
            try:
                anotaciones = await client.get_gene_annotations(gen, max_results=5)
            except ExternalApiError as exc:
                print(f"  {gen:8} ERROR: {exc}")
                lineas_txt.append(f"{gen}: ERROR — {exc}")
                continue

            resultados[gen] = [asdict(a) for a in anotaciones]
            if anotaciones:
                print(f"  {gen:8} {len(anotaciones)} anotaciones:")
                lineas_txt.append(f"GEN {gen} — {len(anotaciones)} anotaciones:")
                for a in anotaciones:
                    print(f"      [{a.evidence_level:2}] {a.drug_name:14} → {a.phenotype[:38]}")
                    print(f"           variante: {a.variant[:60]}")
                    lineas_txt.append(f"  [{a.evidence_level}] {a.to_context_str()}")
                    if a.url:
                        lineas_txt.append(f"       {a.url}")
            else:
                print(f"  {gen:8} sin anotaciones farmacogenómicas")
                lineas_txt.append(f"GEN {gen} — sin anotaciones farmacogenómicas")
            lineas_txt.append("")

        print("\n  Ojo con PMP22, MPZ y TTR: 0 anotaciones NO es un fallo. Son genes")
        print("  de enfermedad, no farmacogenes, y la API lo dice con un 404 que el")
        print("  cliente traduce a lista vacía. El demo anterior inventaba para TTR")
        print("  tres anotaciones 1A/1B con patisiran, tafamidis e inotersen.")

        print(f"\n{'─' * 78}\n2. Distinguir 'sin resultados' de 'la API falló'\n{'─' * 78}")
        vacio = await client.get_gene_annotations("NOEXISTEESTEGEN")
        print(f"  Gen inexistente     → {vacio} (404, sin excepción)")

        try:
            await client._request("/clinicalAnnotation", {"pageSize": "1"})
            print("  Query mal formada   → (no debería llegar acá)")
        except ExternalApiError as exc:
            print(f"  Query mal formada   → ExternalApiError, HTTP {exc.status_code}")
            print(f"                        {str(exc)[:90]}")
            lineas_txt.append(f"Query mal formada -> {exc}")

        print(f"\n{'─' * 78}\n3. Interacciones de un fármaco\n{'─' * 78}")
        interaccion = await client.get_drug_interactions("warfarin", max_results=5)
        if interaccion:
            print(f"  warfarin  id={interaccion.pharmgkb_id}")
            print(f"  genes asociados: {', '.join(interaccion.genes[:8])}…")
            print(f"  {interaccion.summary().splitlines()[1][:95]}")
            lineas_txt.append("FÁRMACO warfarin:")
            lineas_txt.append(interaccion.summary())
            resultados["_warfarin"] = [asdict(a) for a in interaccion.annotations]

        inexistente = await client.get_drug_interactions("NOEXISTEFARMACO")
        print(f"  Fármaco inexistente → {inexistente} (None, sin excepción)")

    lineas_txt.append("")
    lineas_txt.append(_ESCALA)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt = _OUT_DIR / "anotaciones.txt"
    txt.write_text("\n".join(lineas_txt), encoding="utf-8")
    resumen = _OUT_DIR / "resumen.json"
    resumen.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{_SEP}")
    print("Artefactos:")
    print(f"  • {txt}")
    print(f"  • {resumen}")
    print(_SEP)


if __name__ == "__main__":
    asyncio.run(main())
