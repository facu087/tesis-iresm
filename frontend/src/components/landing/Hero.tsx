import AccessCta from "@/components/landing/AccessCta";
import IllustrationPlate from "@/components/landing/IllustrationPlate";
import { CONTAINER, TEXT_LINK } from "@/components/landing/styles";

/**
 * Hero: outcome headline, subheadline, the single primary action, one proof
 * signal (the measured verification figure) and the scope notice, all above
 * the fold, beside the hero illustration.
 *
 * The blocks rise in with a CSS only entrance (`.landing-rise`), so they end
 * visible without JavaScript and stay static under reduced motion.
 */

/** `id` of the hero action; the navigation watches it to reveal its own. */
export const HERO_ACTION_ID = "hero-solicitar-acceso";

function rise(delayMs: number): React.CSSProperties {
  return { "--landing-delay": `${delayMs}ms` } as React.CSSProperties;
}

export default function Hero() {
  return (
    <section aria-labelledby="hero-heading" className="bg-bg pt-24">
      <div
        className={`${CONTAINER} grid gap-12 pt-10 pb-16 lg:grid-cols-12 lg:items-center lg:gap-8 lg:pb-24`}
      >
        <div className="lg:col-span-7">
          <p className="landing-rise text-sm font-semibold text-ochre">
            Tesis final · Analista en Sistemas · IRESM
          </p>

          {/* Line breaks follow the thought; below `sm` the lines flow and balance. */}
          <h1
            id="hero-heading"
            className="landing-hero-heading landing-rise mt-4 max-w-[680px] pb-2 text-4xl font-semibold text-balance sm:text-5xl"
            style={rise(80)}
          >
            <span className="sm:block">Hipótesis de investigación </span>
            <span className="sm:block">con cada cita contrastada </span>
            <span className="sm:block">contra PubMed</span>
          </h1>

          <p
            className="landing-rise mt-4 max-w-[680px] text-lg text-pretty text-fg-muted"
            style={rise(160)}
          >
            Para médicos matriculados. NEXUS analiza los documentos clínicos de un
            paciente con seis agentes de IA que debaten en rondas adversariales y
            ordena las hipótesis por nivel de evidencia.
          </p>

          <div className="landing-rise mt-8" style={rise(240)}>
            <AccessCta id={HERO_ACTION_ID} />
          </div>

          <div
            className="landing-rise mt-8 grid max-w-[680px] gap-3 sm:grid-cols-2"
            style={rise(320)}
          >
            {/* Proof signal: the measured run, with its scope stated */}
            <div className="rounded-2xl border border-border bg-surface p-4">
              <p className="font-mono text-2xl font-semibold text-accent">14 de 18</p>
              <p className="mt-1 text-sm text-pretty text-fg-muted">
                citas no coincidieron con PubMed en la corrida real del caso de
                prueba.{" "}
                <a href="#verificacion" className={TEXT_LINK}>
                  Ver la medición
                </a>
              </p>
            </div>

            {/* Scope notice: always above the fold */}
            <p className="rounded-2xl border border-border bg-bg-subtle p-4 text-sm text-pretty text-fg-muted">
              <strong className="font-semibold text-fg">
                NEXUS no emite diagnósticos.
              </strong>{" "}
              Genera hipótesis de investigación para que las evalúe el médico
              responsable.
            </p>
          </div>
        </div>

        <div className="landing-rise lg:col-span-5" style={rise(240)}>
          <IllustrationPlate
            src="/landing/hero.webp"
            alt="Ilustración de seis nodos cuyas líneas se cruzan y convergen en una hoja de reporte."
            width={1600}
            height={1200}
            sizes="(min-width: 1024px) 40vw, 100vw"
            eager
          />
        </div>
      </div>
    </section>
  );
}
