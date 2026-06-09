"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { downloadPdf } from "@/lib/api";
import type {
  StructuredReport,
  RankedHypothesis,
  ClinicalTrial,
  CaseSummarySection,
  DebateSummary,
  Source,
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
          <MetaStat label="Fuentes" value={String(report.bibliography.length)} />
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
          {tab === "ensayos"      && <EnsayosTab       trials={report.clinical_trials} />}
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

/* ── Hipótesis tab ─────────────────────────────────────────────────────── */

function HipotesisTab({ hypotheses }: { hypotheses: RankedHypothesis[] }) {
  if (!hypotheses.length) {
    return <EmptyState message="No se generaron hipótesis." />;
  }
  return (
    <div className="space-y-5">
      {hypotheses.map((h) => (
        <div
          key={h.rank}
          className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4"
        >
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
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${PRIORITY_BADGE[h.priority] ?? ""}`}>
                  Prioridad {PRIORITY_LABEL[h.priority] ?? h.priority}
                </span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${EVIDENCE_BADGE[h.evidence_level] ?? ""}`}>
                  Evidencia nivel {h.evidence_level}
                </span>
                {h.supporting_agents.map((ag) => (
                  <span key={ag} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500">
                    Agente {ag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Justificación */}
          <div className="rounded-xl bg-slate-50 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
              Justificación
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">{h.rationale}</p>
          </div>

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
      ))}
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

/* ── Ensayos tab ────────────────────────────────────────────────────────── */

function EnsayosTab({ trials }: { trials: ClinicalTrial[] }) {
  if (!trials.length) {
    return (
      <EmptyState message="No se encontraron ensayos clínicos activos relacionados al caso." />
    );
  }
  return (
    <div className="space-y-5">
      {trials.map((t) => (
        <div
          key={t.nct_id}
          className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4"
        >
          {/* Título + badges + link */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 flex-1">
              <p className="text-base font-semibold text-slate-900 leading-snug">
                {t.title}
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-mono text-slate-600">
                  {t.nct_id}
                </span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  t.status === "RECRUITING"
                    ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200"
                    : "bg-slate-100 text-slate-600"
                }`}>
                  {t.status}
                </span>
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
      ))}
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
            <p className="text-sm font-medium text-slate-800">{s.title}</p>
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
  return (
    <li className="flex items-start gap-2 text-xs text-slate-500">
      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
      <span className="flex-1 leading-relaxed">
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
