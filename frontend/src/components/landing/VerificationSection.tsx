import ScrollReveal from "@/components/ScrollReveal";
import BeforeAfter from "@/components/BeforeAfter";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Verification: the measured figure as the dominant number and the real
 * citation pair (`BeforeAfter`) as the centrepiece.
 *
 * The page has no testimonials or customer logos to show, and none are
 * invented: the proof is the measured run of the test case (22 September
 * 2026), stated with its scope. The figure and its note are real data and are
 * kept verbatim.
 */
export default function VerificationSection() {
  return (
    <section
      id="verificacion"
      aria-labelledby="verificacion-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
            <h2 id="verificacion-heading" className="lg:col-span-7">
              <span className="block font-mono text-7xl font-bold text-accent sm:text-8xl lg:text-9xl">
                14 de 18
              </span>
              <span className="mt-4 block text-2xl font-semibold text-balance text-fg sm:text-3xl">
                citas no coincidieron con PubMed
              </span>
            </h2>
            <p className="text-sm text-pretty text-fg-muted lg:col-span-5">
              Corrida real del caso de prueba, 22 de septiembre de 2026: 3
              coincidieron y 1 no traía PMID. Es un caso medido, no una tasa
              general.
            </p>
          </div>
        </ScrollReveal>

        <ScrollReveal className="mt-12">
          <BeforeAfter />
        </ScrollReveal>
      </div>
    </section>
  );
}
