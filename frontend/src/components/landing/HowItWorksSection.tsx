import ScrollReveal from "@/components/ScrollReveal";
import PipelineDiagram from "@/components/landing/PipelineDiagram";
import SectionHeading from "@/components/landing/SectionHeading";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * How it works: one diagram of the real pipeline that lights up stage by
 * stage as the user scrolls, beside a heading that stays in view on wide
 * screens. The diagram is the text alternative of itself: an ordered list.
 */
export default function HowItWorksSection() {
  return (
    <section
      id="como-funciona"
      aria-labelledby="como-funciona-heading"
      className={`bg-bg ${SECTION_PADDING}`}
    >
      <div className={`${CONTAINER} grid gap-12 lg:grid-cols-12 lg:items-start`}>
        <div className="lg:sticky lg:top-32 lg:col-span-5">
          <ScrollReveal>
            <SectionHeading
              id="como-funciona-heading"
              eyebrow="Cómo funciona"
              title="Del documento clínico al reporte"
            />
          </ScrollReveal>
        </div>
        <div className="lg:col-span-7">
          <PipelineDiagram />
        </div>
      </div>
    </section>
  );
}
