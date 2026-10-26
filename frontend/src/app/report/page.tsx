"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { DownloadSimpleIcon, WarningCircleIcon } from "@phosphor-icons/react/ssr";
import { downloadPdf } from "@/lib/api";
import { reportStore } from "@/lib/reportStore";
import DiagnosticNotice from "@/components/landing/DiagnosticNotice";
import ShellFrame from "@/components/landing/ShellFrame";
import {
  CARD,
  CONTAINER,
  FOCUS_RING,
  PRIMARY_BUTTON,
  TEXT_LINK,
  TRANSITION,
} from "@/components/landing/styles";
import { CasoTab, DebateTab } from "@/components/report/CaseDebateTabs";
import { HipotesisTab } from "@/components/report/HypothesesTab";
import { Notice, SECTION_LABEL } from "@/components/report/primitives";
import {
  ArbitrationBanner,
  DisclaimerNotice,
  MockBanner,
  VerificationBanner,
} from "@/components/report/ReportNotices";
import { BibliografiaTab } from "@/components/report/sources";
import { EnsayosTab } from "@/components/report/TrialsTab";

/**
 * Report view, in the landing visual system: the shared frame (`ShellFrame`)
 * with a full width body, the notices of the report, five tabs and the PDF
 * export. The tab bodies live in `components/report/`.
 *
 * Presentation only: what is read from `reportStore`, the redirect when there
 * is no report and the PDF request are the same as before the migration.
 */

type Tab = "hipotesis" | "caso" | "debate" | "ensayos" | "bibliografia";

const PANEL_ID = "reporte-panel";
const tabDomId = (id: Tab) => `reporte-tab-${id}`;

/** Keys that move the selection along the tab list (wrapping at both ends). */
const NEXT_INDEX: Record<string, (current: number, total: number) => number> = {
  ArrowRight: (current, total) => (current + 1) % total,
  ArrowLeft: (current, total) => (current - 1 + total) % total,
  Home: () => 0,
  End: (_current, total) => total - 1,
};

