"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import UploadForm from "@/components/UploadForm";
import { inputStore } from "@/lib/inputStore";
import type { AnalysisInput } from "@/lib/inputStore";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";

export default function AnalizarPage() {
  const router = useRouter();

  const handleReady = (input: AnalysisInput) => {
    inputStore.set(input);
    router.push("/analyzing");
  };

  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="cursor-pointer rounded-sm text-sm font-semibold tracking-tight transition-colors duration-200 hover:text-fg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            NEXUS
          </Link>
          <Link
            href="/"
            className="cursor-pointer rounded-sm text-sm text-fg-muted transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            ← Volver al inicio
          </Link>
        </div>
      </header>

      {/* ── Contenido principal ───────────────────────────────────────── */}
      <main className="flex-1">
        <div className="mx-auto grid max-w-5xl gap-10 px-6 py-14 md:grid-cols-2 md:items-start">
          {/* Carga de caso */}
          <div className="rounded-2xl border border-border bg-bg-subtle p-8">
            <h1 className="mb-1 text-xl font-semibold">Cargar caso clínico</h1>
            <p className="mb-6 text-sm text-fg-muted">
              Subí la historia clínica en PDF o pegá el texto directamente.
            </p>
            <UploadForm onReady={handleReady} />
          </div>

          {/* Pasos del pipeline */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-fg-muted">
              Pipeline de análisis
            </h2>
            <ol className="space-y-3">
              {PIPELINE_STEPS.map((step) => (
                <li
                  key={step.id}
                  className="flex items-start gap-4 rounded-xl border border-border bg-bg px-5 py-3"
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-fg text-xs font-bold text-bg">
                    {step.id}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{step.label}</p>
                    <p className="text-xs text-fg-muted">{step.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </main>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-5xl px-6 py-5 text-xs text-fg-muted">
          <span className="font-medium text-fg">NEXUS</span> no emite
          diagnósticos clínicos. Las hipótesis generadas son orientativas y
          deben ser evaluadas por el médico responsable.
        </div>
      </footer>
    </div>
  );
}
