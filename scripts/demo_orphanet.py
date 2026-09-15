"""
Demo — Cliente Orphanet: búsqueda de enfermedades raras.

Este script **consulta la API real**. La versión anterior usaba datos
simulados, y eso tapaba dos cosas:

1. `search()` apuntaba a `/approximatelymatching`, un endpoint que no existe:
   devuelve 404. Como el cliente atrapaba `except (httpx.HTTPError, Exception)`
   y devolvía `[]`, nunca falló de forma visible. Nunca trajo un resultado real.
2. Los códigos ORPHA simulados no son los que devuelve Orphanet. El demo
   afirmaba ORPHA:85163 para la amiloidosis ATTR hereditaria; el código real
   es **ORPHA:271861**.

Los genes no se consultan acá: la ORPHAcodes API no expone ese dato (32 rutas,
ninguna de genes). Ver el docstring de `backend/external/orphanet.py`.

Correrlo necesita conexión. No necesita GROQ_API_KEY.

    python scripts/demo_orphanet.py

Artefactos generados en output/demo_orphanet/:
    1. enfermedades.txt → lo que devuelve la API real, término por término
    2. resumen.json     → el mismo resultado en JSON
"""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.external.orphanet import (
    OrphanetClient,
    OrphanetGenesNoDisponibles,
)
from backend.external.rate_limiter import ExternalApiError

_SEP = "═" * 78
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_orphanet"

# Términos en inglés médico, que es como indexa Orphanet. El caso de la tesis
# (neuropatía axonal sensitivomotora, varón de 42 años) y su sospecha principal.
_TERMINOS = [
    "hereditary transthyretin amyloidosis",
    "axonal sensorimotor polyneuropathy",
    "Charcot-Marie-Tooth",
]


async def main() -> None:
    print(_SEP)
    print("DEMO — Cliente Orphanet contra la API REAL")
    print(_SEP)
    print("\nBase URL: https://api.orphacode.org/EN/ClinicalEntity")
    print("(el endpoint anterior, /approximatelymatching, no existe: 404)")

    resultados: dict[str, list[dict]] = {}
    lineas: list[str] = ["NEXUS — Orphanet: consulta a la API real", "=" * 70, ""]

    async with OrphanetClient() as client:
        print(f"\n{'─' * 78}\n1. Búsqueda por nombre aproximado\n{'─' * 78}")
        for termino in _TERMINOS:
            try:
                encontradas = await client.search(termino, max_results=3)
            except ExternalApiError as exc:
                print(f"  '{termino}' → ERROR: {exc}")
                lineas.append(f"{termino}: ERROR — {exc}")
                continue

            resultados[termino] = [asdict(d) for d in encontradas]
            print(f"\n  '{termino}' → {len(encontradas)} resultados")
            lineas.append(f"TÉRMINO: {termino} ({len(encontradas)} resultados)")
            for d in encontradas:
                print(f"      ORPHA:{d.orpha_code:<8} {d.name[:56]}")
                lineas.append(f"  ORPHA:{d.orpha_code}  {d.name}")
                lineas.append(f"       {d.url}")
            lineas.append("")

        print(f"\n{'─' * 78}\n2. Detalle por código: definición y sinónimos\n{'─' * 78}")
        print("  ApproximateName solo devuelve ORPHAcode y 'Preferred term'.")
        print("  La definición y los sinónimos exigen una segunda llamada.\n")
        try:
            detalle = await client.get_by_code("271861")
        except ExternalApiError as exc:
            # El demo no se cae por un fallo de red: lo reporta, que es
            # precisamente lo que el cliente ahora sabe distinguir.
            print(f"  La API falló: {exc}")
            lineas.append(f"DETALLE ORPHA:271861 — la API falló: {exc}")
            detalle = None

        if detalle:
            print(f"  ORPHA:{detalle.orpha_code} — {detalle.name}")
            print(f"  sinónimos: {', '.join(detalle.synonyms[:4]) or '(ninguno)'}")
            print(f"  definición: {(detalle.definition or '(no disponible)')[:90]}")
            lineas.append(f"DETALLE ORPHA:{detalle.orpha_code} — {detalle.name}")
            lineas.append(f"  Sinónimos: {', '.join(detalle.synonyms)}")
            lineas.append(f"  Definición: {detalle.definition or '(no disponible)'}")
            resultados["_detalle_271861"] = [asdict(detalle)]

        print(f"\n{'─' * 78}\n3. Distinguir 'sin resultados' de 'la API falló'\n{'─' * 78}")
        vacio = await client.search("zzzzzznoexisteestaenfermedad")
        print(f"  Término inexistente → {vacio}  (404 'Query not found', sin excepción)")
        print(f"  Código inexistente  → {await client.get_by_code('99999999')}")

        print(f"\n{'─' * 78}\n4. Genes: esta API no los tiene\n{'─' * 78}")
        try:
            await client.get_genes("271861")
        except OrphanetGenesNoDisponibles as exc:
            print(f"  OrphanetGenesNoDisponibles:")
            for linea in str(exc).split(". "):
                print(f"      {linea.strip()}")
            lineas.append(f"GENES: {exc}")
        print("\n  Antes devolvía [] en silencio, que se lee como 'esta enfermedad")
        print("  no tiene genes asociados' — y es falso: el dato está en otra API.")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt = _OUT_DIR / "enfermedades.txt"
    txt.write_text("\n".join(lineas), encoding="utf-8")
    resumen = _OUT_DIR / "resumen.json"
    resumen.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{_SEP}")
    print("Artefactos:")
    print(f"  • {txt}")
    print(f"  • {resumen}")
    print(_SEP)


if __name__ == "__main__":
    asyncio.run(main())
