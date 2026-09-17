"""
Demo de verificación — Agente 02: Especialista Genómica.

Muestra entrada → salida para dos escenarios:

  A) Caso base (neuropatía axonal, panel CMT negativo):
     - CMT descartado como gen, modo orientación activo
     - PharmGKB no_consultada (sin genes para enriquecer)
     - Bloque enviado al agente + hipótesis orientativas

  B) Caso sintético con TTR p.Val30Met (amiloidosis hereditaria):
     - PharmGKB consultada para TTR
     - Anotaciones farmacogenómicas disponibles
     - Bloque con variante + hipótesis con guarda inactiva

Si Groq no tiene cupo, muestra igual el perfil y el bloque y avisa,
como demo_agente03.py.

Guarda en output/demo_agente02/:
  contexto_caso_base.json
  hipotesis_caso_base.json
  contexto_ttr.json
  hipotesis_ttr.json

Uso:
  python3 scripts/demo_agente02.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncio

from backend.agents.agent_02_genomics import GenomicsSpecialistAgent
from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.pipeline import genomic_context as gc_module
from backend.pipeline import pico

OUTPUT_DIR = Path("output") / "demo_agente02"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEP = "─" * 72

# ── Casos clínicos ────────────────────────────────────────────────────────────

TEXTO_BASE = """
Paciente masculino de 42 años. Consulta por debilidad progresiva distal en
miembros inferiores de 4 años de evolución, con parestesias en guante y bota.
EMG: patrón axonal sensitivomotor bilateral. Velocidad de conducción normal
(descarta desmielinizante). Panel CMT (PMP22, MFN2, GJB1, MPZ): negativo.
No antecedentes familiares de neuropatía. Sin tratamiento modificador previo.
Objetivo: determinar etiología y orientar diagnóstico etiológico.
""".strip()

TEXTO_TTR = """
Paciente masculino de 67 años. Polineuropatía axonal sensitivomotora bilateral
de 3 años de evolución, asociada a insuficiencia cardíaca congestiva de causa
no filiada y síndrome del túnel carpiano bilateral operado hace 2 años.
Estudio genético: variante TTR p.Val30Met (c.148G>A) heterocigota, patogénica
según ClinVar. Padre fallecido con cuadro similar a los 72 años. Biopsia
nerviosa: depósito amiloide con rojo Congo positivo. Sin tratamiento para TTR.
Objetivo: confirmar amiloidosis ATTR hereditaria y evaluar tratamiento.
""".strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _guardar(nombre: str, datos: dict) -> None:
    path = OUTPUT_DIR / nombre
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {path}")


def _hipotesis_a_dict(h) -> dict:
    return {
        "texto": h.text,
        "prioridad": h.priority.value,
        "evidencia": h.evidence_level.value,
        "rationale": h.rationale,
        "guarda_activada": h.rationale.startswith("ADVERTENCIA"),
    }


def _construir_caso_base() -> ClinicalCase:
    pico_obj = PICOSynthesis(
        patient_profile="Masculino 42 años",
        chief_complaint="Neuropatía axonal sensitivomotora bilateral",
        relevant_history=["inicio insidioso a los 38 años"],
        negative_findings=["Panel CMT negativo (PMP22, MFN2, GJB1, MPZ)"],
        disease_duration="4 años",
        current_treatments=[],
        procedures_done=["EMG", "NCV"],
        comparison="No aplica",
        primary_outcome="Determinar etiología",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=[],
        clinical_narrative=TEXTO_BASE,
        condition_en="hereditary axonal neuropathy",
    )
    return ClinicalCase(raw_text=TEXTO_BASE, pico=pico_obj)


def _construir_caso_ttr() -> ClinicalCase:
    pico_obj = PICOSynthesis(
        patient_profile="Masculino 67 años",
        chief_complaint="Polineuropatía axonal + insuficiencia cardíaca",
        relevant_history=["síndrome del túnel carpiano bilateral operado"],
        negative_findings=[],
        disease_duration="3 años",
        current_treatments=[],
        procedures_done=["biopsia nerviosa", "estudio genético"],
        comparison="No aplica",
        primary_outcome="Confirmar amiloidosis ATTR y evaluar tratamiento",
        secondary_outcomes=[],
        biomarkers=["TTR"],
        genetic_findings=["TTR p.Val30Met (c.148G>A) heterocigota — patogénica (ClinVar)"],
        clinical_narrative=TEXTO_TTR,
        condition_en="hereditary transthyretin amyloidosis",
    )
    case = ClinicalCase(raw_text=TEXTO_TTR, pico=pico_obj)
    case.biomarkers = BiomarkerProfile(
        genes=["TTR"],
        genetic_variants=["p.Val30Met"],
    )
    return case


# ── Escenario A: caso base ────────────────────────────────────────────────────

async def escenario_a() -> None:
    print(f"\n{SEP}")
    print("  ESCENARIO A — Caso base (panel CMT negativo, sin hallazgos genéticos)")
    print(SEP)

    case = _construir_caso_base()

    ctx_base = gc_module.build(case)
    ctx = await gc_module.enrich(ctx_base)
    case.genomic_context = ctx

    print("\n  Perfil genómico construido:")
    print(f"    Variantes       : {ctx.variants or '—'}")
    print(f"    Hallazgos       : {ctx.genetic_findings or '—'}")
    print(f"    Genes saneados  : {ctx.genes or '—'}")
    print(f"    Descartados     : {ctx.discarded_symbols or '—'}")
    print(f"    Estud. negativos: {ctx.negative_genetic_studies or '—'}")
    print(f"    Anotaciones PharmGKB: {len(ctx.annotations)}")
    fuentes = {s.name: s.status.value for s in ctx.sources}
    print(f"    Fuentes: {fuentes}")

    bloque = ctx.to_prompt_block()
    print(f"\n  Bloque enviado al agente:\n{bloque}")

    contexto_dict = {
        "variantes": ctx.variants,
        "hallazgos": ctx.genetic_findings,
        "genes": ctx.genes,
        "descartados": list(ctx.discarded_symbols),
        "estudios_negativos": ctx.negative_genetic_studies,
        "anotaciones": len(ctx.annotations),
        "fuentes": fuentes,
        "bloque_prompt": bloque,
    }
    _guardar("contexto_caso_base.json", contexto_dict)

    agente = GenomicsSpecialistAgent(genomic_context=ctx)
    contexto_pico = pico.format_for_agents(case.pico)

    print("\n  Llamando al LLM (Groq)…")
    try:
        output = agente.run(contexto_pico)
        print(f"  Hipótesis generadas: {len(output.hypotheses)}")
        for i, h in enumerate(output.hypotheses, 1):
            guard = " ⚠ GUARDA" if h.rationale.startswith("ADVERTENCIA") else ""
            print(f"\n  [{i}] {h.text[:80]}")
            print(f"       {h.priority.value} | Ev.{h.evidence_level.value}{guard}")
            print(f"       {h.rationale[:100]}…")
        _guardar("hipotesis_caso_base.json", {
            "agente_id": output.agent_id,
            "agente_nombre": output.agent_name,
            "hipotesis": [_hipotesis_a_dict(h) for h in output.hypotheses],
        })
    except Exception as exc:
        print(f"  ⚠ LLM no disponible ({exc}). El perfil genómico se guardó igual.")
        _guardar("hipotesis_caso_base.json", {"error": str(exc)})


# ── Escenario B: TTR p.Val30Met ───────────────────────────────────────────────

async def escenario_b() -> None:
    print(f"\n{SEP}")
    print("  ESCENARIO B — TTR p.Val30Met (amiloidosis ATTR hereditaria)")
    print(SEP)

    case = _construir_caso_ttr()

    ctx_base = gc_module.build(case)
    ctx = await gc_module.enrich(ctx_base)
    case.genomic_context = ctx

    print("\n  Perfil genómico construido:")
    print(f"    Variantes       : {ctx.variants or '—'}")
    print(f"    Hallazgos       : {ctx.genetic_findings or '—'}")
    print(f"    Genes saneados  : {ctx.genes or '—'}")
    print(f"    Anotaciones PharmGKB: {len(ctx.annotations)}")
    if ctx.annotations:
        for ann in ctx.annotations[:2]:
            print(f"      {ann.gene} / {ann.drug} — {ann.significance} (nivel {ann.level})")
    fuentes = {s.name: s.status.value for s in ctx.sources}
    print(f"    Fuentes: {fuentes}")

    bloque = ctx.to_prompt_block()
    print(f"\n  Bloque enviado al agente:\n{bloque[:500]}{'…' if len(bloque) > 500 else ''}")

    contexto_dict = {
        "variantes": ctx.variants,
        "hallazgos": ctx.genetic_findings,
        "genes": ctx.genes,
        "descartados": list(ctx.discarded_symbols),
        "anotaciones": [
            {"gen": a.gene, "farmaco": a.drug, "significancia": a.significance, "nivel": a.level}
            for a in ctx.annotations
        ],
        "fuentes": fuentes,
        "bloque_prompt": bloque,
    }
    _guardar("contexto_ttr.json", contexto_dict)

    agente = GenomicsSpecialistAgent(genomic_context=ctx)
    contexto_pico = pico.format_for_agents(case.pico)

    print("\n  Llamando al LLM (Groq)…")
    try:
        output = agente.run(contexto_pico)
        print(f"  Hipótesis generadas: {len(output.hypotheses)}")
        for i, h in enumerate(output.hypotheses, 1):
            guard = " ⚠ GUARDA" if h.rationale.startswith("ADVERTENCIA") else ""
            print(f"\n  [{i}] {h.text[:80]}")
            print(f"       {h.priority.value} | Ev.{h.evidence_level.value}{guard}")
            print(f"       {h.rationale[:100]}…")
        _guardar("hipotesis_ttr.json", {
            "agente_id": output.agent_id,
            "agente_nombre": output.agent_name,
            "hipotesis": [_hipotesis_a_dict(h) for h in output.hypotheses],
        })
    except Exception as exc:
        print(f"  ⚠ LLM no disponible ({exc}). El perfil genómico se guardó igual.")
        _guardar("hipotesis_ttr.json", {"error": str(exc)})


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 72)
    print("  NEXUS — Demo Agente 02: Especialista Genómica")
    print("  Tarea Trello #51 — Sprint 4")
    print("=" * 72)

    await escenario_a()
    await escenario_b()

    print(f"\n{SEP}")
    print(f"  Artefactos guardados en: {OUTPUT_DIR}/")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
