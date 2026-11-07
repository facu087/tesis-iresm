"""
Demo del cliente Orphadata (evidencia para Trello, tarjeta #74).

Consulta la **API real** (https://api.orphadata.com/rd-associated-genes). Nada
simulado: la mitad del valor de esta tarjeta era averiguar qué devuelve de
verdad, después de que dos clientes de este repo "funcionaran" parseando campos
inexistentes.

ENTRADA  un ORPHAcode
SALIDA   las asociaciones gen–enfermedad de Orphanet: símbolo, nombre, tipo de
         asociación (causal vs. modificadora), estado de validación, locus,
         PMID que la respalda y referencias externas (HGNC, OMIM, Ensembl)

Consultas:
  1. ORPHA:85447  ATTRV30M amyloidosis → 200, gen TTR (el caso de la tesis)
  2. ORPHA:586    Cystic fibrosis      → 200, 19 asociaciones: CFTR es la causa
                                         y el resto son modificadoras
  3. ORPHA:271861 Hereditary ATTR amyloidosis → 404 "Query not found": ese
                                         código no tiene asociación cargada
  4. ORPHA:64746  Charcot-Marie-Tooth 2 AD    → 404, es un grupo de enfermedades
  5. Delegación: OrphanetClient.get_genes() y enrich_with_genes(), que antes
     levantaban OrphanetGenesNoDisponibles, ahora traen el dato de verdad
  6. Manejo de error: una ruta inexistente del mismo host levanta
     ExternalApiError en vez de pasar por "sin resultados"

Uso:
    python3 scripts/demo_orphadata.py

Artefactos en output/demo_orphadata/: genes.json y resumen.txt.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.external.orphadata import OrphadataClient
from backend.external.orphanet import OrphanetClient, RareDisease
from backend.external.rate_limiter import ExternalApiError

SALIDA = RAIZ / "output" / "demo_orphadata"
SEP = "═" * 78

# (código, qué se espera y por qué) — los cuatro casos medidos el 2026-10-06.
CONSULTAS = [
    ("85447", "ATTRV30M amyloidosis — subtipo con gen causal (el caso de la tesis)"),
    ("586", "Cystic fibrosis — varias asociaciones: una causal y muchas modificadoras"),
    ("271861", "Hereditary ATTR amyloidosis — sin asociación cargada para este código"),
    ("64746", "Charcot-Marie-Tooth 2 AD — grupo de enfermedades, sin asociación"),
]


async def main() -> None:
    lineas: list[str] = [
        "NEXUS — Orphadata: genes asociados a enfermedades raras (API real)",
        "=" * 78,
        "Base URL: https://api.orphadata.com/rd-associated-genes",
        "Licencia de los datos: CC-BY-4.0 (Orphanet) — declarada en cada respuesta",
        "",
    ]
    salida: dict[str, object] = {}

    print(SEP)
    print("DEMO — Cliente Orphadata contra la API REAL (tarjeta #74)")
    print(SEP)
    print("\nLos genes NO están en la ORPHAcodes API (32 rutas, ninguna de genes):")
    print("están en Orphadata, otro producto y otro host.\n")

    async with OrphadataClient() as client:
        print(f"{'─' * 78}\n1. Entrada → salida, código por código\n{'─' * 78}")
        for codigo, por_que in CONSULTAS:
            print(f"\n  ENTRADA  ORPHA:{codigo}  ({por_que})")
            genes = await client.get_disease_genes(codigo)

            if genes is None:
                print("  SALIDA   None — 404 'Query not found': la ruta existe y ese")
                print("           ORPHAcode no tiene asociación génica cargada.")
                print("           NO significa 'no se conoce gen para esta enfermedad'.")
                lineas += [
                    f"ORPHA:{codigo} ({por_que})",
                    "  → sin asociación génica cargada (404 'Query not found')",
                    "",
                ]
                salida[codigo] = None
                continue

            print(f"  SALIDA   {genes.name} [{genes.typology} / {genes.disorder_group}]")
            print(f"           {len(genes.associations)} asociación/es — "
                  f"licencia {genes.licence}, actualizado {genes.date}")
            print(f"           genes: {', '.join(genes.gene_symbols)}")
            print(f"           causales: {', '.join(genes.causal_gene_symbols) or '(ninguno)'}")
            lineas += [
                f"ORPHA:{codigo} ({por_que})",
                f"  {genes.name} [{genes.typology} / {genes.disorder_group}]",
                f"  Licencia: {genes.licence} | Actualizado: {genes.date}",
                f"  URL: {genes.url}",
                f"  Genes ({len(genes.gene_symbols)}): {', '.join(genes.gene_symbols)}",
                f"  Causales: {', '.join(genes.causal_gene_symbols) or '(ninguno)'}",
            ]
            for asociacion in genes.associations[:6]:
                print(f"             • {asociacion.to_context_str()}")
                lineas.append(f"    • {asociacion.to_context_str()}")
                refs = asociacion.external_references
                if refs:
                    lineas.append(
                        "        refs: "
                        + ", ".join(f"{k}:{v}" for k, v in sorted(refs.items()))
                    )
            if len(genes.associations) > 6:
                print(f"             … y {len(genes.associations) - 6} más")
                lineas.append(f"    … y {len(genes.associations) - 6} más")
            lineas.append("")
            salida[codigo] = {
                "orpha_code": genes.orpha_code,
                "name": genes.name,
                "typology": genes.typology,
                "disorder_group": genes.disorder_group,
                "licence": genes.licence,
                "date": genes.date,
                "url": genes.url,
                "gene_symbols": genes.gene_symbols,
                "causal_gene_symbols": genes.causal_gene_symbols,
                "associations": [asdict(a) for a in genes.associations],
            }

        print(f"\n{'─' * 78}\n2. Resumen tal como lo vería un agente\n{'─' * 78}")
        attr = await client.get_disease_genes("85447")
        if attr is not None:
            print(attr.summary())
            lineas += ["RESUMEN PARA EL CONTEXTO DE UN AGENTE:", attr.summary(), ""]

        print(f"\n{'─' * 78}\n3. Manejo de error: 404 de ruteo ≠ sin resultados\n{'─' * 78}")
        print("  Mismo host, ruta que no existe: /orphacodes-inventado/85447")
        # Se llama a `_request` a propósito: ningún método público puede armar
        # una ruta inválida, y lo que se quiere mostrar es justamente que ese
        # 404 no se confunde con "esta enfermedad no tiene genes".
        try:
            await client._request("/orphacodes-inventado/85447")
        except ExternalApiError as exc:
            print(f"  ExternalApiError → {exc}")
            lineas += ["MANEJO DE ERROR (404 de ruteo, no 'Query not found'):",
                       f"  ExternalApiError → {exc}", ""]
        else:
            print("  ¡No levantó! Revisar la discriminación de los dos 404.")

        print("\n  Código no numérico: no llega a la red (la ruta espera un entero)")
        try:
            await client.get_disease_genes("ORPHA:85447")
        except ValueError as exc:
            print(f"  ValueError → {exc}")
            lineas += [f"MANEJO DE ERROR (código inválido): ValueError → {exc}", ""]

    print(f"\n{'─' * 78}\n4. OrphanetClient ahora delega: get_genes() funciona\n{'─' * 78}")
    print("  Antes levantaba OrphanetGenesNoDisponibles; ahora trae el dato real.\n")
    async with OrphanetClient() as orphanet:
        simbolos = await orphanet.get_genes("85447")
        print(f"  get_genes('85447') → {simbolos}")
        enfermedad = RareDisease(
            orpha_code="85447", name="ATTRV30M amyloidosis", definition="",
        )
        await orphanet.enrich_with_genes(enfermedad)
        print(f"  enrich_with_genes(...) → genes={enfermedad.genes}")
        print(f"  summary() → {enfermedad.summary()}")
        lineas += [
            "DELEGACIÓN DESDE OrphanetClient:",
            f"  get_genes('85447') → {simbolos}",
            f"  enrich_with_genes → genes={enfermedad.genes}",
            f"  summary → {enfermedad.summary()}",
            "",
        ]
        salida["_delegacion_orphanet"] = {
            "get_genes_85447": simbolos,
            "enrich_with_genes": asdict(enfermedad),
        }

    SALIDA.mkdir(parents=True, exist_ok=True)
    txt = SALIDA / "resumen.txt"
    txt.write_text("\n".join(lineas), encoding="utf-8")
    js = SALIDA / "genes.json"
    js.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{SEP}")
    print("Artefactos:")
    print(f"  • {txt}")
    print(f"  • {js}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
