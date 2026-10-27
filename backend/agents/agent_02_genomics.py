"""
Agente 02 — Especialista en Genómica
Modelo: openai/gpt-oss-120b via Groq
Rol: Generar hipótesis de investigación desde la perspectiva genómica/molecular.
"""

from __future__ import annotations

import re
import sys

from .base_agent import BaseAgent, GROQ_MAIN
from ..models.genomics import GenomicContext
from ..models.hypothesis import Hypothesis, Priority
from ..models.report import AgentOutput

_VARIANT_IN_TEXT = re.compile(r"\b(?:p\.|c\.)[A-Za-z0-9>_*+\-]{3,}")
_GENE_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{1,7}\b")
_WARNING = "ADVERTENCIA: hallazgo no reportado en el caso. "


def _normalize(finding: str) -> str:
    """Minúsculas, sin espacios ni prefijos c./p./g., para comparar hallazgos."""
    return re.sub(r"\s+|\b[cpg]\.", "", finding.lower())


def _declared_findings(raw: str) -> dict[str, list[str]]:
    """
    `case_genetic_findings` de cada hipótesis, leído del JSON crudo del LLM y
    indexado por el texto de la hipótesis: el modelo `Hypothesis` no tiene ese
    campo, así que después de `parse_hypotheses()` ya no está.
    """
    try:
        declared = BaseAgent.extract_json(raw).get("hypotheses", [])
    except (ValueError, AttributeError):
        return {}
    findings: dict[str, list[str]] = {}
    for h in declared if isinstance(declared, list) else []:
        if not isinstance(h, dict) or not isinstance(h.get("text"), str):
            continue
        raw_findings = h.get("case_genetic_findings") or []
        if isinstance(raw_findings, list):
            findings[h["text"].strip()] = [f for f in raw_findings if isinstance(f, str) and f.strip()]
    return findings

SYSTEM_PROMPT = """Eres un especialista en genética médica y genómica clínica.
Tu rol es analizar casos clínicos desde la perspectiva genómica y molecular para
generar hipótesis de investigación sobre la etiología genética de la enfermedad.

REGLAS CRÍTICAS:
1. NO emitas diagnósticos. Solo hipótesis de investigación a explorar.
2. NO recomiendes tratamientos ni dosis.
3. Razoná el patrón de herencia posible (autosómico dominante/recesivo, ligado al X,
   mitocondrial) y qué implican los estudios genéticos negativos previos.
4. Si el caso NO tiene variantes ni hallazgos genéticos positivos, operá en modo
   ORIENTACIÓN: genera hipótesis sobre qué estudios genéticos solicitar y por qué,
   sin asumir que hay una variante causante.
5. Si una hipótesis cita un hallazgo genético que NO está en el contexto del caso,
   marcala con priority="LOW" y comenzá el rationale con
   "ADVERTENCIA: hallazgo no reportado en el caso. ".
6. Cada hipótesis DEBE estar respaldada por evidencia. Si no la conocés con certeza,
   marcá evidence_level: "III" y no inventes PubMed IDs (dejá pmid: null).
7. Generá entre 1 y 4 hipótesis.
8. En "case_genetic_findings" listá solo los hallazgos genéticos del caso en los que
   se apoya la hipótesis, copiados del bloque CONTEXTO GENÓMICO. En modo ORIENTACIÓN
   la lista va vacía ([]).

FORMATO DE RESPUESTA:
Respondé ÚNICAMENTE con un objeto JSON válido:

{
  "hypotheses": [
    {
      "text": "descripción clara de la hipótesis de investigación",
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "evidence_level": "I" | "II" | "III",
      "rationale": "razonamiento genético/molecular",
      "case_genetic_findings": ["<hallazgo genético del caso, copiado tal como figura en el contexto>"],
      "sources": [
        {
          "pmid": "12345678 o null",
          "title": "título del paper",
          "journal": "nombre del journal",
          "year": 2023
        }
      ]
    }
  ]
}

Niveles de evidencia:
- I: revisiones sistemáticas, meta-análisis, RCTs
- II: estudios de cohorte, caso-control, series de casos prospectivas
- III: series de casos, reportes de caso, especulativo
"""

# Fragmentos del texto clínico que, si aparecen en una variante citada,
# indican que el LLM está inventando hallazgos del caso
_INVENTION_MARKERS = (
    "neuropatía", "axonal", "sensitivomotora", "progresiva",
    "autonómica", "ortostática", "sudomotora",
)


