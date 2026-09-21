"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { downloadPdf } from "@/lib/api";
import type {
  ArbitrationSummary,
  StructuredReport,
  RankedHypothesis,
  ClinicalTrial,
  CaseSummarySection,
  Compatibility,
  DebateSummary,
  HypothesisStatus,
  RareDiseaseMatch,
  Source,
  TrialSearchSummary,
  VerificationSummary,
} from "@/lib/types";

type Tab = "hipotesis" | "caso" | "debate" | "ensayos" | "bibliografia";

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<StructuredReport | null>(null);
  const [tab, setTab] = useState<Tab>("hipotesis");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem("nexus_report");
    if (!stored) { router.replace("/"); return; }
    setReport(JSON.parse(stored) as StructuredReport);
  }, [router]);

  const handleDownload = async () => {
    if (!report) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const blob = await downloadPdf(report);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nexus-reporte-${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("No se pudo generar el PDF. Verificá que el backend esté activo.");
    } finally {
      setDownloading(false);
    }
  };

  if (!report) return null;

  const generatedAt = new Date(report.metadata.generated_at).toLocaleString("es-AR");

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "hipotesis",   label: "Hipótesis",        count: report.hypotheses.length },
    { id: "caso",        label: "Caso clínico" },
    { id: "debate",      label: "Debate" },
    { id: "ensayos",     label: "Ensayos clínicos", count: report.clinical_trials.length },
    { id: "bibliografia",label: "Bibliografía",      count: report.bibliography.length },
  ];

  return (
    <div className="min-h-screen flex flex-col">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold">NEXUS</span>
          <span className="text-slate-500 text-sm">·</span>
          <span className="text-slate-400 text-sm hidden sm:inline">Reporte de análisis</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/")}
            className="rounded-lg border border-slate-700 px-4 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-white transition-colors"
          >
            Nuevo análisis
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="rounded-lg bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-50 transition-colors"
          >
            {downloading ? "Generando…" : "↓ Descargar PDF"}
          </button>
        </div>
      </header>

      {/* ── Meta bar ────────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-5xl px-6 py-4 flex flex-wrap items-center gap-6 text-sm">
          <MetaStat label="Hipótesis" value={String(report.hypotheses.length)} />
          <MetaStat label="Tiempo" value={`${report.metadata.processing_time_seconds.toFixed(1)} s`} />
          <MetaStat label="Ensayos" value={String(report.clinical_trials.length)} />
          <MetaStat
            label="Fuentes"
            value={
              report.verification?.total_fuentes
                ? `${report.verification.verificadas}/${report.verification.total_fuentes} verificadas`
                : String(report.bibliography.length)
            }
          />
          <MetaStat label="Generado" value={generatedAt} />
          <span className="ml-auto text-xs text-slate-400">
            NEXUS {report.metadata.nexus_version}
          </span>
        </div>
      </div>

      {/* ── Disclaimer ──────────────────────────────────────────────────── */}
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="mx-auto max-w-5xl px-6 py-2.5 text-xs text-amber-700">
          ⚠ {report.metadata.disclaimer}
        </div>
      </div>

      {/* ── Verificación bibliográfica ──────────────────────────────────── */}
      {report.verification && <VerificationBanner v={report.verification} />}
      {report.arbitration && <ArbitrationBanner a={report.arbitration} />}

      {/* ── PDF error ───────────────────────────────────────────────────── */}
      {downloadError && (
        <div className="bg-red-50 border-b border-red-200">
          <div className="mx-auto max-w-5xl px-6 py-2.5 text-xs text-red-700 flex items-center justify-between">
            {downloadError}
            <button onClick={() => setDownloadError(null)} className="ml-4 underline">
              Cerrar
            </button>
          </div>
        </div>
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-slate-200 sticky top-[60px] z-10">
        <div className="mx-auto max-w-5xl px-6 flex gap-1 overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === t.id
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
              {t.count !== undefined && (
                <span className={`rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                  tab === t.id
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}>
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <main className="flex-1 bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-8">
          {tab === "hipotesis"    && <HipotesisTab    hypotheses={report.hypotheses} />}
          {tab === "caso"         && <CasoTab         summary={report.case_summary} />}
          {tab === "debate"       && <DebateTab        debate={report.debate_summary} />}
          {tab === "ensayos"      && <EnsayosTab       report={report} />}
          {tab === "bibliografia" && <BibliografiaTab  sources={report.bibliography} />}
        </div>
      </main>

    </div>
  );
}

/* ── Meta stat ─────────────────────────────────────────────────────────── */

function MetaStat({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-slate-500">
      {label}:{" "}
      <span className="font-semibold text-slate-700">{value}</span>
    </span>
  );
}

/* ── Badges ─────────────────────────────────────────────────────────────── */

const PRIORITY_BADGE: Record<string, string> = {
  HIGH:   "bg-red-100 text-red-700 ring-1 ring-red-200",
  MEDIUM: "bg-amber-100 text-amber-700 ring-1 ring-amber-200",
  LOW:    "bg-blue-100 text-blue-700 ring-1 ring-blue-200",
};

const PRIORITY_LABEL: Record<string, string> = {
  HIGH: "Alta", MEDIUM: "Media", LOW: "Baja",
};

const EVIDENCE_BADGE: Record<string, string> = {
  I:   "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
  II:  "bg-orange-100 text-orange-700 ring-1 ring-orange-200",
  III: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
};

/* ── Verificación bibliográfica (Agente 04) ─────────────────────────────── */

const STATUS_BADGE: Record<string, string> = {
  respaldada:   "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
  pendiente:    "bg-sky-100 text-sky-700 ring-1 ring-sky-200",
  especulativa: "bg-amber-100 text-amber-800 ring-1 ring-amber-300",
};

const STATUS_LABEL: Record<string, string> = {
  respaldada:   "✓ Respaldada",
  pendiente:    "? Pendiente",
  especulativa: "⚠ Especulativa",
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

/** Cómo se muestra cada veredicto de fuente. */
const SOURCE_VERDICT: Record<string, { label: string; color: string; tachado: boolean }> = {
  verificada:     { label: "verificada",       color: "text-emerald-600", tachado: false },
  discordante:    { label: "no corresponde",   color: "text-red-600",     tachado: true  },
  inexistente:    { label: "no existe",        color: "text-red-600",     tachado: true  },
  sin_pmid:       { label: "sin PMID",         color: "text-slate-400",   tachado: false },
  no_verificable: { label: "no verificable",   color: "text-slate-400",   tachado: false },
};

/**
 * Aviso de cabecera con el resultado de la verificación.
 *
 * Sin esto, un lector ve la referencia citada y asume que es buena: la
 * contradicción queda en el dato y no llega a la pantalla.
 */
function ArbitrationBanner({ a }: { a: ArbitrationSummary }) {
  if (a.status === "sin_hipotesis") return null;

  const degradado = a.status === "degradado";
  const consolido = a.consensus_hypotheses < a.input_hypotheses;
  const r = a.recitation;

  return (
    <div className={degradado ? "bg-amber-50 border-b border-amber-200" : "bg-indigo-50 border-b border-indigo-200"}>
      <div className={`mx-auto max-w-5xl px-6 py-2.5 text-xs ${degradado ? "text-amber-800" : "text-indigo-800"}`}>
        <span className="font-semibold">Árbitro:</span>{" "}
        {degradado ? (
          <>
            el arbitraje no se pudo completar: las {a.input_hypotheses} hipótesis se
            muestran sin consolidar, como las entregó el debate.
          </>
        ) : (
          <>
            {consolido ? (
              <>
                las {a.input_hypotheses} hipótesis del debate se consolidaron en{" "}
                {a.consensus_hypotheses}.
              </>
            ) : (
              <>las {a.consensus_hypotheses} hipótesis del debate son distintas entre sí.</>
            )}
            {a.contradictions > 0 && (
              <> {a.contradictions} objeción{a.contradictions === 1 ? "" : "es"} quedó sin resolver.</>
            )}
          </>
        )}
        {a.cited_sources > 0 && a.retrieved_articles > 0 && (
          <>
            {" "}Solo {a.rag_overlap} de las {a.cited_sources} referencias citadas salieron de
            los {a.retrieved_articles} artículos que se les recuperó de PubMed.
          </>
        )}
        {r?.executed && (
          <>
            {" "}Se les pidió volver a citar {r.recited} hipótesis sobre literatura real:{" "}
            {r.improved} consiguió respaldo verificable.
            {r.rejected_pmids > 0 && (
              <> Se descartaron {r.rejected_pmids} referencias que volvieron a inventar.</>
            )}
          </>
        )}
        <span className="block mt-0.5 text-[11px] opacity-80">
          El consenso es entre agentes de inteligencia artificial: no es un diagnóstico
          ni una recomendación clínica.
        </span>
      </div>
    </div>
  );
}

function VerificationBanner({ v }: { v: VerificationSummary }) {
  if (!v.total_fuentes) return null;

  const sospechosas = v.discordantes + v.inexistentes;
  const hayProblema = sospechosas > 0;
  const pendientes = v.hipotesis_pendientes ?? 0;
  const topeadas = v.hipotesis_topeadas ?? 0;
  const totalHipotesis = v.hipotesis_respaldadas + pendientes + v.hipotesis_especulativas;

  return (
    <div className={hayProblema ? "bg-red-50 border-b border-red-200" : "bg-emerald-50 border-b border-emerald-200"}>
      <div className={`mx-auto max-w-5xl px-6 py-2.5 text-xs ${hayProblema ? "text-red-700" : "text-emerald-700"}`}>
        <span className="font-semibold">Verificación bibliográfica:</span>{" "}
        {hayProblema ? (
          <>
            {sospechosas} de {v.total_fuentes} referencias citadas no se pudieron confirmar
            contra PubMed{v.discordantes > 0 && <> ({v.discordantes} apuntan a otro artículo)</>}.
            {" "}{v.hipotesis_especulativas} de {totalHipotesis} hipótesis quedan como especulativas.
          </>
        ) : (
          <>
            {v.verificadas} de {v.total_fuentes} referencias confirmadas contra PubMed.
          </>
        )}
        {v.no_verificables > 0 && (
          <> {v.no_verificables} no se pudieron consultar (fallo de red): no se invalidan.</>
        )}
        {pendientes > 0 && (
          <> {pendientes} de {totalHipotesis} hipótesis quedan pendientes de verificación.</>
        )}
        {topeadas > 0 && (
          <> A {topeadas} hipótesis se les bajó el nivel de evidencia declarado por el agente.</>
        )}
      </div>
    </div>
  );
}

/* ── Hipótesis tab ─────────────────────────────────────────────────────── */

/** Estado de agrupación: un status desconocido (reporte viejo) va con las especulativas. */
function groupStatus(h: RankedHypothesis): HypothesisStatus {
  return STATUS_GROUPS.some((g) => g.status === h.status) ? h.status : "especulativa";
}

function HipotesisTab({ hypotheses }: { hypotheses: RankedHypothesis[] }) {
  if (!hypotheses.length) {
    return <EmptyState message="No se generaron hipótesis." />;
  }
  return (
    <div className="space-y-8">
      {STATUS_GROUPS.map((group) => {
        const items = hypotheses.filter((h) => groupStatus(h) === group.status);
        if (!items.length) return null;
        return (
          <section key={group.status} className="space-y-4">
            <div className="flex items-baseline justify-between gap-3 border-b border-slate-200 pb-2">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">
                  {group.title} <span className="text-slate-400">({items.length})</span>
                </h2>
                <p className="text-xs text-slate-500">{group.description}</p>
              </div>
            </div>
            <div className="space-y-5">
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

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
      {/* Rank + título + badges */}
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-bold text-white mt-0.5">
          #{h.rank}
        </span>
        <div className="flex-1 space-y-2">
          <p className="text-base font-semibold text-slate-900 leading-snug">
            {h.text}
          </p>
          <div className="flex flex-wrap gap-2">
            {h.status && (
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_BADGE[h.status] ?? ""}`}
                title={STATUS_TOOLTIP[h.status]?.(h)}
              >
                {STATUS_LABEL[h.status] ?? h.status}
              </span>
            )}
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${PRIORITY_BADGE[h.priority] ?? ""}`}>
              Prioridad {PRIORITY_LABEL[h.priority] ?? h.priority}
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${EVIDENCE_BADGE[h.evidence_level] ?? ""}`}
              title={h.evidence_note || undefined}
            >
              Evidencia nivel {h.evidence_level}
              {topeada && (
                <span className="ml-1 font-normal">
                  (el agente declaró {h.declared_evidence_level})
                </span>
              )}
            </span>
            {h.supporting_agents.map((ag) => (
              <span key={ag} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500">
                Agente {ag}
              </span>
            ))}
            {(h.refuting_agents ?? []).map((ag) => (
              <span
                key={`ref-${ag}`}
                className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs text-rose-700"
                title="Este agente objetó la hipótesis y no incorporó la crítica"
              >
                Objeta: {ag}
              </span>
            ))}
            {h.recitation === "mejorada" && (
              <span
                className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-700"
                title="Se le pidió volver a citar sobre la literatura recuperada y consiguió respaldo verificable"
              >
                Recitada: consiguió respaldo
              </span>
            )}
            {h.recitation === "sin_cambio" && (
              <span
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500"
                title="Se le pidió volver a citar sobre la literatura recuperada y siguió sin respaldo verificable"
              >
                Recitada: sin respaldo
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Veredicto del Árbitro (Agente 04) */}
      {h.arbiter_note && (
        <div className="rounded-xl border-l-4 border-indigo-300 bg-indigo-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500 mb-1">
            Veredicto del Árbitro
          </p>
          <p className="text-sm text-slate-700 leading-relaxed">{h.arbiter_note}</p>
        </div>
      )}

      {/* Objeciones que quedaron abiertas al cerrar el debate */}
      {(h.contradictions ?? []).length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-rose-600 mb-2">
            Objeciones sin resolver
          </p>
          <ul className="space-y-2">
            {(h.contradictions ?? []).map((c, i) => (
              <li key={i} className="text-sm text-slate-700 leading-relaxed">
                <span className="font-semibold">{c.from_agent_name}</span>{" "}
                <span className="text-xs font-semibold text-rose-600">[{c.severity}]</span>{" "}
                {c.critique_text}
                {c.alternative && (
                  <span className="block text-xs text-slate-500 mt-0.5">
                    Alternativa sugerida: {c.alternative}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Justificación */}
      <div className="rounded-xl bg-slate-50 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
          Justificación
        </p>
        <p className="text-sm text-slate-700 leading-relaxed">{h.rationale}</p>
      </div>

      {/* Por qué quedó con este nivel de evidencia */}
      {h.evidence_note && (
        <p className={`text-xs leading-relaxed ${topeada ? "text-orange-700" : "text-slate-500"}`}>
          <span className="font-semibold">Nivel de evidencia:</span> {h.evidence_note}
        </p>
      )}

      {/* Fuentes de la hipótesis */}
      {h.sources.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
            Fuentes
          </p>
          <ul className="space-y-1.5">
            {h.sources.map((s, i) => (
              <SourceRow key={s.pmid ?? i} source={s} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ── Caso tab ───────────────────────────────────────────────────────────── */

function CasoTab({ summary }: { summary: CaseSummarySection }) {
  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
          Narrativa clínica
        </p>
        <p className="text-sm text-slate-700 leading-relaxed">{summary.narrative}</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
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
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
        {label}
      </p>
      <p className="text-sm text-slate-700">{value}</p>
    </div>
  );
}

function ListCard({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
        {label}
      </p>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ── Debate tab ─────────────────────────────────────────────────────────── */

function DebateTab({ debate }: { debate: DebateSummary }) {
  return (
    <div className="space-y-5">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Rondas",       value: String(debate.rounds_completed) },
          { label: "Críticas",     value: String(debate.total_critiques) },
          { label: "Divergencias", value: String(debate.divergences.length) },
          { label: "Consenso",     value: debate.consensus_reached ? "Sí" : "No" },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 text-center">
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            <p className="text-xs text-slate-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Consenso */}
      <div className={`rounded-2xl border p-5 ${
        debate.consensus_reached
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50"
      }`}>
        <p className={`text-sm font-semibold ${
          debate.consensus_reached ? "text-emerald-700" : "text-amber-700"
        }`}>
          {debate.consensus_reached
            ? "✓ Consenso alcanzado — ninguna hipótesis de alta prioridad fue rechazada por los agentes."
            : "⚠ Divergencias de alta prioridad — revisá las hipótesis marcadas con cautela."}
        </p>
      </div>

      {/* Divergencias */}
      {debate.divergences.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
            Divergencias identificadas
          </p>
          <ul className="space-y-2">
            {debate.divergences.map((d, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-slate-700">
                <span className="mt-0.5 text-amber-500 shrink-0">⚠</span>
                {d}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ── Ensayos tab (Agente 05) ────────────────────────────────────────────── */

const COMPATIBILITY_BADGE: Record<Compatibility, string> = {
  alta:        "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
  media:       "bg-amber-100 text-amber-700 ring-1 ring-amber-200",
  baja:        "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
  sin_evaluar: "bg-white text-slate-400 ring-1 ring-slate-200",
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

function EnsayosTab({ report }: { report: StructuredReport }) {
  // `trial_search` nulo = reporte anterior al Agente 05: se muestra como antes.
  const busqueda = report.trial_search ?? null;
  const trials = report.clinical_trials;
  const raras = report.rare_diseases ?? [];
  const avisos = busqueda ? avisosDeBusqueda(busqueda) : [];

  return (
    <div className="space-y-5">
      {avisos.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-3 text-xs text-amber-800">
          <span className="font-semibold">Estado de la búsqueda:</span>{" "}
          {avisos.join("; ")}.
        </div>
      )}

      {busqueda && trials.length > 0 && (
        <p className="text-xs text-slate-500">⚠ {TRIAL_DISCLAIMER}</p>
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
    <div className="rounded-2xl border border-violet-200 bg-violet-50 p-6 space-y-3">
      <div>
        <p className="text-sm font-semibold text-violet-900">
          Enfermedades raras relacionadas (Orphanet)
        </p>
        <p className="text-xs text-violet-700">
          Hipótesis de investigación que corresponden a una enfermedad rara catalogada.
          No son diagnósticos del paciente.
        </p>
      </div>
      <ul className="space-y-2">
        {matches.map((m) => (
          <li key={`${m.orpha_code}-${m.hypothesis}`} className="text-sm text-slate-700">
            <a
              href={m.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-violet-800 hover:underline"
            >
              ORPHA:{m.orpha_code} — {m.name} ↗
            </a>
            <span className="block text-xs text-slate-500">
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
    <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
      {/* Título + badges + link */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 flex-1">
          <p className="text-base font-semibold text-slate-900 leading-snug">
            {t.title}
          </p>
          <div className="flex flex-wrap gap-2">
            {evaluado && (
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${COMPATIBILITY_BADGE[compatibilidad]}`}
              >
                {COMPATIBILITY_LABEL[compatibilidad]}
              </span>
            )}
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-mono text-slate-600">
              {t.nct_id}
            </span>
            {/* Advertencia, no badge de calidad: el ensayo todavía no abrió. */}
            {t.status === "NOT_YET_RECRUITING" ? (
              <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700 ring-1 ring-orange-200">
                ⏳ Aún no recluta
              </span>
            ) : (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                t.status === "RECRUITING"
                  ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200"
                  : "bg-slate-100 text-slate-600"
              }`}>
                {t.status}
              </span>
            )}
            {tieneSedeEnArgentina(t) && (
              <span className="rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">
                📍 Sede en Argentina
              </span>
            )}
            {t.phase && (
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700 ring-1 ring-blue-100">
                {t.phase}
              </span>
            )}
          </div>
        </div>
        <a
          href={t.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          ClinicalTrials ↗
        </a>
      </div>

      {/* Resumen */}
      <p className="text-sm text-slate-600 leading-relaxed">{t.brief_summary}</p>

      {/* Fundamento de la compatibilidad */}
      {evaluado && t.compatibility_rationale && (
        <div className="rounded-xl bg-slate-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
            Por qué
          </p>
          <p className="text-sm text-slate-700 leading-relaxed">
            {t.compatibility_rationale}
          </p>
        </div>
      )}

      {/* Criterios a verificar */}
      {evaluado && criterios.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
            Criterios a verificar
          </p>
          <ul className="space-y-1.5">
            {criterios.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Hipótesis que trajeron este ensayo */}
      {evaluado && hipotesis.length > 0 && (
        <p className="text-xs text-slate-500">
          <strong>Hipótesis relacionadas:</strong> {hipotesis.join(" · ")}
        </p>
      )}

      {/* Metadatos */}
      <div className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-xs text-slate-500">
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
    </div>
  );
}

/* ── Bibliografía tab ───────────────────────────────────────────────────── */

function BibliografiaTab({ sources }: { sources: Source[] }) {
  if (!sources.length) {
    return <EmptyState message="No hay fuentes bibliográficas registradas." />;
  }
  return (
    <div className="rounded-2xl border border-slate-200 bg-white divide-y divide-slate-100">
      {sources.map((s, i) => (
        <div key={s.pmid ?? i} className="px-6 py-4 flex items-start gap-4">
          <span className="shrink-0 text-sm font-mono text-slate-400 w-7 text-right pt-0.5">
            {i + 1}
          </span>
          <div className="flex-1 space-y-0.5">
            <p className="text-sm font-medium text-slate-800">
              <span
                className={
                  s.verification_status && SOURCE_VERDICT[s.verification_status]?.tachado
                    ? "line-through text-slate-400"
                    : ""
                }
              >
                {s.title}
              </span>
              {s.verification_status && SOURCE_VERDICT[s.verification_status] && (
                <span
                  className={`ml-2 text-xs font-semibold ${SOURCE_VERDICT[s.verification_status].color}`}
                >
                  ({SOURCE_VERDICT[s.verification_status].label})
                </span>
              )}
            </p>
            {s.actual_title && (
              <p className="text-xs text-slate-500">
                <span className="font-semibold text-red-600">En PubMed este PMID es:</span>{" "}
                {s.actual_title}
              </p>
            )}
            <p className="text-xs text-slate-400">
              {[s.journal, s.year].filter(Boolean).join(" · ")}
              {s.pmid && (
                <span className="ml-2 font-mono">PMID: {s.pmid}</span>
              )}
            </p>
          </div>
          {s.url && (
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-xs text-blue-600 hover:text-blue-800 pt-0.5"
            >
              PubMed ↗
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Source row (dentro de hipótesis) ──────────────────────────────────── */

function SourceRow({ source }: { source: Source }) {
  const veredicto = source.verification_status
    ? SOURCE_VERDICT[source.verification_status]
    : undefined;

  return (
    <li className="flex items-start gap-2 text-xs text-slate-500">
      <span
        className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
          veredicto?.tachado ? "bg-red-400" : source.verified ? "bg-emerald-400" : "bg-slate-300"
        }`}
      />
      <span className="flex-1 leading-relaxed">
        <span className={veredicto?.tachado ? "line-through text-slate-400" : ""}>
          {source.title}
          {source.journal && (
            <span className="text-slate-400"> · {source.journal}</span>
          )}
          {source.year && (
            <span className="text-slate-400"> · {source.year}</span>
          )}
          {source.pmid && (
            <span className="font-mono text-slate-400"> · PMID: {source.pmid}</span>
          )}
        </span>
        {veredicto && (
          <span className={`ml-1.5 font-semibold ${veredicto.color}`}>({veredicto.label})</span>
        )}
        {/* Tipos de publicación de PubMed: son los que fijan el tope de evidencia. */}
        {source.verified && !!source.publication_types?.length && (
          <span className="mt-0.5 block text-slate-400">
            Tipo en PubMed: {source.publication_types.join(", ")}
          </span>
        )}
        {/* El título real es la prueba: el PMID existe, pero es de otra cosa. */}
        {source.actual_title && (
          <span className="mt-0.5 block text-slate-500">
            <span className="font-semibold text-red-600">En PubMed este PMID es:</span>{" "}
            {source.actual_title}
          </span>
        )}
      </span>
      {source.url && (
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:text-blue-700 shrink-0"
        >
          ↗
        </a>
      )}
    </li>
  );
}

/* ── Empty state ────────────────────────────────────────────────────────── */

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-white py-16 text-center">
      <p className="text-slate-400 text-sm">{message}</p>
    </div>
  );
}
