"""
Demo de verificación — Normalización terminológica (nombres INN + unidades).

Muestra un texto clínico ANTES y DESPUÉS de la normalización, y una tabla con
cada transformación aplicada:
    • Marcas comerciales → nombre genérico internacional (INN)
    • Variantes de unidades → forma canónica

Guarda en disco artefactos tangibles para Trello:
    1. Texto original     → output/demo_normalizacion/texto_original.txt
    2. Texto normalizado  → output/demo_normalizacion/texto_normalizado.txt

Uso:
    python scripts/demo_normalizacion.py
"""

import sys
from pathlib import Path

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.normalizer import normalize

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_normalizacion"

# Texto clínico con marcas comerciales y unidades en formato inconsistente
# (tal como aparecerían en una historia clínica real o tras un OCR).
_ORIGINAL = """\
Paciente medicado con Lyrica 150 mg/dia, Neurontin y Cymbalta.
Antecedente de toma crónica de Aspirina y Coumadin.
Laboratorio: glucemia 180 mg/dl, hemoglobina 9 g/dl.
Presion arterial 140/90 mmhg. Sodio 138 meq/l.
Vitamina B12 disminuida. Fludrocortisona 50 mcg por dia."""

# Transformaciones que este caso demuestra: (tipo, antes, después).
# Se verifican contra la salida REAL de normalize() — no están hardcodeadas.
_SHOWCASE = [
    ("INN",     "Lyrica",      "pregabalina"),
    ("INN",     "Neurontin",   "gabapentina"),
    ("INN",     "Cymbalta",    "duloxetina"),
    ("INN",     "Aspirina",    "ácido acetilsalicílico"),
    ("INN",     "Coumadin",    "warfarina"),
    ("INN",     "Vitamina B12", "cianocobalamina"),
    ("Unidad",  "mg/dl",       "mg/dL"),
    ("Unidad",  "g/dl",        "g/dL"),
    ("Unidad",  "mmhg",        "mmHg"),
    ("Unidad",  "meq/l",       "mEq/L"),
    ("Unidad",  "mcg",         "μg"),
]


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    normalizado = normalize(_ORIGINAL)

    # Guarda artefactos tangibles
    (_OUT_DIR / "texto_original.txt").write_text(_ORIGINAL, encoding="utf-8")
    (_OUT_DIR / "texto_normalizado.txt").write_text(normalizado, encoding="utf-8")

    print(_SEP)
    print("  DEMO — Normalización terminológica (nombres INN + unidades)")
    print(_SEP)
    print("  TEXTO ORIGINAL (como llega de la historia clínica / OCR):")
    print(_SEP)
    print(_ORIGINAL)
    print(_SEP)
    print("  TEXTO NORMALIZADO (listo para los agentes):")
    print(_SEP)
    print(normalizado)
    print(_SEP)

    # Tabla de transformaciones, verificada contra la salida real
    print("  TRANSFORMACIONES APLICADAS:")
    print(_SEP)
    print(f"  {'TIPO':<8} {'ANTES':<16} →  DESPUÉS")
    print(f"  {'-'*8} {'-'*16}    {'-'*22}")
    ok = 0
    for tipo, antes, despues in _SHOWCASE:
        # Verificación honesta: la variante estaba en el original y la forma
        # canónica (con su casing exacto) aparece en la salida real.
        estaba_en_original = antes.lower() in _ORIGINAL.lower()
        quedo_canonico = despues in normalizado
        aplicado = estaba_en_original and quedo_canonico
        marca = "✓" if aplicado else "·"
        if aplicado:
            ok += 1
        print(f"  {tipo:<8} {antes:<16} →  {despues}  {marca}")
    print(_SEP)
    print(f"  ✓ {ok}/{len(_SHOWCASE)} transformaciones verificadas contra la salida real.")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Texto original     → {_OUT_DIR / 'texto_original.txt'}")
    print(f"    • Texto normalizado  → {_OUT_DIR / 'texto_normalizado.txt'}")
    print(_SEP)


if __name__ == "__main__":
    main()
