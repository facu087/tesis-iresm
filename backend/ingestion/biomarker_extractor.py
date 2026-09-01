"""
Extracción de biomarcadores y mapeo del historial terapéutico.

Identifica entidades clínicas relevantes en texto médico:
- Genes y variantes genéticas
- Proteínas, anticuerpos y enzimas
- Biomarcadores de laboratorio
- Historial terapéutico completo (fármacos + procedimientos)

Usa dos estrategias combinadas:
1. Regex/diccionario: captura entidades conocidas de forma rápida y determinista
2. LLM (Groq): captura entidades no previstas en el diccionario
"""

import json
import os
import re

from groq import Groq

from ..agents.base_agent import GROQ_MAIN
from ..models.biomarkers import BiomarkerProfile

# ── Patrones de reconocimiento rápido ────────────────────────────────────────

# Genes: mayúsculas, 2-10 chars, opcionalmente seguidos de número
_GENE_PATTERN = re.compile(
    r'\b(?:'
    r'[A-Z]{2,6}\d{0,2}'           # Ej: KCNQ2, TTR, ATM
    r'|[A-Z]{1}[A-Z0-9]{1,8}B\d?' # Ej: NDRG1, PMP22
    r')\b'
)

# Siglas clínicas que NO son genes
_NON_GENE_TERMS = {
    "LCR", "EMG", "TAC", "RMN", "MRI", "PCR", "EEG", "ECG", "EKG",
    "VCN", "PET", "SPECT", "RX", "UCI", "UTI", "ACV", "TEC",
    "INN", "OMS", "WHO", "FDA", "EMA", "NCCN", "ESMO",
}

# Anticuerpos anti-X. El separador (guion o espacio) es OBLIGATORIO para no
# capturar la palabra española "anticuerpos" (anti + cuerpos) ni términos como
# "antiinflamatorio", que no llevan separador.
_ANTIBODY_PATTERN = re.compile(
    r'\banti[-\s][A-Za-záéíóúÁÉÍÓÚñÑ0-9\-]{2,20}\b',
    re.IGNORECASE
)

# Términos que empiezan con "anti" pero NO son anticuerpos (se comparan sin
# guiones ni espacios). Filtran falsos positivos del patrón anterior.
_NON_ANTIBODY_ANTI = {
    "anticuerpos", "anticuerpo", "antiinflamatorio", "antiinflamatorios",
    "anticoagulante", "anticoagulantes", "antiagregante", "antiagregantes",
    "antibiotico", "antibioticos", "antidepresivo", "antidepresivos",
    "antihipertensivo", "antiviral", "antivirales", "antialergico",
}

# Variantes genéticas tipo p.Val30Met o c.148G>A
_VARIANT_PATTERN = re.compile(
    r'\b(?:p\.|c\.)[A-Za-z0-9>_*+\-]{4,20}\b'
)

# Genes conocidos en neuropatías y enfermedades raras (complementa regex)
_KNOWN_GENES = {
    "CMT", "PMP22", "MPZ", "GJB1", "MFN2", "GDAP1", "NEFL", "LITAF",
    "EGR2", "PRPS1", "SH3TC2", "NDRG1", "FIG4", "MTMR2", "SETX",
    "TTR", "FAP", "ATTR", "TRPV4", "GARS", "YARS", "AARS",
    "ATM", "BRCA1", "BRCA2", "TP53", "PTEN", "VHL", "RET",
    "KCNA1", "KCNQ2", "SCN1A", "SCN9A", "HBA1", "HBA2", "HBB",
    "HMBS", "ALAD", "CPOX", "PPOX", "FECH", "UROS", "UROD",
    "FXN", "SMN1", "SMN2", "ATN1", "ATXN1", "ATXN2", "ATXN3",
    "WNK1", "WNK4", "DYNC1H1", "DCTN1",
}

# Biomarcadores de laboratorio comunes
_LAB_MARKERS = {
    "hba1c", "hemoglobina glicosilada", "vitamina b12", "folato",
    "tsh", "t3", "t4", "aca", "enas", "ana", "anca",
    "crioglobulinas", "proteína m", "cadenas ligeras",
    "proteinuria", "creatinina", "urea", "clearance",
    "aldolasa", "cpk", "ck", "ldh", "ferritina",
    "ceruloplasmina", "cobre", "zinc", "arsénico", "plomo",
    "porfirinas", "ácido metilmalónico", "homocisteína",
    "anticuerpos anti-gangliósido", "gm1", "gm2", "gq1b", "gd1a",
}

