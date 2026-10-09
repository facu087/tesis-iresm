import {
  CheckCircleIcon,
  ClockIcon,
  SealCheckIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";

/**
 * Example NEXUS report, built in code, used by the landing as its product
 * visual: the full report in `#reporte` (`ReportDemo`) and a single
 * hypothesis card in the hero (`ReportSnippet`). Both render the same lead
 * hypothesis through `LeadHypothesis`, so the markup lives in one place.
 *
 * Everything is real text, not an image: screen readers read it whole. The
 * hypotheses are an illustrative example and both views carry the "Ejemplo
 * ilustrativo" marker; PMID 22439958 is the one the project tests already use
 * and the trial is a public record that appeared in a real run.
 *
 * Layout: one bordered card whose panels are separated by the 1 px gaps of
 * the grid, so no panel carries a border on a single side.
 */

/**
 * What the numbered marks on the annotated report point at. The landing
 * renders this list as the legend, in the same order as the marks.
 */
export const REPORT_ANNOTATIONS = [
  "Cita contrastada con PubMed",
  "Orden por nivel de evidencia",
  "Consenso entre agentes",
  "Ensayos activos para el caso",
] as const;

const BADGE =
  "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold";

const PANEL_LABEL = "text-sm font-semibold text-fg-muted";

const FRAME = "m-0 grid gap-px overflow-hidden rounded-2xl border border-border bg-border";

/** Numbered circle shared by the marks on the report and by their legend. */
export const ANNOTATION_DOT =
  "inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ochre font-mono text-xs font-bold text-bg";

/** Numbered mark placed beside the part of the report an annotation is about. */
function Mark({ note }: { note: 1 | 2 | 3 | 4 }) {
  return (
    <span className={ANNOTATION_DOT}>
      <span className="sr-only">
        Nota {note}: {REPORT_ANNOTATIONS[note - 1]}
      </span>
      <span aria-hidden="true">{note}</span>
    </span>
  );
}

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

/**
 * Lead hypothesis of the example: statement, evidence level, status and its
 * citation verified against PubMed. `annotated` adds the numbered marks and
 * the agents that hold the hypothesis (full report only).
 */
function LeadHypothesis({ annotated = false }: { annotated?: boolean }) {
  return (
    <>
      <p className="font-mono text-sm font-semibold text-fg-muted">H1</p>
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
        {annotated && <Mark note={2} />}
      </div>
      {/* Nested radius: 16 px card minus the 24 px gap is below 2, so
          this inner block keeps its own small radius. */}
      <div className="mt-4 flex items-start justify-between gap-3 rounded-lg bg-bg-subtle p-4">
        <div>
          <p className="text-sm font-semibold text-fg">
            Metformin-associated vitamin B12 deficiency
          </p>
          <p className="mt-0.5 font-mono text-sm text-fg-muted">PMID 22439958</p>
          <p className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-accent">
            <SealCheckIcon aria-hidden="true" weight="bold" className="size-4" />
            Título verificado contra PubMed
          </p>
        </div>
        {annotated && <Mark note={1} />}
      </div>
      {annotated && (
        <p className="mt-4 flex items-start gap-2 text-sm text-pretty text-fg-muted">
          <Mark note={3} />
          <span>
            <strong className="font-semibold text-fg">Sostenida por:</strong>{" "}
            Agente 01 · Analista de Literatura, Agente 03 · Consultor Clínico
          </span>
        </p>
      )}
    </>
  );
}

/** Hero visual: one hypothesis of the example report, as a single card. */
export function ReportSnippet() {
  return (
    <figure
      aria-label="Ejemplo ilustrativo de una hipótesis del reporte"
      className={FRAME}
    >
      <div className="bg-bg-subtle px-6 py-4">
        <ReportTitle />
      </div>
      <div className="bg-surface p-6">
        <LeadHypothesis />
      </div>
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
            <LeadHypothesis annotated />
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
