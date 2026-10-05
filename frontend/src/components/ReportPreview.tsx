import { CheckIcon, VerifiedIcon } from "@/components/icons";

/**
 * Vista previa del reporte para el hero de la landing.
 *
 * Muestra, en HTML/CSS, una ficha de hipótesis como la que produce NEXUS:
 * enunciado, nivel de evidencia, estado, fuente verificada y agentes que la
 * sostienen; y detrás una segunda ficha "especulativa" para contrastar una
 * hipótesis respaldada con una sin respaldo.
 *
 * El contenido es inventado y está rotulado como "Ejemplo ilustrativo". El
 * PMID es el que ya usan los tests del proyecto. Todo es texto real (no una
 * imagen), así que lo leen los lectores de pantalla.
 */
export default function ReportPreview() {
  return (
    <figure aria-labelledby="preview-caption" className="m-0">
      <div className="relative z-10 rounded-2xl border border-border bg-bg p-6 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-4">
          <span className="rounded-full border border-accent px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-widest text-accent">
            Ejemplo ilustrativo
          </span>
          <span className="text-xs text-fg-muted">
            Hipótesis de investigación, no un diagnóstico
          </span>
        </div>

        <p className="mt-5 font-serif text-xl leading-snug text-balance">
          El déficit de vitamina B12 asociado al uso crónico de metformina
          podría contribuir a la neuropatía axonal sensitivomotora del
          paciente.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-accent px-2.5 py-1 text-xs font-semibold text-accent-fg">
            Nivel II
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-accent px-2.5 py-1 text-xs font-semibold text-accent">
            <CheckIcon className="h-3.5 w-3.5" />
            Respaldada
          </span>
        </div>

        <div className="mt-5 rounded-xl bg-bg-subtle px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-fg-muted">
            Fuente
          </p>
          <p className="mt-1 text-sm font-medium">
            Metformin-associated vitamin B12 deficiency
          </p>
          <p className="mt-0.5 text-xs text-fg-muted">PMID 22439958</p>
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-accent">
            <VerifiedIcon className="h-4 w-4" />
            Título verificado contra PubMed
          </p>
        </div>

        <p className="mt-5 text-xs text-fg-muted">
          <span className="font-semibold text-fg">Sostenida por:</span> Agente
          01 · Analista de Literatura, Agente 03 · Consultor Clínico
        </p>
      </div>

      {/* Segunda ficha que asoma detrás: hipótesis sin respaldo verificable. */}
      <div className="mx-5 -mt-3 rounded-b-2xl border border-dashed border-border bg-bg-subtle px-5 pt-6 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-fg-muted px-2 py-0.5 text-xs font-semibold text-fg-muted">
            Nivel III
          </span>
          <span className="text-xs font-semibold text-fg-muted">
            Especulativa: sin respaldo verificado
          </span>
        </div>
        <p className="mt-2 text-sm text-fg-muted">
          Origen autoinmune de la neuropatía.
        </p>
      </div>

      <figcaption
        id="preview-caption"
        className="mt-3 text-center text-xs text-fg-muted"
      >
        Ficha de ejemplo con datos inventados, para mostrar cómo se presenta
        cada hipótesis en el reporte.
      </figcaption>
    </figure>
  );
}
