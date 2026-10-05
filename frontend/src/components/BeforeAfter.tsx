import { AlertIcon } from "@/components/icons";

/**
 * Comparación "antes y después" de una cita (variante /v2).
 *
 * El par sale de una corrida real del caso de prueba (2026-09-22,
 * `output/corrida_agente04/reporte.json`, PMID 23686244): lo que declaró el
 * modelo frente al título que PubMed devuelve para ese PMID. El veredicto se
 * dice con texto y con un ícono de alerta, no solo con color.
 */
export default function BeforeAfter() {
  return (
    <figure aria-labelledby="beforeafter-caption" className="m-0">
      <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-2">
        <div className="bg-surface p-6 sm:p-8">
          <p className="text-xs font-bold uppercase tracking-widest text-fg-muted">
            Antes · lo que declaró el modelo
          </p>
          <blockquote className="mt-4 border-l-2 border-fg pl-4 font-serif text-xl leading-snug">
            IgM paraprotein-associated neuropathy: clinical features and
            treatment
          </blockquote>
          <p className="mt-3 text-sm text-fg-muted">
            Neurology · 2013 · PMID 23686244
          </p>
        </div>
        <div className="bg-surface p-6 sm:p-8">
          <p className="text-xs font-bold uppercase tracking-widest text-fg-muted">
            Después · lo que devuelve PubMed
          </p>
          <blockquote className="mt-4 border-l-2 border-fg pl-4 font-serif text-xl leading-snug">
            Paper-based transparent flexible thin film supercapacitors.
          </blockquote>
          <p className="mt-3 text-sm text-fg-muted">
            Título real del PMID 23686244
          </p>
        </div>
        <div className="bg-bg-subtle px-6 py-4 sm:px-8 md:col-span-2">
          <p className="flex items-start gap-2 text-base font-bold text-ochre">
            <AlertIcon className="mt-0.5 h-5 w-5 shrink-0" />
            Veredicto del sistema: no coincide
          </p>
          <p className="mt-1 text-sm text-fg-muted">
            El título citado no corresponde al artículo que existe con ese
            PMID. La referencia no cuenta como respaldo y la hipótesis que
            dependía de ella queda marcada como sin respaldo verificable.
          </p>
        </div>
      </div>
      <figcaption
        id="beforeafter-caption"
        className="mt-3 text-xs text-fg-muted"
      >
        Caso real, no ilustrativo: corrida del caso de prueba del 22 de
        septiembre de 2026.
      </figcaption>
    </figure>
  );
}