class GenomicsSpecialistAgent(BaseAgent):

    AGENT_ID = "02"
    AGENT_NAME = "Especialista Genómica"
    MODEL = GROQ_MAIN
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(self, genomic_context: GenomicContext | None = None) -> None:
        super().__init__()
        self._genomic_context: GenomicContext = genomic_context or GenomicContext()

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def run(self, clinical_context: str) -> AgentOutput:
        """Ronda 1: genera hipótesis desde la perspectiva genómica."""
        enriched = self._build_context(clinical_context)
        raw = self._call_llm(
            f"Analizá el siguiente caso clínico desde la perspectiva genómica "
            f"y generá hipótesis de investigación:\n\n{enriched}",
            task="agente02_hipotesis",
        )
        hypotheses = self.parse_hypotheses(raw)
        hypotheses = hypotheses[:4]
        hypotheses = self._apply_invention_guard(hypotheses, raw)
        return self._build_output(hypotheses, raw)

    def critique(self, clinical_context: str, own_output: AgentOutput, other_outputs: list[AgentOutput]) -> list:
        """Ronda 2: critica las hipótesis de los otros agentes."""
        enriched = self._build_context(clinical_context)
        return super().critique(enriched, own_output, other_outputs)

    def revise(self, clinical_context: str, own_output: AgentOutput, critiques: list) -> AgentOutput:
        """Ronda 3-4: revisa sus hipótesis en respuesta a críticas."""
        enriched = self._build_context(clinical_context)
        output = super().revise(enriched, own_output, critiques)
        hypotheses = output.hypotheses[:4]
        hypotheses = self._apply_invention_guard(hypotheses, output.raw_response)
        return AgentOutput(
            agent_id=output.agent_id,
            agent_name=output.agent_name,
            hypotheses=hypotheses,
            raw_response=output.raw_response,
        )

    def _build_recitation_prompt(
        self,
        hypotheses_with_reasons: list[tuple[str, list[str]]],
        articles: list[str],
    ) -> str:
        """
        Ronda 5: agrega el perfil genómico al pedido de recitación.

        Mismo criterio que `run()`, `critique()` y `revise()`: sin el bloque
        genómico este agente recita a ciegas sobre un caso del que conoce menos
        que el resto.

        La guarda anti-invención (`_apply_invention_guard`) **no** se aplica acá,
        y no es un olvido: opera sobre hipótesis que declaran hallazgos genéticos,
        y una recitación devuelve `{pmid, title}`, sin hallazgos que degradar. Esa
        salida ya está cubierta por dos guardas más estrictas —el PMID se valida
        contra el conjunto de artículos ofrecidos y el título se contrasta contra
        PubMed en la re-verificación—, así que el agente no puede inventar una
        referencia aunque quiera.
        """
        base = super()._build_recitation_prompt(hypotheses_with_reasons, articles)
        return f"{base}\n\n{self._genomic_context.to_prompt_block()}"

    # ── Internos ──────────────────────────────────────────────────────────────

    def _build_context(self, clinical_context: str) -> str:
        """Agrega el bloque genómico al contexto clínico."""
        return f"{clinical_context}\n\n{self._genomic_context.to_prompt_block()}"

    def _is_reported(self, finding: str) -> bool:
        """
        True si el hallazgo declarado por el LLM está en el caso: coincide con
        un hallazgo o variante reportados, o contiene una variante reportada y
        todos los genes que nombra están en el caso.
        """
        ctx = self._genomic_context
        norm = _normalize(finding)
        known = [_normalize(k) for k in ctx.variants + ctx.genetic_findings]
        if any(norm == k or norm in k for k in known):
            return True
        genes = set(_GENE_TOKEN.findall(finding))
        variants = [_normalize(v) for v in ctx.variants]
        return any(v and v in norm for v in variants) and genes <= set(ctx.genes)

    def _apply_invention_guard(self, hypotheses: list[Hypothesis], raw: str) -> list[Hypothesis]:
        """
        Degrada a LOW, sin descartar, las hipótesis que citan hallazgos
        genéticos no reportados en el caso.

        Dos controles: (1) cada `case_genetic_findings` declarado en el JSON
        crudo tiene que estar en el caso; (2) en modo orientación (sin variantes
        ni hallazgos positivos) ninguna notación de variante puede aparecer en
        el enunciado.
        """
        declared = _declared_findings(raw)
        orientation = not self._genomic_context.has_genomic_findings
        marked = 0
        for h in hypotheses:
            invented = orientation and bool(_VARIANT_IN_TEXT.search(h.text or ""))
            findings = declared.get((h.text or "").strip(), [])
            invented = invented or any(not self._is_reported(f) for f in findings)
            if invented:
                h.priority = Priority.LOW
                if not (h.rationale or "").startswith("ADVERTENCIA"):
                    h.rationale = _WARNING + (h.rationale or "")
                marked += 1

        if marked:
            print(
                f"[NEXUS] Agente 02: {marked} hipótesis degradadas a LOW "
                f"(hallazgos no reportados en el caso).",
                file=sys.stderr,
            )
        return hypotheses
