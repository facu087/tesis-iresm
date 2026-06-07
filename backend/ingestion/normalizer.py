"""
Normalización terminológica de texto clínico.
- Nombres INN: reemplaza marcas comerciales por el nombre genérico internacional.
- Unidades de medida: estandariza variantes ortográficas a la forma canónica.
"""

import re

# ── Diccionario INN ────────────────────────────────────────────────────────────
# Formato: "Marca / variante" → "inn_canonical"
# Cubre las familias más frecuentes en neurología e internación clínica.
# Cada entrada incluye la marca en mayúscula, minúscula y capitalizada
# para que el regex (case-insensitive) las capture todas.

_INN_MAP: dict[str, str] = {
    # Antiinflamatorios / analgésicos
    "advil": "ibuprofeno",
    "ibupirac": "ibuprofeno",
    "panadol": "paracetamol",
    "tafirol": "paracetamol",
    "tempra": "paracetamol",
    "acetaminophen": "paracetamol",
    "acetaminofén": "paracetamol",
    "voltaren": "diclofenaco",
    "cataflam": "diclofenaco",
    "arcoxia": "etoricoxib",
    "celebrex": "celecoxib",
    "aspirina": "ácido acetilsalicílico",
    "aspirin": "ácido acetilsalicílico",
    "flanax": "naproxeno",
    "apronax": "naproxeno",
    # Neuropático / anticonvulsivante
    "lyrica": "pregabalina",
    "neurontin": "gabapentina",
    "topamax": "topiramato",
    "tegretol": "carbamazepina",
    "carbatrol": "carbamazepina",
    "depakote": "valproato",
    "depakene": "valproato",
    "epival": "valproato",
    "lamictal": "lamotrigina",
    "keppra": "levetiracetam",
    "vimpat": "lacosamida",
    "trileptal": "oxcarbazepina",
    "dilantin": "fenitoína",
    "phenytek": "fenitoína",
    # Antidepresivos / dolor neuropático
    "cymbalta": "duloxetina",
    "effexor": "venlafaxina",
    "elavil": "amitriptilina",
    "tryptanol": "amitriptilina",
    "prozac": "fluoxetina",
    "zoloft": "sertralina",
    "paxil": "paroxetina",
    "lexapro": "escitalopram",
    "celexa": "citalopram",
    "wellbutrin": "bupropión",
    "zyban": "bupropión",
    "remeron": "mirtazapina",
    # Corticoides
    "medrol": "metilprednisolona",
    "depo-medrol": "metilprednisolona",
    "solu-medrol": "metilprednisolona",
    "decadron": "dexametasona",
    "oradexon": "dexametasona",
    # Inmunosupresores
    "cellcept": "micofenolato",
    "imuran": "azatioprina",
    "prograf": "tacrolimus",
    "sandimmun": "ciclosporina",
    "neoral": "ciclosporina",
    "rituxan": "rituximab",
    "mabthera": "rituximab",
    # Vitaminas / suplementos
    "vitamina b12": "cianocobalamina",
    "vitamin b12": "cianocobalamina",
    "vitamina d": "colecalciferol",
    "vitamin d": "colecalciferol",
    # Cardiovascular / autonómico
    "norvasc": "amlodipina",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "tenormin": "atenolol",
    "inderal": "propranolol",
    "midodrine": "midodrina",
    "florinef": "fludrocortisona",
    # Relajantes musculares
    "flexeril": "ciclobenzaprina",
    "lioresal": "baclofeno",
    # Opioides
    "duragesic": "fentanilo",
    "oxycontin": "oxicodona",
    "percocet": "oxicodona",
    "vicodin": "hidrocodona",
    "ultram": "tramadol",
    # Anticoagulantes
    "coumadin": "warfarina",
    "sintrom": "acenocumarol",
    "xarelto": "rivaroxabán",
    "eliquis": "apixabán",
    "pradaxa": "dabigatrán",
    # Gastrointestinal
    "nexium": "esomeprazol",
    "losec": "omeprazol",
    "prilosec": "omeprazol",
    "zantac": "ranitidina",
    "motilium": "domperidona",
}

