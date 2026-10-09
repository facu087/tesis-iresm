import {
  ChatsCircleIcon,
  FlaskIcon,
  RankingIcon,
  SealCheckIcon,
} from "@phosphor-icons/react/ssr";
import ScrollReveal from "@/components/ScrollReveal";
import SectionHeading from "@/components/landing/SectionHeading";
import { CARD, CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Benefits: four outcomes for the physician, each one a bold benefit followed
 * by the detail that backs it. Every statement describes behaviour that is
 * implemented in the pipeline (`backend/pipeline/verification.py`,
 * `evidence.py`, `consensus.py` and `trial_matching.py`).
 */
const BENEFITS = [
  {
    Icon: SealCheckIcon,
    title: "Citas contrastadas antes de leerlas",
    detail:
      "Cada PMID que cita un agente se consulta en PubMed y el título real se compara con el citado. Una cita que no coincide no cuenta como respaldo.",
  },
  {
    Icon: RankingIcon,
    title: "Prioridad por nivel de evidencia",
    detail:
      "El reporte ordena las hipótesis por nivel I, II y III. Una hipótesis sin fuente verificable no se descarta: queda como especulativa y nunca supera el nivel III.",
  },
  {
    Icon: ChatsCircleIcon,
    title: "Desacuerdos a la vista",
    detail:
      "El Árbitro agrupa las hipótesis equivalentes en un consenso y documenta las objeciones que quedaron sin resolver, en lugar de ocultarlas.",
  },
  {
    Icon: FlaskIcon,
    title: "Ensayos clínicos activos para el caso",
    detail:
      "Búsqueda en ClinicalTrials.gov y de enfermedades raras compatibles en Orphanet, con una compatibilidad orientativa que nunca excluye resultados.",
  },
] as const;

export default function BenefitsSection() {
  return (
    <section
      id="beneficios"
      aria-labelledby="beneficios-heading"
      className={`bg-bg ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="beneficios-heading"
            eyebrow="Qué obtiene el médico"
            title="Un reporte que muestra qué está respaldado y qué no"
          />
        </ScrollReveal>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2">
          {BENEFITS.map((benefit, index) => (
            <li key={benefit.title} className="flex">
              <ScrollReveal delay={(index % 2) * 120} className="flex w-full">
                <div className={`${CARD} w-full`}>
                  <benefit.Icon aria-hidden="true" className="size-8 text-accent" />
                  <h3 className="mt-4 text-xl font-semibold text-balance text-fg">
                    {benefit.title}
                  </h3>
                  <p className="mt-2 text-base text-pretty text-fg-muted">
                    {benefit.detail}
                  </p>
                </div>
              </ScrollReveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
