import HeroReportTabs from "@/components/landing/HeroReportTabs";
import {
  EXAMPLE_HYPOTHESES,
  ExampleHypothesis,
  Mark,
} from "@/components/landing/reportExample";

/**
 * Example NEXUS report, built in code, used by the landing as its product
 * visual: the full report in `#reporte` (`ReportDemo`) and the hypothesis
 * card of the hero (`ReportSnippet`), whose tabs switch between the three
 * hypotheses. Both read the hypotheses from `landing/reportExample.tsx` and
 * render them through `ExampleHypothesis`, so texts and markup live in one
 * place.
 *
 * Everything is real text, not an image: screen readers read it whole. The
 * hypotheses are an illustrative example and both views carry the "Ejemplo
 * ilustrativo" marker; PMID 22439958 is the one the project tests already use
 * and the trial is a public record that appeared in a real run.
 *
 * Layout: one bordered card whose panels are separated by the 1 px gaps of
 * the grid, so no panel carries a border on a single side.
 */

/** Re-exported for the legend of the report section. */
export { ANNOTATION_DOT, REPORT_ANNOTATIONS } from "@/components/landing/reportExample";

const PANEL_LABEL = "text-sm font-semibold text-fg-muted";

const FRAME = "m-0 grid gap-px overflow-hidden rounded-2xl border border-border bg-border";

function ExampleBadge() {
  return (
    <span className="rounded-full border border-ochre px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-ochre">
      Ejemplo ilustrativo
    </span>
  );
}

function ReportTitle() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-lg font-semibold whitespace-nowrap text-accent">
        Reporte de análisis
      </span>
      <ExampleBadge />
    </div>
  );
}

const [LEAD, ...OTHER_HYPOTHESES] = EXAMPLE_HYPOTHESES;

/**
 * Hero visual: one hypothesis of the example report at a time, as a single
 * card. The frame and the title are rendered on the server; the tabs and the
 * panels are the `HeroReportTabs` Client Component, whose server render
 * already shows the first hypothesis.
 */
export function ReportSnippet() {
  return (
    <figure
      aria-label="Ejemplo ilustrativo de una hipótesis del reporte"
      className={FRAME}
    >
      <div className="bg-bg-subtle px-6 py-4">
        <ReportTitle />
      </div>
      <HeroReportTabs />
    </figure>
  );
}

/** Full example report, with the numbered marks the landing annotates. */
export default function ReportDemo() {
  return (
    <figure aria-labelledby="reportdemo-caption" className={FRAME}>
      {/* Report bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-bg-subtle px-6 py-4">
        <ReportTitle />
        <p className="text-sm text-fg-muted">
          Hipótesis: <strong className="font-mono font-semibold text-fg">3</strong> ·
          Ensayos: <strong className="font-mono font-semibold text-fg">1</strong> ·
          Fuentes verificadas:{" "}
          <strong className="font-mono font-semibold text-fg">1 de 1</strong>
        </p>
      </div>

      <div className="grid gap-px lg:grid-cols-12">
        {/* Hypotheses */}
        <div className="grid gap-px lg:col-span-7">
          <article className="bg-surface p-6">
            <p className={`${PANEL_LABEL} mb-6`}>
              Hipótesis de investigación · no son diagnósticos
            </p>
            <ExampleHypothesis hypothesis={LEAD} lead annotated />
            <p className="mt-4 flex items-start gap-2 text-sm text-pretty text-fg-muted">
              <Mark note={3} />
              <span>
                <strong className="font-semibold text-fg">Sostenida por:</strong>{" "}
                Agente 01 · Analista de Literatura, Agente 03 · Consultor Clínico
              </span>
            </p>
          </article>

          {OTHER_HYPOTHESES.map((hypothesis) => (
            <article key={hypothesis.id} className="bg-surface p-6">
              <ExampleHypothesis hypothesis={hypothesis} />
            </article>
          ))}
        </div>

        {/* Compatible trial */}
        <aside className="bg-surface p-6 lg:col-span-5">
          <p className={`${PANEL_LABEL} flex items-center gap-2`}>
            <Mark note={4} />
            Ensayo clínico compatible
          </p>
          <p className="mt-3 text-lg font-semibold text-pretty text-fg">
            Natural History Study for Charcot Marie Tooth Disease
          </p>
          <p className="mt-1 text-sm text-fg-muted">
            <span className="font-mono">NCT05902351</span> · Reclutando ·
            ClinicalTrials.gov
          </p>
          <p className="mt-3 inline-flex rounded-md border border-accent px-2 py-1 text-xs font-semibold text-accent">
            Compatibilidad orientativa: alta
          </p>
          <p className="mt-3 text-sm text-pretty text-fg-muted">
            A verificar por el médico: diagnóstico clínico o sospecha de
            neuropatía hereditaria; consentimiento informado.
          </p>
        </aside>
      </div>

      <figcaption
        id="reportdemo-caption"
        className="bg-bg-subtle px-6 py-3 text-xs text-pretty text-fg-muted"
      >
        Ejemplo ilustrativo: las hipótesis y su contenido son inventados para
        mostrar cómo se presenta el reporte. El registro del ensayo es un
        registro público de ClinicalTrials.gov.
      </figcaption>
    </figure>
  );
}
