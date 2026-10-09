import ScrollReveal from "@/components/ScrollReveal";
import DebateDiagram from "@/components/DebateDiagram";
import IllustrationPlate from "@/components/landing/IllustrationPlate";
import SectionHeading from "@/components/landing/SectionHeading";
import {
  CARD,
  CONTAINER,
  FOCUS_RING,
  SECTION_PADDING,
  TRANSITION,
} from "@/components/landing/styles";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";

/**
 * How it works: the real pipeline grouped into three phases, with the full
 * eight stage flow (diagram plus step list) one disclosure away.
 *
 * The phases only regroup `PIPELINE_STEPS` (01 to 03, 04 and 05, 06 to 08);
 * the Agent 06 sentence comes from `backend/agents/agent_06_synthesizer.py`.
 * `PIPELINE_STEPS` is shared with `/analizar` and is not edited here: its
 * labels are only reformatted for display.
 */
const PHASES = [
  {
    title: "Preparación del caso",
    detail:
      "Se extrae el texto del PDF, nativo o escaneado con OCR, se normalizan los nombres de fármacos y las unidades de medida, y se arma la síntesis PICO del caso.",
  },
  {
    title: "Debate adversarial",
    detail:
      "Los agentes 01, 02 y 03 generan hipótesis en simultáneo, sin verse entre sí. Después, en las rondas 2 a 4, cada uno critica las hipótesis de los demás y revisa las propias.",
  },
  {
    title: "Verificación y reporte",
    detail:
      "El Agente 04 contrasta cada cita con PubMed, agrupa el consenso y pide una recitación a las hipótesis sin respaldo. El Agente 05 busca ensayos activos y el Agente 06 redacta el resumen ejecutivo.",
  },
] as const;

/** Display form of a shared step label: the dash becomes a colon. */
function displayLabel(label: string): string {
  return label.replace(" — ", ": ");
}

const PIPELINE_SUMMARY_LABEL =
  "Flujo del pipeline: " +
  PIPELINE_STEPS.map((step) => displayLabel(step.label)).join(", después ") +
  ".";

export default function HowItWorksSection() {
  return (
    <section
      id="como-funciona"
      aria-labelledby="como-funciona-heading"
      className={`bg-bg ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="como-funciona-heading"
            eyebrow="Cómo funciona"
            title="Del documento clínico al reporte, en tres fases"
          />
        </ScrollReveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-12 lg:items-start">
          <ol className="grid gap-4 lg:col-span-7">
            {PHASES.map((phase, index) => (
              <li key={phase.title}>
                <ScrollReveal delay={index * 120}>
                  <div className={`${CARD} grid gap-4 sm:grid-cols-[auto_1fr]`}>
                    <span
                      aria-hidden="true"
                      className="font-mono text-4xl font-semibold text-ochre"
                    >
                      {index + 1}
                    </span>
                    <div>
                      <h3 className="text-xl font-semibold text-fg">
                        <span className="sr-only">Fase {index + 1}: </span>
                        {phase.title}
                      </h3>
                      <p className="mt-2 text-base text-pretty text-fg-muted">
                        {phase.detail}
                      </p>
                    </div>
                  </div>
                </ScrollReveal>
              </li>
            ))}
          </ol>

          <ScrollReveal className="lg:col-span-5" delay={120}>
            <IllustrationPlate
              src="/landing/debate.webp"
              alt="Ilustración de tres nodos que intercambian flechas en rondas concéntricas."
              width={1200}
              height={900}
              sizes="(min-width: 1024px) 40vw, 100vw"
            />
          </ScrollReveal>
        </div>

        {/* Full flow: native disclosure, operable without JavaScript */}
        <ScrollReveal className="mt-8">
          <details className="group rounded-2xl border border-border bg-surface">
            <summary
              className={`cursor-pointer rounded-2xl p-6 text-lg font-semibold text-fg ${TRANSITION} hover:text-accent ${FOCUS_RING}`}
            >
              Ver las ocho etapas del pipeline
            </summary>
            <div className="grid gap-8 px-6 pb-6 lg:grid-cols-12 lg:items-start">
              {/*
                Below 768 px the diagram keeps a legible minimum width and
                scrolls inside its own box, never the page. The text
                alternative is the list beside it (same steps, same order).
              */}
              <div
                role="img"
                aria-label={PIPELINE_SUMMARY_LABEL}
                tabIndex={0}
                className={`overflow-x-auto rounded-lg md:overflow-visible lg:col-span-5 ${FOCUS_RING}`}
              >
                <DebateDiagram className="w-full max-w-md min-w-120 md:min-w-0" />
              </div>
              <ol className="grid gap-3 lg:col-span-7">
                {PIPELINE_STEPS.map((step) => (
                  <li
                    key={step.id}
                    className="grid gap-x-4 gap-y-1 rounded-lg bg-bg-subtle p-4 sm:grid-cols-[auto_1fr]"
                  >
                    <span
                      aria-hidden="true"
                      className="font-mono text-xl font-semibold text-accent"
                    >
                      {step.id}
                    </span>
                    <div>
                      <p className="text-base font-semibold text-fg">
                        <span className="sr-only">Paso {step.id}: </span>
                        {displayLabel(step.label)}
                      </p>
                      <p className="mt-1 text-sm text-pretty text-fg-muted">
                        {step.description}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </details>
        </ScrollReveal>
      </div>
    </section>
  );
}
