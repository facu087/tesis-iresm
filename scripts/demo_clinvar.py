"""
Demo del cliente ClinVar (evidencia para Trello, tarjeta #71).

ENTRADA  gen + notación de variante (lo único que viaja a NCBI)
SALIDA   estado, clasificación germinal, revisión y accession VCV verificable,
         y el bloque que recibe el Agente 02 para un caso con la variante TTR.

Consultas:
  1. TTR c.148G>A   → encontrada (VCV000013417, Pathogenic)
  2. TTR p.Val50Met → encontrada (el mismo registro, notación proteica HGVS)
  3. TTR Val30Met   → ambigua (numeración clásica: ClinVar trae registros de otras variantes)
  4. TTR c.9999G>A  → sin resultados

Uso:
    python3 scripts/demo_clinvar.py            # consultas reales a NCBI (sin LLM)
    python3 scripts/demo_clinvar.py --sin-red  # simula la caída de NCBI

Artefactos en output/demo_clinvar/: clinvar.json y resumen.txt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv()

import httpx

from backend.external.clinvar import ClinVarClient
from backend.models.genomics import GenomicContext
from backend.pipeline.genomic_context import enrich

SALIDA = RAIZ / "output" / "demo_clinvar"
CONSULTAS = [
    ("TTR", "c.148G>A"),
    ("TTR", "p.Val50Met"),
    ("TTR", "Val30Met"),
    ("TTR", "c.9999G>A"),
]


async def _consultas() -> list:
    async with ClinVarClient() as client:
        return [await client.classify(gen, variante) for gen, variante in CONSULTAS]


async def _caso_ttr() -> GenomicContext:
    ctx = GenomicContext(
        genes=["TTR"],
        variants=["c.148G>A"],
        genetic_findings=["TTR c.148G>A (p.Val50Met) heterocigota"],
    )
    return await enrich(ctx)


def _caida_de_red(*_args, **_kwargs):
    raise httpx.ConnectError("NCBI no responde (simulado)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sin-red", action="store_true", help="simula la caída de NCBI")
    args = parser.parse_args()

    lineas: list[str] = []

    def out(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    modo = "caída simulada de NCBI" if args.sin_red else "consultas reales a NCBI"
    out(f"=== ClinVar — {modo} ===")
    out("A NCBI solo viajan el gen y la notación de la variante.\n")

    if args.sin_red:
        with patch("httpx.AsyncClient.get", side_effect=_caida_de_red):
            resultados = asyncio.run(_consultas())
            ctx = asyncio.run(_caso_ttr())
    else:
        resultados = asyncio.run(_consultas())
        ctx = asyncio.run(_caso_ttr())

    out("=== ENTRADA → SALIDA por variante ===")
    for r in resultados:
        out(f"{r.gene} {r.variant:12s} → {r.status.value}")
        if r.classification:
            out(f"    {r.classification} | {r.review_status} | evaluada {r.last_evaluated}")
            out(f"    {r.accession} — {r.title}")
            out(f"    {r.url}")
        if r.candidates and not r.classification:
            out(f"    {r.candidates} registros devueltos; ninguno coincide con la notación y el gen")
        if r.detail and r.status.value == "no_disponible":
            out(f"    error: {r.detail}")

    out("\n=== Bloque que recibe el Agente 02 (caso con TTR c.148G>A) ===")
    out(ctx.to_prompt_block())
    out("\nFuentes: " + ", ".join(f"{s.name}={s.status.value}" for s in ctx.sources))

    SALIDA.mkdir(parents=True, exist_ok=True)
    sufijo = "_sin_red" if args.sin_red else ""
    (SALIDA / f"clinvar{sufijo}.json").write_text(json.dumps({
        "modo": modo,
        "consultas": [r.model_dump(mode="json") for r in resultados],
        "contexto_ttr": ctx.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (SALIDA / f"resumen{sufijo}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nArtefactos en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
