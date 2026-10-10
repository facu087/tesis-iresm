import {
  CheckCircleIcon,
  CircleDashedIcon,
  CircleHalfIcon,
  CircleIcon,
  HourglassIcon,
  InfoIcon,
  MapPinIcon,
  UsersThreeIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";
import type { Icon } from "@phosphor-icons/react";
import type {
  ClinicalTrial,
  Compatibility,
  RareDiseaseMatch,
  StructuredReport,
  TrialSearchSummary,
} from "@/lib/types";
import { CARD, FOCUS_RING, TEXT_LINK, TRANSITION } from "@/components/landing/styles";
import {
  Badge,
  BulletList,
  EmptyState,
  INNER_BLOCK,
  NewTabMark,
  Notice,
  SECTION_LABEL,
  type Tone,
} from "@/components/report/primitives";

/* ── Ensayos tab (Agente 05) ────────────────────────────────────────────── */

const COMPATIBILITY_BADGE: Record<Compatibility, { tone: Tone; Icon: Icon }> = {
  alta:        { tone: "positive", Icon: CheckCircleIcon },
  media:       { tone: "warning",  Icon: CircleHalfIcon },
  baja:        { tone: "muted",    Icon: CircleIcon },
  sin_evaluar: { tone: "dashed",   Icon: CircleDashedIcon },
};

const COMPATIBILITY_LABEL: Record<Compatibility, string> = {
  alta:        "Compatibilidad alta",
  media:       "Compatibilidad media",
  baja:        "Compatibilidad baja",
  sin_evaluar: "Sin evaluar",
};

/** Aclaración fija: la misma que imprime el PDF. */
const TRIAL_DISCLAIMER =
  "La compatibilidad es orientativa: la elegibilidad la determina el equipo investigador de cada ensayo.";

/** Outlined pill link to the trial record. */
const TRIAL_LINK = `inline-flex shrink-0 items-center gap-2 self-start rounded-full border border-fg-muted px-3 py-2 text-sm font-semibold text-fg ${TRANSITION} hover:border-accent hover:text-accent active:scale-[0.98] ${FOCUS_RING}`;

/** Argentina ordena el resultado; nunca filtra. La comparación es normalizada. */
function tieneSedeEnArgentina(t: ClinicalTrial): boolean {
  return t.locations.some(
    (pais) =>
      pais
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .trim() === "argentina",
  );
}

/** Avisos de estado: distinguen "no hay ensayos" de "no se pudo consultar". */
function avisosDeBusqueda(s: TrialSearchSummary): string[] {
  const avisos: string[] = [];
  if (s.estado_clinicaltrials === "no_disponible") {
    avisos.push("ClinicalTrials.gov no se pudo consultar");
  } else if (s.estado_clinicaltrials === "parcial") {
    avisos.push("algunas consultas a ClinicalTrials.gov fallaron");
  }
  if (s.estado_orphanet === "no_disponible") {
    avisos.push("Orphanet no se pudo consultar");
  } else if (s.estado_orphanet === "parcial") {
    avisos.push("algunas consultas a Orphanet fallaron");
  }
  if (s.evaluacion === "fallback") {
    avisos.push("la evaluación de compatibilidad no se pudo completar");
  }
  return avisos;
}

export function EnsayosTab({ report }: { report: StructuredReport }) {
  // `trial_search` nulo = reporte anterior al Agente 05: se muestra como antes.
  const busqueda = report.trial_search ?? null;
  const trials = report.clinical_trials;
  const raras = report.rare_diseases ?? [];
  const avisos = busqueda ? avisosDeBusqueda(busqueda) : [];

  return (
    <div className="flex flex-col gap-4">
      {avisos.length > 0 && (
        <Notice tone="warning" Icon={WarningIcon} label="Estado de la búsqueda:">
          {avisos.join("; ")}.
        </Notice>
      )}

      {busqueda && trials.length > 0 && (
        <p className="flex items-start gap-2 text-sm text-pretty text-fg-muted">
          <InfoIcon aria-hidden="true" weight="bold" className="mt-0.5 size-4 shrink-0 text-ochre" />
          {TRIAL_DISCLAIMER}
        </p>
      )}

      {raras.length > 0 && <RareDiseasesCard matches={raras} />}

      {trials.length === 0 ? (
        <EmptyState
          message={
            busqueda?.estado_clinicaltrials === "no_disponible"
              ? "No se pudo consultar ClinicalTrials.gov: esto no significa que no existan ensayos relacionados."
              : "No se encontraron ensayos clínicos activos relacionados al caso."
          }
        />
      ) : (
        trials.map((t) => <TrialCard key={t.nct_id} t={t} evaluado={!!busqueda} />)
      )}
    </div>
  );
}

function RareDiseasesCard({ matches }: { matches: RareDiseaseMatch[] }) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-bg-subtle p-6">
      <div>
        <p className="text-base font-semibold text-fg">
          Enfermedades raras relacionadas (Orphanet)
        </p>
        <p className="mt-1 text-sm text-pretty text-fg-muted">
          Hipótesis de investigación que corresponden a una enfermedad rara catalogada.
          No son diagnósticos del paciente.
        </p>
      </div>
      <ul className="flex flex-col gap-3">
        {matches.map((m) => (
          <li key={`${m.orpha_code}-${m.hypothesis}`} className="min-w-0 text-sm text-fg">
            <a
              href={m.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`inline-flex items-start gap-1 wrap-anywhere ${TEXT_LINK}`}
            >
              <span>
                <span className="font-mono">ORPHA:{m.orpha_code}</span> — {m.name}
              </span>
              <span className="mt-0.5 inline-flex shrink-0">
                <NewTabMark />
              </span>
            </a>
            <span className="mt-0.5 block text-xs wrap-anywhere text-fg-muted">
              Hipótesis: {m.hypothesis}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TrialCard({ t, evaluado }: { t: ClinicalTrial; evaluado: boolean }) {
  const compatibilidad: Compatibility = t.compatibility ?? "sin_evaluar";
  const criterios = t.criteria_to_verify ?? [];
  const hipotesis = t.related_hypotheses ?? [];

  return (
    <article className={`${CARD} flex flex-col gap-4`}>
      {/* Título + badges + link */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <p className="text-lg font-semibold text-pretty wrap-anywhere text-fg">{t.title}</p>
          <div className="flex flex-wrap gap-2">
            {evaluado && (
              <Badge
                tone={COMPATIBILITY_BADGE[compatibilidad].tone}
                Icon={COMPATIBILITY_BADGE[compatibilidad].Icon}
              >
                {COMPATIBILITY_LABEL[compatibilidad]}
              </Badge>
            )}
            <Badge tone="neutral">
              <span className="font-mono">{t.nct_id}</span>
            </Badge>
            {/* Advertencia, no badge de calidad: el ensayo todavía no abrió. */}
            {t.status === "NOT_YET_RECRUITING" ? (
              <Badge tone="warning" Icon={HourglassIcon}>
                Aún no recluta
              </Badge>
            ) : t.status === "RECRUITING" ? (
              <Badge tone="positive" Icon={UsersThreeIcon}>
                {t.status}
              </Badge>
            ) : (
              <Badge tone="neutral">{t.status}</Badge>
            )}
            {tieneSedeEnArgentina(t) && (
              <Badge tone="positive" Icon={MapPinIcon}>
                Sede en Argentina
              </Badge>
            )}
            {t.phase && <Badge tone="neutral">{t.phase}</Badge>}
          </div>
        </div>
        <a href={t.url} target="_blank" rel="noopener noreferrer" className={TRIAL_LINK}>
          ClinicalTrials
          <NewTabMark />
        </a>
      </div>

      {/* Resumen */}
      <p className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg-muted">
        {t.brief_summary}
      </p>

      {/* Fundamento de la compatibilidad */}
      {evaluado && t.compatibility_rationale && (
        <div className={INNER_BLOCK}>
          <p className={`mb-1 ${SECTION_LABEL}`}>Por qué</p>
          <p className="text-sm leading-relaxed text-pretty wrap-anywhere text-fg">
            {t.compatibility_rationale}
          </p>
        </div>
      )}

      {/* Criterios a verificar */}
      {evaluado && criterios.length > 0 && (
        <div>
          <p className={`mb-2 ${SECTION_LABEL}`}>Criterios a verificar</p>
          <BulletList items={criterios} />
        </div>
      )}

      {/* Hipótesis que trajeron este ensayo */}
      {evaluado && hipotesis.length > 0 && (
        <p className="text-xs text-pretty wrap-anywhere text-fg-muted">
          <strong className="font-semibold text-fg">Hipótesis relacionadas:</strong>{" "}
          {hipotesis.join(" · ")}
        </p>
      )}

      {/* Metadatos */}
      <div className="grid gap-x-8 gap-y-1 text-xs text-fg-muted sm:grid-cols-2 [&>span]:min-w-0 [&>span]:wrap-anywhere [&_strong]:font-semibold [&_strong]:text-fg">
        {t.conditions.length > 0 && (
          <span>
            <strong>Condiciones:</strong> {t.conditions.join(", ")}
          </span>
        )}
        {t.sponsor && (
          <span>
            <strong>Patrocinador:</strong> {t.sponsor}
          </span>
        )}
        {t.start_date && (
          <span>
            <strong>Inicio:</strong> {t.start_date}
          </span>
        )}
        {t.completion_date && (
          <span>
            <strong>Fin estimado:</strong> {t.completion_date}
          </span>
        )}
        {(t.min_age || t.max_age) && (
          <span>
            <strong>Edad:</strong> {t.min_age ?? "?"} – {t.max_age ?? "?"}
          </span>
        )}
        {t.sex && (
          <span>
            <strong>Sexo:</strong> {t.sex}
          </span>
        )}
        {t.locations.length > 0 && (
          <span className="sm:col-span-2">
            <strong>Sedes:</strong>{" "}
            {t.locations.slice(0, 3).join(" · ")}
            {t.locations.length > 3 && ` +${t.locations.length - 3} más`}
          </span>
        )}
      </div>
    </article>
  );
}
