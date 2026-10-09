import ScrollReveal from "@/components/ScrollReveal";
import BeforeAfter from "@/components/BeforeAfter";
import IllustrationPlate from "@/components/landing/IllustrationPlate";
import SectionHeading from "@/components/landing/SectionHeading";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Problem to solution, with the proof beside the claim.
 *
 * The page has no testimonials or customer logos to show, and none are
 * invented: the proof is the measured run of the test case (22 September
 * 2026), stated with its scope. The real citation pair lives in
 * `BeforeAfter`.
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
          <SectionHeading
            id="verificacion-heading"
            eyebrow="Verificación"
            title="Un modelo puede citar con aplomo un artículo que no existe como lo describe. NEXUS lo contrasta."
          />
        </ScrollReveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-12 lg:items-start">
          <ScrollReveal className="lg:col-span-7">
            <BeforeAfter />
          </ScrollReveal>

          <div className="grid gap-8 lg:col-span-5">
            <ScrollReveal delay={120}>
              <div className="rounded-2xl border border-brand-line bg-brand p-6 text-brand-fg">
                <p className="font-mono text-5xl font-semibold">
                  14 <span className="text-2xl">de 18</span>
                </p>
                <p className="mt-3 text-base font-semibold">
                  citas no coincidieron con PubMed
                </p>
                <p className="mt-3 text-sm text-pretty text-brand-fg-muted">
                  Corrida real del caso de prueba, 22 de septiembre de 2026: 3
                  coincidieron y 1 no traía PMID. Es un caso medido, no una tasa
                  general.
                </p>
              </div>
            </ScrollReveal>

            <ScrollReveal delay={240}>
              <IllustrationPlate
                src="/landing/verificacion.webp"
                alt="Ilustración de una lente que compara una ficha con una pila de páginas de revistas científicas."
                width={1200}
                height={900}
                sizes="(min-width: 1024px) 40vw, 100vw"
              />
            </ScrollReveal>
          </div>
        </div>
      </div>
    </section>
  );
}
