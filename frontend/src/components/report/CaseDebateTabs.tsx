import { CheckCircleIcon, WarningIcon } from "@phosphor-icons/react/ssr";
import type { AgentProviderInfo, CaseSummarySection, DebateSummary } from "@/lib/types";
import { CARD } from "@/components/landing/styles";
import { BulletList, Notice, SECTION_LABEL } from "@/components/report/primitives";

/* ── Caso tab ───────────────────────────────────────────────────────────── */

export function CasoTab({ summary }: { summary: CaseSummarySection }) {
  return (
    <div className="flex flex-col gap-4">
      <div className={CARD}>
        <p className={`mb-3 ${SECTION_LABEL}`}>Narrativa clínica</p>
        <p className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg">
          {summary.narrative}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {summary.patient_profile && (
          <InfoCard label="Perfil del paciente" value={summary.patient_profile} />
        )}
        {summary.chief_complaint && (
          <InfoCard label="Motivo de consulta" value={summary.chief_complaint} />
        )}
        {summary.disease_duration && (
          <InfoCard label="Duración de la enfermedad" value={summary.disease_duration} />
        )}
      </div>

      {summary.current_treatments && summary.current_treatments.length > 0 && (
        <ListCard label="Tratamientos actuales" items={summary.current_treatments} />
      )}
      {summary.relevant_history && summary.relevant_history.length > 0 && (
        <ListCard label="Antecedentes relevantes" items={summary.relevant_history} />
      )}
      {summary.procedures_done && summary.procedures_done.length > 0 && (
        <ListCard label="Procedimientos realizados" items={summary.procedures_done} />
      )}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className={`${CARD} min-w-0`}>
      <p className={`mb-1 ${SECTION_LABEL}`}>{label}</p>
      <p className="text-sm text-pretty wrap-anywhere text-fg">{value}</p>
    </div>
  );
}

function ListCard({ label, items }: { label: string; items: string[] }) {
  return (
    <div className={CARD}>
      <p className={`mb-3 ${SECTION_LABEL}`}>{label}</p>
      <BulletList items={items} />
    </div>
  );
}

/* ── Debate tab ─────────────────────────────────────────────────────────── */

interface DebateTabProps {
  debate: DebateSummary;
  /** Who answered for each agent; absent in reports older than the field. */
  providers?: AgentProviderInfo[] | null;
}

export function DebateTab({ debate, providers }: DebateTabProps) {
  return (
    <div className="flex flex-col gap-4">
      {/* Stats */}
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Rondas",       value: String(debate.rounds_completed) },
          { label: "Críticas",     value: String(debate.total_critiques) },
          { label: "Divergencias", value: String(debate.divergences.length) },
          { label: "Consenso",     value: debate.consensus_reached ? "Sí" : "No" },
        ].map(({ label, value }) => (
          <div key={label} className={`${CARD} flex min-w-0 flex-col-reverse text-center`}>
            <dt className="mt-1 text-xs text-fg-muted">{label}</dt>
            <dd className="font-mono text-2xl font-semibold text-fg">{value}</dd>
          </div>
        ))}
      </dl>

      {/* Consenso */}
      <Notice
        tone={debate.consensus_reached ? "positive" : "warning"}
        Icon={debate.consensus_reached ? CheckCircleIcon : WarningIcon}
      >
        <span className="font-semibold">
          {debate.consensus_reached
            ? "Consenso alcanzado — ninguna hipótesis de alta prioridad fue rechazada por los agentes."
            : "Divergencias de alta prioridad — revisá las hipótesis marcadas con cautela."}
        </span>
      </Notice>

      {/* Divergencias */}
      {debate.divergences.length > 0 && (
        <div className={CARD}>
          <p className={`mb-3 ${SECTION_LABEL}`}>Divergencias identificadas</p>
          <ul className="flex flex-col gap-2">
            {debate.divergences.map((d, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-fg">
                <WarningIcon
                  aria-hidden="true"
                  weight="bold"
                  className="mt-0.5 size-4 shrink-0 text-ochre"
                />
                <span className="min-w-0 text-pretty wrap-anywhere">{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {providers && providers.length > 0 && <ProvidersCard providers={providers} />}
    </div>
  );
}

/* ── Models that answered ───────────────────────────────────────────────── */

const PROVIDER_NAME: Record<string, string> = {
  groq: "Groq",
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
};

const FALLBACK_NOTE: Record<string, string> = {
  clave_faltante: "Respaldo en Groq: faltaba la clave del proveedor asignado",
  falla: "Respaldo en Groq: el proveedor asignado falló",
};

/**
 * Provider and model that answered for each agent. A fallback is told in
 * words and with an icon, never by colour alone.
 */
export function ProvidersCard({ providers }: { providers: AgentProviderInfo[] }) {
  return (
    <div className={CARD}>
      <p className={`mb-3 ${SECTION_LABEL}`}>Modelos que respondieron</p>
      <ul className="flex flex-col gap-3">
        {providers.map((p) => {
          const note = p.fallback_reason ? FALLBACK_NOTE[p.fallback_reason] : null;
          return (
            <li
              key={`${p.agent_id}-${p.provider}-${p.model}-${p.fallback_reason ?? ""}`}
              className="flex flex-col gap-1 text-sm text-fg sm:flex-row sm:items-baseline sm:gap-3"
            >
              <span className="min-w-0 font-semibold wrap-anywhere sm:w-56 sm:shrink-0">
                {p.agent_id}
                {p.agent_name ? ` — ${p.agent_name}` : ""}
              </span>
              <span className="min-w-0 wrap-anywhere">
                {PROVIDER_NAME[p.provider] ?? p.provider}{" "}
                <span className="font-mono text-fg-muted">{p.model}</span>
              </span>
              {note && (
                <span className="flex min-w-0 items-start gap-1.5 text-ochre">
                  <WarningIcon aria-hidden="true" weight="bold" className="mt-0.5 size-4 shrink-0" />
                  <span className="wrap-anywhere">{note}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
