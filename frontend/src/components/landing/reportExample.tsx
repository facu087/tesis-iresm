import {
  CheckCircleIcon,
  ClockIcon,
  SealCheckIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";

/**
 * Single source of the example hypotheses the landing shows: the full report
 * in `#reporte` (`ReportDemo`) and the tabbed card of the hero
 * (`HeroReportTabs`) both render them through `ExampleHypothesis`, so the
 * texts and the markup live in one place.
 *
 * This module has no state and no hooks on purpose: it is imported from a
 * Server Component and from a Client Component alike.
 *
 * The hypotheses are an illustrative example. PMID 22439958 is the one the
 * project tests already use.
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

/** Numbered circle shared by the marks on the report and by their legend. */
export const ANNOTATION_DOT =
  "inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ochre font-mono text-xs font-bold text-bg";

export type HypothesisStatus = "Respaldada" | "Pendiente" | "Especulativa";

type Citation =
  | { kind: "verified"; title: string; pmid: string; note: string }
  | { kind: "note"; text: string };

export type ExampleHypothesisData = {
  id: "H1" | "H2" | "H3";
  statement: string;
  level: "II" | "III";
  status: HypothesisStatus;
  citation: Citation;
};

/** The three example hypotheses, one per status, in the order of the report. */
export const EXAMPLE_HYPOTHESES: readonly ExampleHypothesisData[] = [
  {
    id: "H1",
    statement:
      "El déficit de vitamina B12 asociado al uso crónico de metformina podría contribuir a la neuropatía axonal sensitivomotora del paciente.",
    level: "II",
    status: "Respaldada",
    citation: {
      kind: "verified",
      title: "Metformin-associated vitamin B12 deficiency",
      pmid: "PMID 22439958",
      note: "Título verificado contra PubMed",
    },
  },
  {
    id: "H2",
    statement: "Posible neuropatía asociada a deficiencia de cobre.",
    level: "II",
    status: "Pendiente",
    citation: {
      kind: "note",
      text: "La cita no pudo verificarse: PubMed no respondió. Se mantiene hasta poder contrastarla.",
    },
  },
  {
    id: "H3",
    statement: "Origen autoinmune de la neuropatía.",
    level: "III",
    status: "Especulativa",
    citation: {
      kind: "note",
      text: "Sin referencia verificable: se conserva, con el nivel de evidencia más bajo.",
    },
  },
];

const BADGE =
  "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold";

const STATUS_STYLES = {
  Respaldada: { Icon: CheckCircleIcon, className: "border-accent text-accent" },
  Pendiente: { Icon: ClockIcon, className: "border-ochre text-ochre" },
  Especulativa: {
    Icon: WarningIcon,
    className: "border-dashed border-fg-muted text-fg-muted",
  },
} as const;

/** Numbered mark placed beside the part of the report an annotation is about. */
export function Mark({ note }: { note: 1 | 2 | 3 | 4 }) {
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

function StatusBadge({ status }: { status: HypothesisStatus }) {
  const { Icon, className } = STATUS_STYLES[status];
  return (
    <span className={`${BADGE} ${className}`}>
      <Icon aria-hidden="true" weight="bold" className="size-4" />
      {status}
    </span>
  );
}

/**
 * One example hypothesis: statement, evidence level, status and what the
 * report shows about its citation. `lead` uses the larger type of the first
 * hypothesis of the report; `annotated` adds the numbered marks (full report
 * only).
 */
export function ExampleHypothesis({
  hypothesis,
  lead = false,
  annotated = false,
}: {
  hypothesis: ExampleHypothesisData;
  lead?: boolean;
  annotated?: boolean;
}) {
  const { citation } = hypothesis;
  const gap = lead ? "mt-4" : "mt-3";
  return (
    <>
      <p className="font-mono text-sm font-semibold text-fg-muted">{hypothesis.id}</p>
      <p
        className={`mt-1 font-semibold text-pretty text-fg ${lead ? "text-xl" : "text-lg"}`}
      >
        {hypothesis.statement}
      </p>
      <div className={`${gap} flex flex-wrap items-center gap-2`}>
        <Level level={hypothesis.level} />
        <StatusBadge status={hypothesis.status} />
        {annotated && <Mark note={2} />}
      </div>
      {citation.kind === "verified" ? (
        /* Nested radius: 16 px card minus the 24 px gap is below 2, so this
           inner block keeps its own small radius. */
        <div
          className={`${gap} flex items-start justify-between gap-3 rounded-lg bg-bg-subtle p-4`}
        >
          <div>
            <p className="text-sm font-semibold text-fg">{citation.title}</p>
            <p className="mt-0.5 font-mono text-sm text-fg-muted">{citation.pmid}</p>
            <p className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-accent">
              <SealCheckIcon aria-hidden="true" weight="bold" className="size-4" />
              {citation.note}
            </p>
          </div>
          {annotated && <Mark note={1} />}
        </div>
      ) : (
        <p className={`${gap} text-sm text-pretty text-fg-muted`}>{citation.text}</p>
      )}
    </>
  );
}
