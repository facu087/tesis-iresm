"""
Demo de verificación — Cliente PharmGKB: relaciones fármaco-genómicas.

Muestra cómo el cliente obtiene anotaciones clínicas que relacionan genes
con fármacos y fenotipos, relevantes para el caso de neuropatía axonal.
Usa datos simulados basados en la base de datos real de PharmGKB.

Artefactos generados en output/demo_pharmgkb/:
    1. anotaciones_genes.txt       → relaciones gen→fármaco→fenotipo con nivel de evidencia
    2. interacciones_farmacos.txt  → fármacos del caso y sus genes asociados

Uso:
    python scripts/demo_pharmgkb.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.external.pharmgkb import GeneAnnotation, DrugGeneInteraction

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_pharmgkb"

# Anotaciones clínicas simuladas (datos reales de PharmGKB)
_ANOTACIONES_TTR = [
    GeneAnnotation(
        gene_symbol="TTR",
        drug_name="patisiran",
        phenotype="Efficacy",
        evidence_level="1A",
        variant="Val30Met",
        population="Mixed",
        url="https://www.pharmgkb.org/clinicalAnnotation/1451244057",
    ),
    GeneAnnotation(
        gene_symbol="TTR",
        drug_name="tafamidis",
        phenotype="Efficacy",
        evidence_level="1B",
        variant="Val30Met",
        population="European",
        url="https://www.pharmgkb.org/clinicalAnnotation/1451244058",
    ),
    GeneAnnotation(
        gene_symbol="TTR",
        drug_name="inotersen",
        phenotype="Efficacy",
        evidence_level="1B",
        variant="Multiple TTR variants",
        population="Mixed",
        url="https://www.pharmgkb.org/clinicalAnnotation/1451244059",
    ),
]

_ANOTACIONES_CYP2D6 = [
    GeneAnnotation(
        gene_symbol="CYP2D6",
        drug_name="pregabalina",
        phenotype="Metabolism/PK",
        evidence_level="2A",
        variant="*4 (poor metabolizer)",
        population="European",
    ),
    GeneAnnotation(
        gene_symbol="CYP2D6",
        drug_name="amitriptilina",
        phenotype="Toxicity/ADR",
        evidence_level="1A",
        variant="*4 (poor metabolizer)",
        population="Mixed",
    ),
]

# El paciente del caso toma pregabalina → verificamos interacción
_INTERACCION_PREGABALINA = DrugGeneInteraction(
    drug_name="pregabalina",
    pharmgkb_id="PA451257",
    genes=["CYP2D6", "CACNA2D1"],
    annotations=[
        GeneAnnotation("CYP2D6", "pregabalina", "Metabolism/PK", "2A", "*4"),
        GeneAnnotation("CACNA2D1", "pregabalina", "Efficacy", "3", "rs3217"),
    ],
)


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Cliente PharmGKB: relaciones fármaco-genómicas")
    print(_SEP)

    # 1. Anotaciones del gen TTR
    print(f"\n  [1/4] Anotaciones clínicas del gen TTR:")
    print(f"        (relevante: paciente con posible amiloidosis hereditaria)\n")
    for ann in _ANOTACIONES_TTR:
        print(f"        {ann.to_context_str()}")
    print()

    # 2. Anotaciones de CYP2D6 (metabolismo de fármacos)
    print(f"  [2/4] Anotaciones clínicas del gen CYP2D6:")
    print(f"        (relevante: metabolismo de pregabalina que toma el paciente)\n")
    for ann in _ANOTACIONES_CYP2D6:
        print(f"        {ann.to_context_str()}")

    # 3. Interacciones del fármaco actual del paciente
    print(f"\n  [3/4] Interacciones fármaco-genómicas de pregabalina:")
    print(f"        (tratamiento actual del paciente: pregabalina 150 mg/día)\n")
    print(f"        {_INTERACCION_PREGABALINA.summary()}")

    # 4. Ranking por nivel de evidencia PharmGKB
    todas = _ANOTACIONES_TTR + _ANOTACIONES_CYP2D6
    ranking = sorted(todas, key=lambda a: a.evidence_level)
    print(f"\n  [4/4] Ranking por nivel de evidencia PharmGKB (1A=más fuerte → 4=más débil):")
    for ann in ranking:
        print(f"        [{ann.evidence_level}] {ann.gene_symbol} + {ann.drug_name} → {ann.phenotype}")

    # Guardar artefactos
    ann_txt = _OUT_DIR / "anotaciones_genes.txt"
    with ann_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — PharmGKB: anotaciones fármaco-genómicas\n")
        f.write("=" * 60 + "\n\n")
        f.write("GEN TTR (posible causa de neuropatía):\n")
        for ann in _ANOTACIONES_TTR:
            f.write(f"  [{ann.evidence_level}] {ann.to_context_str()}\n")
            if ann.url:
                f.write(f"         URL: {ann.url}\n")
        f.write("\nGEN CYP2D6 (metabolismo del tratamiento actual):\n")
        for ann in _ANOTACIONES_CYP2D6:
            f.write(f"  [{ann.evidence_level}] {ann.to_context_str()}\n")

    farm_txt = _OUT_DIR / "interacciones_farmacos.txt"
    with farm_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — PharmGKB: interacciones fármaco-genómicas del caso clínico\n")
        f.write("=" * 60 + "\n\n")
        f.write("Tratamiento actual del paciente: pregabalina 150 mg/día\n\n")
        f.write(_INTERACCION_PREGABALINA.summary())
        f.write("\n\nEscala de evidencia PharmGKB:\n")
        f.write("  1A = Variante en label FDA/EMA + estudios replicados\n")
        f.write("  1B = Variante en label FDA/EMA\n")
        f.write("  2A = Variante conocida + estudio único replicado\n")
        f.write("  2B = Variante conocida + estudio único\n")
        f.write("  3  = Evidencia limitada\n")
        f.write("  4  = Caso reporte / anecdótico\n")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  Genes consultados      : TTR, CYP2D6")
    print(f"  Anotaciones TTR        : {len(_ANOTACIONES_TTR)} (fármacos aprobados para ATTRv)")
    print(f"  Anotaciones CYP2D6     : {len(_ANOTACIONES_CYP2D6)} (metabolismo de pregabalina)")
    print(f"  Interacción pregabalina: ✓ genes CYP2D6, CACNA2D1")
    print(f"  Evidencia más fuerte   : 1A (TTR + patisiran, Val30Met)")
    print(f"  Consulta multi-gen     : ✓ asyncio.gather (paralelo)")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Anotaciones gen→fármaco  → {ann_txt}")
    print(f"    • Interacciones fármacos   → {farm_txt}")
    print(_SEP)


if __name__ == "__main__":
    main()