export default function ReportPage() {
  const router = useRouter();
  const report = useSyncExternalStore(
    reportStore.subscribe,
    reportStore.getSnapshot,
    reportStore.getServerSnapshot,
  );
  const [tab, setTab] = useState<Tab>("hipotesis");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    // Se consulta el almacén en vez de `report`: durante la hidratación esa
    // variable todavía vale null (es la instantánea del servidor) aunque sí
    // haya un reporte guardado, y redirigiría al inicio por error.
    if (reportStore.getSnapshot() === null) router.replace("/");
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

  /* Tabs pattern with automatic activation, as the hero report card of the
     landing: the arrow keys, Home and End move the focus and select the tab
     they land on; only the selected tab is in the tab order. */
  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    // Leave browser shortcuts such as Alt+ArrowLeft (history back) alone.
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const move = NEXT_INDEX[event.key];
    if (!move) return;
    event.preventDefault();
    const next = move(tabs.findIndex((t) => t.id === tab), tabs.length);
    setTab(tabs[next].id);
    tabRefs.current[next]?.focus();
  };

  return (
    <ShellFrame
      headerLink={{ href: "/analizar", label: "Nuevo análisis" }}
      footer={<DiagnosticNotice />}
    >
      <div className={`${CONTAINER} flex flex-col gap-6 pt-12 pb-16`}>

        {/* ── Modo mock ─────────────────────────────────────────────────── */}
        {report.metadata.mock && <MockBanner />}

        {/* ── Título + exportación ──────────────────────────────────────── */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="mb-2 text-sm font-semibold text-ochre">
              NEXUS <span className="font-mono">{report.metadata.nexus_version}</span>
            </p>
            <h1 className="text-3xl font-semibold text-balance text-fg sm:text-4xl">
              Reporte de análisis
            </h1>
          </div>
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            aria-busy={downloading}
            className={`${PRIMARY_BUTTON} cursor-pointer disabled:pointer-events-none disabled:opacity-60`}
          >
            {downloading ? (
              "Generando…"
            ) : (
              <>
                <DownloadSimpleIcon aria-hidden="true" weight="bold" className="size-5" />
                Descargar PDF
              </>
            )}
          </button>
        </div>

        {/* ── PDF error ─────────────────────────────────────────────────── */}
        {downloadError && (
          <Notice tone="danger" Icon={WarningCircleIcon} role="alert">
            <span className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              {downloadError}
              <button
                type="button"
                onClick={() => setDownloadError(null)}
                className={`cursor-pointer text-sm ${TEXT_LINK}`}
              >
                Cerrar
              </button>
            </span>
          </Notice>
        )}

        {/* ── Meta bar ──────────────────────────────────────────────────── */}
        <dl className={`${CARD} grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5`}>
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
        </dl>

        {/* ── Disclaimer ────────────────────────────────────────────────── */}
        <DisclaimerNotice text={report.metadata.disclaimer} />

        {/* ── Verificación bibliográfica ────────────────────────────────── */}
        {report.verification && <VerificationBanner v={report.verification} />}
        {report.arbitration && <ArbitrationBanner a={report.arbitration} />}

        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        {/* The strip stays on screen while the panel scrolls. It scrolls
            sideways inside itself where the five tabs do not fit. */}
        <div className="sticky top-4 z-10 mt-6">
          <div
            role="tablist"
            aria-label="Secciones del reporte"
            onKeyDown={handleTabKeyDown}
            className="flex w-max max-w-full gap-1 overflow-x-auto rounded-full border border-border bg-bg-subtle p-1 [scrollbar-width:none]"
          >
            {tabs.map((t, index) => {
              const isSelected = tab === t.id;
              return (
                <button
                  key={t.id}
                  ref={(node) => {
                    tabRefs.current[index] = node;
                  }}
                  type="button"
                  role="tab"
                  id={tabDomId(t.id)}
                  aria-selected={isSelected}
                  aria-controls={isSelected ? PANEL_ID : undefined}
                  tabIndex={isSelected ? 0 : -1}
                  onClick={() => setTab(t.id)}
                  className={`inline-flex shrink-0 cursor-pointer items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold whitespace-nowrap active:scale-[0.98] ${TRANSITION} ${FOCUS_RING} ${
                    isSelected ? "bg-accent text-accent-fg" : "text-fg-muted hover:text-accent"
                  }`}
                >
                  {t.label}
                  {t.count !== undefined && (
                    <span
                      className={`rounded-full px-2 font-mono text-xs font-semibold ${
                        isSelected ? "bg-accent-fg text-accent" : "bg-surface text-fg-muted"
                      }`}
                    >
                      {t.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Content ───────────────────────────────────────────────────── */}
        <div
          role="tabpanel"
          id={PANEL_ID}
          aria-labelledby={tabDomId(tab)}
          tabIndex={0}
          className={`flex min-w-0 flex-col gap-6 rounded-2xl ${FOCUS_RING}`}
        >
          {tab === "hipotesis" && report.executive_summary && (
            <section className={CARD}>
              <h2 className={`mb-2 ${SECTION_LABEL}`}>Resumen ejecutivo</h2>
              <p className="text-base leading-relaxed text-pretty wrap-anywhere text-fg">
                {report.executive_summary}
              </p>
            </section>
          )}
          {tab === "hipotesis"    && <HipotesisTab    hypotheses={report.hypotheses} />}
          {tab === "caso"         && <CasoTab         summary={report.case_summary} />}
          {tab === "debate"       && <DebateTab        debate={report.debate_summary} />}
          {tab === "ensayos"      && <EnsayosTab       report={report} />}
          {tab === "bibliografia" && <BibliografiaTab  sources={report.bibliography} />}
        </div>

      </div>
    </ShellFrame>
  );
}

/* ── Meta stat ─────────────────────────────────────────────────────────── */

function MetaStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className={SECTION_LABEL}>{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold wrap-anywhere text-fg">{value}</dd>
    </div>
  );
}
