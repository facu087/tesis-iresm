import {
  CheckCircleIcon,
  ClockIcon,
  SealCheckIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";

/**
 * Full width view of a NEXUS report, used by the landing.
 *
 * Shows what the real report has: consensus hypotheses with evidence level
 * and status (backed, pending, speculative), the agents that hold them, their
 * sources with the verification status and a clinical trial with an
 * orientative compatibility. Everything is real text, not an image: screen
 * readers read it whole. The hypotheses are an illustrative example and are
 * labelled as such; PMID 22439958 is the one the project tests already use
 * and the trial is a public record that appeared in a real run.
 *
 * Layout: one bordered card whose panels are separated by the 1 px gaps of
 * the grid, so no panel carries a border on a single side.
 */

const BADGE =
  "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold";

const PANEL_LABEL = "text-sm font-semibold text-fg-muted";

function Level({ level }: { level: "II" | "III" }) {
  return (
    <span
      className={`rounded-md border px-2 py-1 font-mono text-xs font-semibold ${
        level === "II"
          ? "border-accent bg-accent text-accent-fg"
          : "border-fg-muted text-fg-muted"
      }`}
    >
      Nivel {level}
    </span>
  );
}

export default function ReportDemo() {
  return (
    <figure
      aria-labelledby="reportdemo-caption"
      className="m-0 grid gap-px overflow-hidden rounded-2xl border border-border bg-border"
    >
      {/* Report bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-bg-subtle px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-lg font-semibold whitespace-nowrap text-accent">
            Reporte de análisis
          </span>
          <span className="rounded-full border border-ochre px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-ochre">
            Ejemplo ilustrativo
          </span>
        </div>
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
            <p className={PANEL_LABEL}>
              Hipótesis de investigación · no son diagnósticos
            </p>
            <p className="mt-6 font-mono text-sm font-semibold text-fg-muted">H1</p>
            <p className="mt-1 text-xl font-semibold text-pretty text-fg">
              El déficit de vitamina B12 asociado al uso crónico de metformina
              podría contribuir a la neuropatía axonal sensitivomotora del
              paciente.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Level level="II" />
              <span className={`${BADGE} border-accent text-accent`}>
                <CheckCircleIcon aria-hidden="true" weight="bold" className="size-4" />
                Respaldada
              </span>
            </div>
            {/* Nested radius: 16 px card minus the 24 px gap is below 2, so
                this inner block keeps its own small radius. */}
            <div className="mt-4 rounded-lg bg-bg-subtle p-4">
              <p className="text-sm font-semibold text-fg">
                Metformin-associated vitamin B12 deficiency
              </p>
              <p className="mt-0.5 font-mono text-sm text-fg-muted">PMID 22439958</p>
              <p className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-accent">
                <SealCheckIcon aria-hidden="true" weight="bold" className="size-4" />
                Título verificado contra PubMed
              </p>
            </div>
            <p className="mt-4 text-sm text-pretty text-fg-muted">
              <strong className="font-semibold text-fg">Sostenida por:</strong>{" "}
              Agente 01 · Analista de Literatura, Agente 03 · Consultor Clínico
            </p>
          </article>

          <article className="bg-surface p-6">
            <p className="font-mono text-sm font-semibold text-fg-muted">H2</p>
            <p className="mt-1 text-lg font-semibold text-pretty text-fg">
              Posible neuropatía asociada a deficiencia de cobre.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Level level="II" />
              <span className={`${BADGE} border-ochre text-ochre`}>
                <ClockIcon aria-hidden="true" weight="bold" className="size-4" />
                Pendiente
              </span>
            </div>
            <p className="mt-3 text-sm text-pretty text-fg-muted">
              La cita no pudo verificarse: PubMed no respondió. Se mantiene
              hasta poder contrastarla.
            </p>
          </article>

          <article className="bg-surface p-6">
            <p className="font-mono text-sm font-semibold text-fg-muted">H3</p>
            <p className="mt-1 text-lg font-semibold text-pretty text-fg">
              Origen autoinmune de la neuropatía.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Level level="III" />
              <span className={`${BADGE} border-dashed border-fg-muted text-fg-muted`}>
                <WarningIcon aria-hidden="true" weight="bold" className="size-4" />
                Especulativa
              </span>
            </div>
            <p className="mt-3 text-sm text-pretty text-fg-muted">
              Sin referencia verificable: se conserva, con el nivel de
              evidencia más bajo.
            </p>
          </article>
        </div>

        {/* Trial and how to read the statuses */}
        <aside className="flex flex-col gap-px lg:col-span-5">
          <div className="bg-surface p-6">
            <p className={PANEL_LABEL}>Ensayo clínico compatible</p>
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
          </div>

          <div className="flex-1 bg-surface p-6">
            <p className={PANEL_LABEL}>Cómo leer los estados</p>
            <dl className="mt-3 grid gap-3 text-sm">
              <div>
                <dt className="font-semibold text-accent">Respaldada</dt>
                <dd className="text-fg-muted">
                  Al menos una fuente cuyo título coincide con PubMed.
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-ochre">Pendiente</dt>
                <dd className="text-fg-muted">No se pudo verificar todavía.</dd>
              </div>
              <div>
                <dt className="font-semibold text-fg-muted">Especulativa</dt>
                <dd className="text-fg-muted">
                  Sin fuente verificable; nunca supera el nivel III.
                </dd>
              </div>
            </dl>
          </div>
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
