import {
  CheckCircleIcon,
  CircleIcon,
  MinusCircleIcon,
  QuestionIcon,
  SealCheckIcon,
  XCircleIcon,
} from "@phosphor-icons/react/ssr";
import type { Icon } from "@phosphor-icons/react";
import type { Source } from "@/lib/types";
import { TEXT_LINK } from "@/components/landing/styles";
import { DANGER_INK, EmptyState, NewTabMark } from "@/components/report/primitives";

/** Cómo se muestra cada veredicto de fuente. */
const SOURCE_VERDICT: Record<
  string,
  { label: string; color: string; Icon: Icon; tachado: boolean }
> = {
  verificada:     { label: "verificada",     color: "text-accent",   Icon: SealCheckIcon,   tachado: false },
  discordante:    { label: "no corresponde", color: DANGER_INK,      Icon: XCircleIcon,     tachado: true  },
  inexistente:    { label: "no existe",      color: DANGER_INK,      Icon: XCircleIcon,     tachado: true  },
  sin_pmid:       { label: "sin PMID",       color: "text-fg-muted", Icon: MinusCircleIcon, tachado: false },
  no_verificable: { label: "no verificable", color: "text-fg-muted", Icon: QuestionIcon,    tachado: false },
};

/** External link to the article, shared by both source lists. */
const SOURCE_LINK = `inline-flex shrink-0 items-center gap-1 text-xs ${TEXT_LINK}`;

/** Verdict of a source: its icon and its label, never the colour alone. */
function VerdictLabel({ status }: { status: string }) {
  const veredicto = SOURCE_VERDICT[status];
  if (!veredicto) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 align-middle text-xs font-semibold whitespace-nowrap ${veredicto.color}`}
    >
      <veredicto.Icon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
      {veredicto.label}
    </span>
  );
}

/** The title PubMed returns for the cited PMID, beside the cited one. */
function ActualTitle({ title }: { title: string }) {
  return (
    <span className="mt-1 block text-fg">
      <span className={`font-semibold ${DANGER_INK}`}>En PubMed este PMID es:</span> {title}
    </span>
  );
}

/* ── Bibliografía tab ───────────────────────────────────────────────────── */

export function BibliografiaTab({ sources }: { sources: Source[] }) {
  if (!sources.length) {
    return <EmptyState message="No hay fuentes bibliográficas registradas." />;
  }
  return (
    <ol className="divide-y divide-border rounded-2xl border border-border bg-surface">
      {sources.map((s, i) => {
        const veredicto = s.verification_status
          ? SOURCE_VERDICT[s.verification_status]
          : undefined;
        return (
          <li key={s.pmid ?? i} className="flex items-start gap-3 p-4 sm:gap-4 sm:px-6">
            <span
              aria-hidden="true"
              className="w-6 shrink-0 pt-0.5 text-right font-mono text-sm text-fg-muted"
            >
              {i + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <p className="text-sm font-semibold wrap-anywhere text-fg">
                <span className={veredicto?.tachado ? "font-normal text-fg-muted line-through" : ""}>
                  {s.title}
                </span>
                {s.verification_status && veredicto && (
                  <>
                    {" "}
                    <VerdictLabel status={s.verification_status} />
                  </>
                )}
              </p>
              {s.actual_title && (
                <p className="text-xs wrap-anywhere">
                  <ActualTitle title={s.actual_title} />
                </p>
              )}
              <p className="text-xs wrap-anywhere text-fg-muted">
                {[s.journal, s.year].filter(Boolean).join(" · ")}
                {s.pmid && <span className="ml-2 font-mono">PMID: {s.pmid}</span>}
              </p>
              {s.url && (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${SOURCE_LINK} self-start`}
                >
                  PubMed
                  <NewTabMark />
                </a>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ── Source row (dentro de hipótesis) ──────────────────────────────────── */

export function SourceRow({ source }: { source: Source }) {
  const veredicto = source.verification_status
    ? SOURCE_VERDICT[source.verification_status]
    : undefined;

  // Leading marker: the state of the source at a glance. The verdict label
  // beside the title says the same in words.
  const marker = veredicto?.tachado
    ? { Icon: XCircleIcon, color: DANGER_INK }
    : source.verified
      ? { Icon: CheckCircleIcon, color: "text-accent" }
      : { Icon: CircleIcon, color: "text-fg-muted" };

  return (
    <li className="flex items-start gap-2 text-xs text-fg-muted">
      <marker.Icon
        aria-hidden="true"
        weight="bold"
        className={`mt-0.5 size-4 shrink-0 ${marker.color}`}
      />
      <span className="min-w-0 flex-1 leading-relaxed wrap-anywhere">
        <span className={veredicto?.tachado ? "line-through" : "text-fg"}>
          {source.title}
          {source.journal && <span className="text-fg-muted"> · {source.journal}</span>}
          {source.year && <span className="text-fg-muted"> · {source.year}</span>}
          {source.pmid && <span className="font-mono text-fg-muted"> · PMID: {source.pmid}</span>}
        </span>
        {veredicto && (
          <span className={`ml-2 font-semibold whitespace-nowrap ${veredicto.color}`}>
            ({veredicto.label})
          </span>
        )}
        {/* Tipos de publicación de PubMed: son los que fijan el tope de evidencia. */}
        {source.verified && !!source.publication_types?.length && (
          <span className="mt-1 block">
            Tipo en PubMed: {source.publication_types.join(", ")}
          </span>
        )}
        {/* El título real es la prueba: el PMID existe, pero es de otra cosa. */}
        {source.actual_title && <ActualTitle title={source.actual_title} />}
      </span>
      {source.url && (
        <a href={source.url} target="_blank" rel="noopener noreferrer" className={SOURCE_LINK}>
          PubMed
          <NewTabMark />
        </a>
      )}
    </li>
  );
}
