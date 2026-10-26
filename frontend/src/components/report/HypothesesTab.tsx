import {
  CaretDoubleUpIcon,
  CaretDownIcon,
  CaretUpIcon,
  CheckCircleIcon,
  ClockIcon,
  TrendDownIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";
import type { Icon } from "@phosphor-icons/react";
import type { HypothesisStatus, RankedHypothesis } from "@/lib/types";
import { CARD } from "@/components/landing/styles";
import {
  Badge,
  DANGER_INK,
  EmptyState,
  INNER_BLOCK,
  SECTION_LABEL,
  type Tone,
} from "@/components/report/primitives";
import { SourceRow } from "@/components/report/sources";

/* ── Badges ─────────────────────────────────────────────────────────────── */

/** Priority runs on the ochre ramp, so it never reads as an evidence level. */
const PRIORITY_BADGE: Record<string, { tone: Tone; Icon: Icon }> = {
  HIGH:   { tone: "warningSolid", Icon: CaretDoubleUpIcon },
  MEDIUM: { tone: "warning",      Icon: CaretUpIcon },
  LOW:    { tone: "muted",        Icon: CaretDownIcon },
};

const PRIORITY_LABEL: Record<string, string> = {
  HIGH: "Alta", MEDIUM: "Media", LOW: "Baja",
};

/** Evidence level on the accent ramp, as the landing report card draws it. */
const EVIDENCE_BADGE: Record<string, Tone> = {
  I:   "solid",
  II:  "positive",
  III: "muted",
};

/* ── Verificación bibliográfica (Agente 04) ─────────────────────────────── */

/** Same icon and tone per status as the example report of the landing. */
const STATUS_BADGE: Record<string, { tone: Tone; Icon: Icon }> = {
  respaldada:   { tone: "positive", Icon: CheckCircleIcon },
  pendiente:    { tone: "warning",  Icon: ClockIcon },
  especulativa: { tone: "dashed",   Icon: WarningIcon },
};

const STATUS_LABEL: Record<string, string> = {
  respaldada:   "Respaldada",
  pendiente:    "Pendiente",
  especulativa: "Especulativa",
};

const STATUS_TOOLTIP: Record<string, (h: RankedHypothesis) => string> = {
  respaldada:   (h) => `${h.verified_sources} referencia(s) confirmada(s) contra PubMed`,
  pendiente:    () => "La verificación contra PubMed no pudo completarse",
  especulativa: () => "Ninguna de sus referencias se pudo confirmar contra PubMed",
};

/**
 * Grupos de la pestaña de hipótesis, en el mismo orden en que las ordena el
 * backend (backend/pipeline/evidence.py): respaldadas, pendientes, especulativas.
 */
const STATUS_GROUPS: { status: HypothesisStatus; title: string; description: string }[] = [
  {
    status: "respaldada",
    title: "Hipótesis respaldadas",
    description: "Al menos una referencia confirmada contra PubMed.",
  },
  {
    status: "pendiente",
    title: "Pendientes de verificación",
    description: "PubMed no respondió: el nivel queda en III hasta poder confirmar las fuentes.",
  },
  {
    status: "especulativa",
    title: "Hipótesis especulativas",
    description: "Ninguna referencia resistió la verificación. Se muestran, no se descartan.",
  },
];

/* ── Hipótesis tab ─────────────────────────────────────────────────────── */

/** Estado de agrupación: un status desconocido (reporte viejo) va con las especulativas. */
function groupStatus(h: RankedHypothesis): HypothesisStatus {
  return STATUS_GROUPS.some((g) => g.status === h.status) ? h.status : "especulativa";
}

export function HipotesisTab({ hypotheses }: { hypotheses: RankedHypothesis[] }) {
  if (!hypotheses.length) {
    return <EmptyState message="No se generaron hipótesis." />;
  }
  return (
    <div className="flex flex-col gap-12">
      {STATUS_GROUPS.map((group) => {
        const items = hypotheses.filter((h) => groupStatus(h) === group.status);
        if (!items.length) return null;
        const GroupIcon = STATUS_BADGE[group.status].Icon;
        return (
          <section key={group.status} className="flex flex-col gap-4">
            <div className="border-b border-border pb-3">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-fg">
                <GroupIcon aria-hidden="true" weight="bold" className="size-5 shrink-0 text-fg-muted" />
                <span>
                  {group.title}{" "}
                  <span className="font-mono text-sm text-fg-muted">({items.length})</span>
                </span>
              </h2>
              <p className="mt-1 text-sm text-pretty text-fg-muted">{group.description}</p>
            </div>
            <div className="flex flex-col gap-4">
              {items.map((h) => (
                <HypothesisCard key={h.rank} h={h} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function HypothesisCard({ h }: { h: RankedHypothesis }) {
  const topeada =
    !!h.declared_evidence_level && h.declared_evidence_level !== h.evidence_level;

  // Un agente puede sostener la hipótesis y además objetarla. Se lo muestra una
  // sola vez, con reservas, y sale de las otras dos listas. Un reporte sin el
  // campo se trata como lista vacía y se renderiza como antes.
  const conReservas = h.agents_with_reservations ?? [];
  const sostienen = h.supporting_agents.filter((ag) => !conReservas.includes(ag));
  const objetan = (h.refuting_agents ?? []).filter((ag) => !conReservas.includes(ag));

  const status = STATUS_BADGE[h.status];
  const priority = PRIORITY_BADGE[h.priority];

  return (
    <article className={`${CARD} flex flex-col gap-4`}>
      {/* Rank + título + badges */}
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-8 min-w-8 shrink-0 items-center justify-center rounded-full bg-accent px-2 font-mono text-sm font-bold text-accent-fg">
          #{h.rank}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <p className="text-lg font-semibold text-pretty wrap-anywhere text-fg">{h.text}</p>
          <div className="flex flex-wrap gap-2">
            {h.status && (
              <Badge
                tone={status?.tone ?? "neutral"}
                Icon={status?.Icon}
                title={STATUS_TOOLTIP[h.status]?.(h)}
              >
                {STATUS_LABEL[h.status] ?? h.status}
              </Badge>
            )}
            <Badge tone={priority?.tone ?? "neutral"} Icon={priority?.Icon}>
              Prioridad {PRIORITY_LABEL[h.priority] ?? h.priority}
            </Badge>
            <Badge
              tone={EVIDENCE_BADGE[h.evidence_level] ?? "neutral"}
              title={h.evidence_note || undefined}
            >
              Evidencia nivel <span className="font-mono">{h.evidence_level}</span>
              {topeada && (
                <span className="ml-1 font-normal">
                  (el agente declaró <span className="font-mono">{h.declared_evidence_level}</span>)
                </span>
              )}
            </Badge>
            {sostienen.map((ag) => (
              <Badge key={ag} tone="neutral">
                Agente <span className="font-mono">{ag}</span>
              </Badge>
            ))}
            {conReservas.map((ag) => (
              <Badge
                key={`res-${ag}`}
                tone="warning"
                title="Este agente aportó una hipótesis equivalente y además mantiene una objeción sin resolver"
              >
                Sostiene con reservas: <span className="font-mono">{ag}</span>
              </Badge>
            ))}
            {objetan.map((ag) => (
              <Badge
                key={`ref-${ag}`}
                tone="danger"
                title="Este agente objetó la hipótesis y no incorporó la crítica"
              >
                Objeta: <span className="font-mono">{ag}</span>
              </Badge>
            ))}
            {h.recitation === "mejorada" && (
              <Badge
                tone="positive"
                title="Se le pidió volver a citar sobre la literatura recuperada y consiguió respaldo verificable"
              >
                Recitada: consiguió respaldo
              </Badge>
            )}
            {h.recitation === "sin_cambio" && (
              <Badge
                tone="neutral"
                title="Se le pidió volver a citar sobre la literatura recuperada y siguió sin respaldo verificable"
              >
                Recitada: sin respaldo
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Veredicto del Árbitro (Agente 04) */}
      {h.arbiter_note && (
        <div className="rounded-lg border-l-4 border-accent bg-bg-subtle p-4">
          <p className="mb-1 text-xs font-semibold text-accent">Veredicto del Árbitro</p>
          <p className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg">
            {h.arbiter_note}
          </p>
        </div>
      )}

      {/* Objeciones que quedaron abiertas al cerrar el debate */}
      {(h.contradictions ?? []).length > 0 && (
        <div className="rounded-lg border border-(color:--landing-danger)/40 bg-(--landing-danger)/10 p-4">
          <p className={`mb-2 inline-flex items-center gap-1 text-xs font-semibold ${DANGER_INK}`}>
            <WarningIcon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
            Objeciones sin resolver
          </p>
          <ul className="flex flex-col gap-2">
            {(h.contradictions ?? []).map((c, i) => (
              <li key={i} className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg">
                <span className="font-semibold">{c.from_agent_name}</span>{" "}
                <span className={`font-mono text-xs font-semibold ${DANGER_INK}`}>
                  [{c.severity}]
                </span>{" "}
                {c.critique_text}
                {c.alternative && (
                  <span className="mt-0.5 block text-xs text-fg-muted">
                    Alternativa sugerida: {c.alternative}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Justificación */}
      <div className={INNER_BLOCK}>
        <p className={`mb-1 ${SECTION_LABEL}`}>Justificación</p>
        <p className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg">{h.rationale}</p>
      </div>

      {/* Por qué quedó con este nivel de evidencia */}
      {h.evidence_note && (
        <p
          className={`flex items-start gap-2 text-xs leading-relaxed text-pretty ${topeada ? "text-ochre" : "text-fg-muted"}`}
        >
          {/* A lowered level is marked with an icon, not only with the ochre. */}
          {topeada && (
            <TrendDownIcon aria-hidden="true" weight="bold" className="mt-0.5 size-4 shrink-0" />
          )}
          <span className="min-w-0 wrap-anywhere">
            <span className="font-semibold">Nivel de evidencia:</span> {h.evidence_note}
          </span>
        </p>
      )}

      {/* Fuentes de la hipótesis */}
      {h.sources.length > 0 && (
        <div>
          <p className={`mb-2 ${SECTION_LABEL}`}>Fuentes</p>
          <ul className="flex flex-col gap-2">
            {h.sources.map((s, i) => (
              <SourceRow key={s.pmid ?? i} source={s} />
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
