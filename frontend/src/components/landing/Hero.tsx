import { ReportSnippet } from "@/components/ReportDemo";
import AccessCta from "@/components/landing/AccessCta";
import LandingMark from "@/components/landing/LandingMark";
import { HERO_HEADLINE_LINES, SCOPE_NOTICE } from "@/components/landing/copy";
import { CONTAINER } from "@/components/landing/styles";

/**
 * Hero: outcome headline, a one sentence subheadline, the single primary
 * action and the scope notice, beside the product itself: one hypothesis card
 * of the example report, built in code and marked as an illustrative example.
 * Its tabs switch between a backed, a pending and a speculative hypothesis.
 * Behind that card sits the NEXUS mark as a faint watermark: decorative, wide
 * screens only. It starts at the left edge of the card and runs off to the
 * right, where the section clips it, so it never sits under the text column.
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
    <section aria-labelledby="hero-heading" className="overflow-x-clip bg-bg pt-24">
      <div
        className={`${CONTAINER} grid gap-12 pt-10 pb-16 lg:grid-cols-12 lg:items-center lg:gap-8 lg:pb-24`}
      >
        <div className="lg:col-span-7">
          {/* Line breaks follow the thought; below `sm` the lines flow and balance. */}
          <h1
            id="hero-heading"
            className="landing-hero-heading landing-rise max-w-[680px] pb-2 text-4xl font-semibold text-balance sm:text-5xl"
          >
            {HERO_HEADLINE_LINES.map((line) => (
              <span key={line} className="sm:block">
                {line}{" "}
              </span>
            ))}
          </h1>

          <p
            className="landing-rise mt-4 max-w-[680px] text-lg text-pretty text-fg-muted"
            style={rise(80)}
          >
            Seis agentes de IA debaten el caso clínico y ordenan las hipótesis
            por nivel de evidencia.
          </p>

          <div className="landing-rise mt-8" style={rise(160)}>
            <AccessCta id={HERO_ACTION_ID} />
          </div>

          {/* Scope notice: always above the fold */}
          <p
            className="landing-rise mt-8 max-w-[680px] text-sm text-pretty text-fg-muted"
            style={rise(240)}
          >
            <strong className="font-semibold text-fg">{SCOPE_NOTICE}</strong> Genera
            hipótesis de investigación para el médico responsable.
          </p>
        </div>

        <div className="landing-rise relative lg:col-span-5" style={rise(160)}>
          <div
            aria-hidden="true"
            className="landing-hero-mark pointer-events-none absolute -inset-y-24 left-0 hidden lg:block"
          >
            <LandingMark className="block h-full w-auto max-w-none" />
          </div>
          <div className="relative">
            <ReportSnippet />
          </div>
        </div>
      </div>
    </section>
  );
}
