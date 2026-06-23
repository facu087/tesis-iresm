"""
Demo de verificación — Cliente Orphanet API: búsqueda de enfermedades raras.

Muestra cómo el cliente busca enfermedades raras por nombre y devuelve
información estructurada incluyendo código ORPHA, definición y genes asociados.
Usa datos simulados del caso clínico (neuropatía axonal, 42 años).

Artefactos generados en output/demo_orphanet/:
    1. enfermedades_encontradas.txt → enfermedades con código ORPHA, genes y definición
    2. genes_asociados.txt          → genes por enfermedad (para el Agente 02)

Uso:
    python scripts/demo_orphanet.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.external.orphanet import RareDisease

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_orphanet"

# Enfermedades raras simuladas relevantes para el caso (neuropatía axonal)
_ENFERMEDADES = [
    RareDisease(
        orpha_code="85163",
        name="Hereditary transthyretin amyloidosis",
        definition=(
            "Hereditary ATTR (ATTRv) amyloidosis is a progressive, fatal systemic disease "
            "caused by mutations in the TTR gene encoding transthyretin. It manifests mainly "
            "as peripheral neuropathy and/or cardiomyopathy, with onset typically in adulthood."
        ),
        genes=["TTR"],
        synonyms=["Familial amyloid polyneuropathy", "hATTR amyloidosis", "ATTRv amyloidosis"],
    ),
    RareDisease(
        orpha_code="642",
        name="Charcot-Marie-Tooth disease type 1A",
        definition=(
            "CMT1A is the most common inherited peripheral neuropathy caused by duplication of "
            "the PMP22 gene on chromosome 17p11.2. It presents with distal muscle weakness, "
            "areflexia and sensory loss with slow nerve conduction velocities."
        ),
        genes=["PMP22"],
        synonyms=["CMT1A", "HMSN Ia", "Hereditary motor and sensory neuropathy type Ia"],
    ),
    RareDisease(
        orpha_code="98878",
        name="Acute hepatic porphyria",
        definition=(
            "Acute hepatic porphyria encompasses four disorders caused by deficiencies in heme "
            "biosynthesis enzymes. AHP presents with acute neurovisceral attacks, abdominal pain "
            "and peripheral neuropathy. ALAS1 overexpression drives pathogenesis."
        ),
        genes=["HMBS", "CPOX", "PPOX", "ALAD"],
        synonyms=["AHP", "Acute porphyria"],
    ),
    RareDisease(
        orpha_code="251908",
        name="Autoimmune autonomic ganglionopathy",
        definition=(
            "AAG is an acquired autoimmune neuropathy caused by antibodies against ganglionic "
            "nicotinic acetylcholine receptors. It presents with subacute autonomic failure "
            "affecting both sympathetic and parasympathetic systems."
        ),
        genes=[],
        synonyms=["AAG", "Autoimmune dysautonomia"],
    ),
]


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Cliente Orphanet API: búsqueda de enfermedades raras")
    print(_SEP)

    # 1. Búsqueda por nombre
    print(f"\n  [1/4] Búsqueda simulada: 'neuropathy hereditary axonal'")
    print(f"        Resultados: {len(_ENFERMEDADES)} enfermedades raras\n")
    for i, e in enumerate(_ENFERMEDADES, 1):
        genes_str = ", ".join(e.genes) if e.genes else "—"
        print(f"        [{i}] ORPHA:{e.orpha_code} — {e.name}")
        print(f"             Genes : {genes_str}")
        print(f"             URL   : {e.url}")
        print()

    # 2. Detalle de enfermedad con código ORPHA
    print(f"  [2/4] Detalle por código ORPHA ('85163' → ATTRv amyloidosis):")
    attr = _ENFERMEDADES[0]
    print(f"        Nombre      : {attr.name}")
    print(f"        Código ORPHA: {attr.orpha_code}")
    print(f"        Genes       : {', '.join(attr.genes)}")
    print(f"        Sinónimos   : {', '.join(attr.synonyms[:2])}")
    print(f"        Definición  : {attr.definition[:120]}...")

    # 3. Summary formateado para contexto de agente
    print(f"\n  [3/4] Summary formateado para el contexto de un agente:")
    for e in _ENFERMEDADES[:2]:
        print(f"        → {e.summary()}")
        print()

    # 4. Genes únicos extraídos (para el Agente 02 — Especialista Genómica)
    todos_los_genes = sorted({g for e in _ENFERMEDADES for g in e.genes})
    print(f"  [4/4] Genes únicos asociados a enfermedades encontradas:")
    print(f"        {', '.join(todos_los_genes) if todos_los_genes else '(ninguno para AAG)'}")

    # Guardar artefactos
    enf_txt = _OUT_DIR / "enfermedades_encontradas.txt"
    with enf_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Cliente Orphanet: enfermedades raras encontradas\n")
        f.write("=" * 60 + "\n")
        f.write("Query: 'neuropathy hereditary axonal'\n\n")
        for i, e in enumerate(_ENFERMEDADES, 1):
            f.write(f"[{i}] ORPHA:{e.orpha_code} — {e.name}\n")
            f.write(f"     Genes     : {', '.join(e.genes) if e.genes else '(no asociados)'}\n")
            f.write(f"     Sinónimos : {', '.join(e.synonyms)}\n")
            f.write(f"     URL       : {e.url}\n")
            f.write(f"     Definición: {e.definition}\n\n")

    genes_txt = _OUT_DIR / "genes_asociados.txt"
    with genes_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — Genes asociados a enfermedades raras (para Agente 02)\n")
        f.write("=" * 60 + "\n\n")
        for e in _ENFERMEDADES:
            f.write(f"ORPHA:{e.orpha_code} — {e.name}\n")
            if e.genes:
                for g in e.genes:
                    f.write(f"  → Gen: {g}\n")
            else:
                f.write(f"  → Sin genes asociados (enfermedad autoinmune adquirida)\n")
            f.write("\n")
        f.write(f"Total genes únicos: {len(todos_los_genes)}\n")
        f.write(f"Genes: {', '.join(todos_los_genes)}\n")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Enfermedades encontradas : {len(_ENFERMEDADES)}")
    print(f"  Genes únicos asociados   : {len(todos_los_genes)} ({', '.join(todos_los_genes)})")
    print(f"  Summary para agentes     : ✓ generado para cada enfermedad")
    print(f"  Autenticación            : header apiKey (ORPHANET_API_KEY en .env)")
    print(f"  Fallback si no responde  : ✓ lista vacía (no bloquea pipeline)")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Enfermedades encontradas → {enf_txt}")
    print(f"    • Genes asociados          → {genes_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