SYSTEM_PROMPT_LLM = """Sos un especialista en medicina interna y neurología.
Analizá el texto clínico y extraé TODAS las entidades biomédicas mencionadas.

Respondé ÚNICAMENTE con JSON válido con esta estructura:

{
  "genes": ["gen1", "gen2"],
  "antibodies": ["anti-Hu", "anti-Yo"],
  "lab_biomarkers": ["vitamina B12", "HbA1c"],
  "genetic_variants": ["p.Val30Met"],
  "pathways": ["neuropatía CMT", "porfiria aguda"],
  "therapeutic_history": {
    "drugs": ["pregabalina", "metilprednisolona"],
    "procedures": ["electromiograma", "biopsia de nervio"],
    "surgeries": []
  }
}

REGLAS:
- Incluí SOLO lo que está explícitamente en el texto.
- Si un campo no tiene información, dejá la lista vacía [].
- Normalizá nombres a su forma canónica (INN para fármacos).
- En "pathways" incluí los diagnósticos o síndromes mencionados o descartados."""


def _extract_with_regex(text: str) -> dict:
    """Extracción rápida y determinista con patrones predefinidos."""
    genes_found = set()

    # Genes por regex
    for match in _GENE_PATTERN.finditer(text):
        candidate = match.group()
        if candidate not in _NON_GENE_TERMS and len(candidate) >= 2:
            genes_found.add(candidate)

    # Genes conocidos en el texto
    words = set(re.findall(r'\b[A-Z]{2,}\d*\b', text))
    genes_found.update(words & _KNOWN_GENES)

    # Anticuerpos (excluye términos "anti…" que no son anticuerpos)
    antibodies = list({
        m.group() for m in _ANTIBODY_PATTERN.finditer(text)
        if m.group().lower().replace("-", "").replace(" ", "") not in _NON_ANTIBODY_ANTI
    })

    # Variantes
    variants = list({m.group() for m in _VARIANT_PATTERN.finditer(text)})

    # Biomarcadores de lab por diccionario. Se busca por palabra completa (\b)
    # y no por subcadena, para que "ana" no matchee dentro de "analizados", etc.
    text_lower = text.lower()
    lab_markers = [
        marker for marker in _LAB_MARKERS
        if re.search(r"\b" + re.escape(marker) + r"\b", text_lower)
    ]

    return {
        "genes_regex": sorted(genes_found),
        "antibodies_regex": antibodies,
        "variants_regex": variants,
        "lab_markers_regex": lab_markers,
    }


def _extract_with_llm(text: str) -> dict:
    """Extracción semántica con LLM para capturar entidades no previstas."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model=GROQ_MAIN,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_LLM},
            {"role": "user", "content": f"Extraé las entidades biomédicas del siguiente texto clínico:\n\n{text}"},
        ],
        max_tokens=1024,
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()

    # Limpiar markdown fences si los hay
    if raw.startswith("```"):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```\s*$', '', raw.strip())

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}


def _merge_results(regex_results: dict, llm_results: dict) -> BiomarkerProfile:
    """Fusiona los resultados de regex y LLM eliminando duplicados."""

    def merge_lists(*lists) -> list[str]:
        seen = set()
        result = []
        for lst in lists:
            for item in (lst or []):
                key = item.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    result.append(item.strip())
        return result

    therapeutic = llm_results.get("therapeutic_history", {})

    return BiomarkerProfile(
        genes=merge_lists(
            regex_results.get("genes_regex", []),
            llm_results.get("genes", [])
        ),
        antibodies=merge_lists(
            regex_results.get("antibodies_regex", []),
            llm_results.get("antibodies", [])
        ),
        lab_biomarkers=merge_lists(
            regex_results.get("lab_markers_regex", []),
            llm_results.get("lab_biomarkers", [])
        ),
        genetic_variants=merge_lists(
            regex_results.get("variants_regex", []),
            llm_results.get("genetic_variants", [])
        ),
        pathways=llm_results.get("pathways", []),
        drugs=therapeutic.get("drugs", []),
        procedures=therapeutic.get("procedures", []),
        surgeries=therapeutic.get("surgeries", []),
    )


def extract(clinical_text: str) -> "BiomarkerProfile":
    """
    Extrae biomarcadores e historial terapéutico del texto clínico.
    Combina regex (rápido, determinista) + LLM (semántico, cubre casos no previstos).
    """
    regex_results = _extract_with_regex(clinical_text)
    llm_results = _extract_with_llm(clinical_text)
    return _merge_results(regex_results, llm_results)
