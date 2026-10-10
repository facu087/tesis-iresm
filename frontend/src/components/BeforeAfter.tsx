import { WarningIcon } from "@phosphor-icons/react/ssr";

/**
 * "Before and after" comparison of one citation: the centrepiece of the
 * verification section.
 *
 * The pair comes from a real run of the test case (2026-09-22,
 * `output/corrida_agente04/reporte.json`, PMID 23686244): what the model
 * declared against the title PubMed returns for that PMID. Both titles are
 * real data and are kept verbatim. The verdict is stated with text and a
 * warning icon, never with colour alone.
 *
 * The three panels share one bordered card: the 1 px gaps of the grid show
 * the border colour, so no panel carries a border on a single side.
 */

const PANEL = "bg-surface p-6 sm:p-8";
const QUOTE = "mt-4 text-2xl font-semibold text-pretty text-fg sm:text-3xl";

export default function BeforeAfter() {
  return (
    <figure aria-labelledby="beforeafter-caption" className="m-0">
      <div className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-2">
        <div className={PANEL}>
          <p className="text-sm font-semibold text-fg-muted">
            Antes · lo que declaró el modelo
          </p>
          <blockquote className={QUOTE}>
            IgM paraprotein-associated neuropathy: clinical features and
            treatment
          </blockquote>
          <p className="mt-4 text-sm text-fg-muted">
            Neurology · 2013 · <span className="font-mono">PMID 23686244</span>
          </p>
        </div>
        <div className={PANEL}>
          <p className="text-sm font-semibold text-fg-muted">
            Después · lo que devuelve PubMed
          </p>
          <blockquote className={QUOTE}>
            Paper-based transparent flexible thin film supercapacitors.
          </blockquote>
          <p className="mt-4 text-sm text-fg-muted">
            Título real del <span className="font-mono">PMID 23686244</span>
          </p>
        </div>
        <div className="bg-bg-subtle p-6 sm:px-8 md:col-span-2">
          <p className="flex items-start gap-2 text-lg font-semibold text-ochre">
            <WarningIcon aria-hidden="true" weight="bold" className="mt-1 size-5 shrink-0" />
            Veredicto del sistema: no coincide
          </p>
          <p className="mt-2 text-base text-pretty text-fg-muted">
            La referencia no cuenta como respaldo de la hipótesis.
          </p>
        </div>
      </div>
      <figcaption id="beforeafter-caption" className="mt-3 text-xs text-fg-muted">
        Caso real, no ilustrativo: corrida del caso de prueba del 22 de
        septiembre de 2026.
      </figcaption>
    </figure>
  );
}
