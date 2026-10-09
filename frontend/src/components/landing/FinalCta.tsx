import ScrollReveal from "@/components/ScrollReveal";
import AccessCta from "@/components/landing/AccessCta";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Closing section: the final call to action, the same component as in the
 * hero. NEXUS has no trial, pricing or guarantee to offer, and none is
 * invented; the limits of the system are already shown above, so they are
 * not repeated here.
 */
export default function FinalCta() {
  return (
    <section
      aria-labelledby="cierre-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <div className="flex flex-wrap items-center justify-between gap-8 rounded-3xl border border-brand-line bg-brand p-6 text-brand-fg sm:p-12">
            <h2
              id="cierre-heading"
              className="max-w-[680px] text-3xl font-semibold text-balance sm:text-4xl"
            >
              Acceso para médicos matriculados
            </h2>
            <AccessCta tone="brand" />
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
