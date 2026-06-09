"use client";

import { useRouter } from "next/navigation";
import UploadForm from "@/components/UploadForm";
import type { StructuredReport } from "@/lib/types";

const AGENTS = [
  { icon: "🔬", name: "Analista de Literatura", desc: "Evidencia PubMed" },
  { icon: "🧬", name: "Especialista Genómica", desc: "Variantes y genes" },
  { icon: "🏥", name: "Consultor Clínico", desc: "Razonamiento diferencial" },
  { icon: "⚖️", name: "Árbitro Verificador", desc: "Validación cruzada" },
  { icon: "🔭", name: "Navegador de Ensayos", desc: "ClinicalTrials.gov" },
  { icon: "📋", name: "Sintetizador", desc: "Reporte final estructurado" },
];

const STEPS = [
  { n: "01", label: "Ingesta", sub: "PDF o texto" },
  { n: "02", label: "Normalización", sub: "INN · unidades" },
  { n: "03", label: "Síntesis PICO", sub: "Contexto clínico" },
  { n: "04", label: "Ronda 1", sub: "Análisis paralelo" },
  { n: "05", label: "Debate", sub: "Rondas 2–4" },
  { n: "06", label: "Reporte", sub: "Hipótesis + ensayos" },
];

export default function HomePage() {
  const router = useRouter();

  const handleSuccess = (report: StructuredReport) => {
    sessionStorage.setItem("nexus_report", JSON.stringify(report));
    router.push("/report");
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <header className="bg-slate-900 text-white">
        <div className="mx-auto max-w-5xl px-6 py-14">
          <div className="flex items-start justify-between gap-8">
            <div className="space-y-4 max-w-xl">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-blue-500/20 px-3 py-0.5 text-xs font-medium text-blue-300 ring-1 ring-blue-500/30">
                  v0.3 · Sprint 3
                </span>
                <span className="rounded-full bg-emerald-500/20 px-3 py-0.5 text-xs font-medium text-emerald-300 ring-1 ring-emerald-500/30">
                  Prototipo académico
                </span>
              </div>
              <h1 className="text-5xl font-bold tracking-tight">NEXUS</h1>
              <p className="text-lg text-slate-300 leading-relaxed">
                Sistema de soporte investigativo clínico multi-agente.
                Genera hipótesis de investigación respaldadas por evidencia
                a partir de documentos clínicos.
              </p>
              <p className="text-sm text-slate-500">
                Tesis Final · Analista en Sistemas · IRESM, Villa Carlos Paz
              </p>
            </div>

            {/* Stats */}
            <div className="hidden md:grid grid-cols-2 gap-3 shrink-0">
              {[
                { n: "6", label: "Agentes IA" },
                { n: "4", label: "Rondas de debate" },
                { n: "I–III", label: "Niveles evidencia" },
                { n: "PDF", label: "Entrada soportada" },
              ].map(({ n, label }) => (
                <div
                  key={label}
                  className="rounded-xl bg-slate-800 px-5 py-4 text-center"
                >
                  <p className="text-2xl font-bold text-white">{n}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* ── Contenido principal ────────────────────────────────────────── */}
      <main className="flex-1 bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-12 space-y-12">

          {/* Upload card */}
          <section className="grid md:grid-cols-2 gap-8 items-start">
            <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-800 mb-1">
                Cargar caso clínico
              </h2>
              <p className="text-sm text-slate-400 mb-6">
                Subí la historia clínica en PDF o pegá el texto directamente.
              </p>
              <UploadForm onSuccess={handleSuccess} />
            </div>

            {/* Pipeline steps */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                Pipeline de análisis
              </h3>
              {STEPS.map((s, i) => (
                <div
                  key={s.n}
                  className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
                    {s.n}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-800">
                      {s.label}
                    </p>
                    <p className="text-xs text-slate-400">{s.sub}</p>
                  </div>
                  {i < STEPS.length - 1 && (
                    <span className="text-slate-300 text-xs">→</span>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Agents grid */}
          <section>
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-400">
              Agentes especializados
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {AGENTS.map((a) => (
                <div
                  key={a.name}
                  className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4"
                >
                  <span className="text-2xl">{a.icon}</span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {a.name}
                    </p>
                    <p className="text-xs text-slate-400">{a.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-400">
          <p>
            <span className="font-medium text-slate-600">NEXUS</span> no emite
            diagnósticos clínicos. Las hipótesis generadas son orientativas y
            deben ser evaluadas por el médico responsable.
          </p>
          <p className="shrink-0">IRESM · 2026</p>
        </div>
      </footer>
    </div>
  );
}
