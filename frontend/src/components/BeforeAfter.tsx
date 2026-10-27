import { WarningIcon } from "@phosphor-icons/react/ssr";
import VerificationSequence from "@/components/landing/VerificationSequence";

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
 *
 * This is the resolved comparison, server rendered. `VerificationSequence`
 * plays it as a sequence on scroll by revealing the parts marked with
 * `data-step` in order; the skeleton of the lookup beat is laid over the
 * PubMed title, so no beat changes the height of the card.
 */

const PANEL = "bg-surface p-6 sm:p-8";
const QUOTE = "text-2xl font-semibold text-pretty text-fg sm:text-3xl";
const SKELETON_BAR = "landing-verify-bar h-6 rounded-sm bg-border";

export default function BeforeAfter() {
  return (
    <VerificationSequence
      captionId="beforeafter-caption"
      caption={
        <>
          Caso real, no ilustrativo: corrida del caso de prueba del 22 de
          septiembre de 2026.
        </>
      }
    >
      <div className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-2">
        <div className={PANEL}>
          <p className="text-sm font-semibold text-fg-muted">
            Antes · lo que declaró el modelo
          </p>
          <div data-step="cited" className="mt-4">
            <blockquote className={QUOTE}>
              IgM paraprotein-associated neuropathy: clinical features and
              treatment
            </blockquote>
            <p className="mt-4 text-sm text-fg-muted">
              Neurology · 2013 · <span className="font-mono">PMID 23686244</span>
            </p>
          </div>
        </div>
        <div className={PANEL}>
          <p className="text-sm font-semibold text-fg-muted">
            Después · lo que devuelve PubMed
          </p>
          <div className="relative mt-4">
            <div data-step="real">
              <blockquote className={QUOTE}>
                Paper-based transparent flexible thin film supercapacitors.
              </blockquote>
              <p className="mt-4 text-sm text-fg-muted">
                Título real del <span className="font-mono">PMID 23686244</span>
              </p>
            </div>
            {/* Lookup beat: bars shaped like the title lines, never read aloud. */}
            <div
              aria-hidden="true"
              className="landing-verify-skeleton pointer-events-none absolute inset-0 flex flex-col gap-2 overflow-hidden pt-1 sm:gap-3"
            >
              <span className={`${SKELETON_BAR} w-full`} />
              <span className={`${SKELETON_BAR} w-2/3`} />
              <span className="mt-auto text-sm text-fg-muted">
                Consultando PubMed
              </span>
            </div>
          </div>
        </div>
        <div className="bg-bg-subtle p-6 sm:px-8 md:col-span-2">
          <div data-step="verdict">
            <p className="flex items-start gap-2 text-lg font-semibold text-ochre">
              <WarningIcon aria-hidden="true" weight="bold" className="mt-1 size-5 shrink-0" />
              Veredicto del sistema: no coincide
            </p>
            <p className="mt-2 text-base text-pretty text-fg-muted">
              La referencia no cuenta como respaldo de la hipótesis.
            </p>
          </div>
        </div>
      </div>
    </VerificationSequence>
  );
}
