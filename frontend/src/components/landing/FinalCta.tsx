import { CheckCircleIcon } from "@phosphor-icons/react/ssr";
import ScrollReveal from "@/components/ScrollReveal";
import AccessCta from "@/components/landing/AccessCta";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Closing section: risk reversal and the final call to action.
 *
 * NEXUS has no trial, pricing or guarantee to offer, and none is invented.
 * The risk reversal is made only of true statements about how the system
 * limits its own claims. The action is the same component as in the hero.
 */
const ASSURANCES = [
  "NEXUS no emite diagnósticos: las hipótesis las evalúa el médico responsable.",
  "Ninguna hipótesis se descarta por falta de respaldo: queda marcada como especulativa, con nivel III.",
  "Cada fuente del reporte muestra su estado de verificación contra PubMed.",
] as const;

export default function FinalCta() {
  return (
    <section
      aria-labelledby="cierre-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <div className="grid gap-10 rounded-3xl border border-brand-line bg-brand p-6 text-brand-fg sm:p-12 lg:grid-cols-12 lg:items-center">
            <div className="lg:col-span-7">
              <h2
                id="cierre-heading"
                className="max-w-[680px] text-3xl font-semibold text-balance sm:text-4xl"
              >
                Acceso para médicos matriculados
              </h2>
              <ul className="mt-6 grid gap-3">
                {ASSURANCES.map((assurance) => (
                  <li
                    key={assurance}
                    className="flex items-start gap-3 text-base text-pretty text-brand-fg-muted"
                  >
                    <CheckCircleIcon
                      aria-hidden="true"
                      weight="fill"
                      className="mt-0.5 size-5 shrink-0 text-brand-fg"
                    />
                    {assurance}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lg:col-span-5 lg:justify-self-end">
              <AccessCta tone="brand" />
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