# ── Unidades de medida ─────────────────────────────────────────────────────────
# Formato: patrón regex → forma canónica
# El orden importa: primero los más específicos.

_UNIT_RULES: list[tuple[str, str]] = [
    # Glucosa / lípidos
    (r"mg\s*/\s*dl\b", "mg/dL"),
    (r"MG\s*/\s*DL\b", "mg/dL"),
    (r"mg\s*/\s*dL\b", "mg/dL"),
    # Hemoglobina / proteínas
    (r"g\s*/\s*dl\b", "g/dL"),
    (r"G\s*/\s*DL\b", "g/dL"),
    (r"g\s*/\s*dL\b", "g/dL"),
    # Presión arterial
    (r"mm\s*hg\b", "mmHg"),
    (r"mmHG\b", "mmHg"),
    (r"MM\s*HG\b", "mmHg"),
    (r"mm\s*Hg\b", "mmHg"),
    # Microgramos
    (r"\bmcg\b", "μg"),
    (r"\bug\b", "μg"),
    (r"\bµg\b", "μg"),          # µ (U+00B5) → μ (U+03BC)
    (r"mcg\s*/\s*ml\b", "μg/mL"),
    (r"mcg\s*/\s*mL\b", "μg/mL"),
    (r"ug\s*/\s*ml\b", "μg/mL"),
    (r"ug\s*/\s*mL\b", "μg/mL"),
    # Miliequivalentes
    (r"meq\s*/\s*l\b", "mEq/L"),
    (r"mEq\s*/\s*l\b", "mEq/L"),
    (r"MEQ\s*/\s*L\b", "mEq/L"),
    # Miliunidades internacionales
    (r"\bmUI\b", "mUI/L"),
    (r"\bmuI\b", "mUI/L"),
    (r"miu\s*/\s*ml\b", "mUI/mL"),
    (r"mIU\s*/\s*mL?\b", "mUI/mL"),
    # Unidades internacionales
    (r"\bUI\s*/\s*ml\b", "UI/mL"),
    (r"\bIU\s*/\s*mL?\b", "UI/mL"),
    (r"\bIU\b", "UI"),
    # ng, pg
    (r"ng\s*/\s*ml\b", "ng/mL"),
    (r"ng\s*/\s*mL\b", "ng/mL"),
    (r"pg\s*/\s*ml\b", "pg/mL"),
    (r"pg\s*/\s*mL\b", "pg/mL"),
    # Velocidad de sedimentación / frecuencia
    (r"\bmm/h\b", "mm/h"),
    (r"\bmm/hr\b", "mm/h"),
    # Temperatura
    (r"°\s*c\b", "°C"),
    (r"°\s*f\b", "°F"),
    (r"\bdeg\s*c\b", "°C"),
]

# Compilar patrones una sola vez al importar el módulo
_COMPILED_UNITS: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in _UNIT_RULES
]

# Compilar INN: patrón de palabra completa, case-insensitive
_COMPILED_INN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b" + re.escape(brand) + r"\b", re.IGNORECASE), inn)
    for brand, inn in _INN_MAP.items()
]


def normalize_units(text: str) -> str:
    """Estandariza variantes de unidades de medida a su forma canónica."""
    for pattern, replacement in _COMPILED_UNITS:
        text = pattern.sub(replacement, text)
    return text


def normalize_inn(text: str) -> str:
    """Reemplaza nombres comerciales de medicamentos por su INN genérico."""
    for pattern, inn in _COMPILED_INN:
        text = pattern.sub(inn, text)
    return text


def normalize(text: str) -> str:
    """
    Aplica normalización completa sobre texto clínico extraído:
    primero unidades, luego INN.
    Devuelve el texto normalizado listo para ser procesado por los agentes.
    """
    text = normalize_units(text)
    text = normalize_inn(text)
    return text
