"""
Agente 02 — Especialista en Genómica
Modelo: openai/gpt-oss-120b via Groq
Rol: Generar hipótesis de investigación desde la perspectiva genómica/molecular.
"""

from __future__ import annotations

import sys

from .base_agent import BaseAgent, GROQ_MAIN
from ..models.genomics import GenomicContext
from ..models.report import AgentOutput

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

FORMATO DE RESPUESTA:
Respondé ÚNICAMENTE con un objeto JSON válido:

{
  "hypotheses": [
    {
      "text": "descripción clara de la hipótesis de investigación",
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "evidence_level": "I" | "II" | "III",
      "rationale": "razonamiento genético/molecular",
      "case_genetic_findings": ["TTR p.Val30Met"],
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
            f"y generá hipótesis de investigación:\n\n{enriched}"
        )
        hypotheses = self.parse_hypotheses(raw)
        hypotheses = hypotheses[:4]
        hypotheses = self._apply_invention_guard(hypotheses)
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
        hypotheses = self._apply_invention_guard(hypotheses)
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

    def _apply_invention_guard(self, hypotheses):
        """
        Degrada a LOW las hipótesis que citan hallazgos genéticos no reportados.

        Un hallazgo es "no reportado" cuando aparece en case_genetic_findings del
        JSON del agente pero no está en los datos reales del caso. En modo
        orientación (sin variantes ni hallazgos positivos) cualquier notación de
        variante (p.X o c.X) en el texto de la hipótesis activa la guarda.
        """
        ctx = self._genomic_context
        known = {f.lower() for f in ctx.variants + ctx.genetic_findings}
        in_orientation_mode = not ctx.has_genomic_findings

        marked = 0
        for h in hypotheses:
            invented = False

            if in_orientation_mode:
                # En modo orientación no debería haber notación de variante concreta
                import re
                if re.search(r'\b(?:p\.|c\.)[A-Za-z0-9>_*+\-]{3,}', h.text or ""):
                    invented = True

            # Hallazgos que el LLM dice que están en el caso pero no están
            raw_findings = getattr(h, "case_genetic_findings", None) or []
            if raw_findings:
                for finding in raw_findings:
                    if finding.lower() not in known:
                        invented = True
                        break

            if invented:
                from ..models.hypothesis import Priority
                object.__setattr__(h, "priority", Priority.LOW)
                rationale = h.rationale or ""
                if not rationale.startswith("ADVERTENCIA"):
                    object.__setattr__(
                        h, "rationale",
                        "ADVERTENCIA: hallazgo no reportado en el caso. " + rationale,
                    )
                marked += 1

        if marked:
            print(
                f"[NEXUS] Agente 02: {marked} hipótesis degradadas a LOW "
                f"(hallazgos no reportados en el caso).",
                file=sys.stderr,
            )

        return hypotheses
