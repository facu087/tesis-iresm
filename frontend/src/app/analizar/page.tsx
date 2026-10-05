"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { useRouter } from "next/navigation";
import UploadForm from "@/components/UploadForm";
import { inputStore } from "@/lib/inputStore";
import type { AnalysisInput } from "@/lib/inputStore";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";
import { obtenerCuenta } from "@/lib/api";

export default function AnalizarPage() {
  const router = useRouter();
  const [autorizado, setAutorizado] = useState(false);

  // Protección de UX, no de seguridad (proteccion-analisis-clinico —
  // Requirement: La aplicación no es el límite de seguridad): el backend ya
  // rechaza con 401/403 igual, sin sesión de médico verificado. Esto solo
  // evita que alguien sin cuenta cargue un caso para nada.
  useEffect(() => {
    let cancelado = false;
    obtenerCuenta()
      .then((cuenta) => {
        if (cancelado) return;
        if (cuenta === null) {
          router.push("/ingresar");
        } else if (cuenta.rol !== "medico" || cuenta.estado !== "verificado") {
          router.push("/cuenta");
        } else {
          setAutorizado(true);
        }
      })
      .catch(() => {
        if (!cancelado) router.push("/ingresar");
      });
    return () => {
      cancelado = true;
    };
  }, [router]);

  const handleReady = (input: AnalysisInput) => {
    inputStore.set(input);
    router.push("/analyzing");
  };

  if (!autorizado) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-sm text-fg-muted">
        Verificando sesión...
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="cursor-pointer rounded-sm font-serif text-lg font-semibold tracking-tight text-accent transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
          >
            NEXUS
          </Link>
          <div className="flex items-center gap-2 sm:gap-4">
            <ThemeToggle />
            <Link
              href="/"
              className="cursor-pointer rounded-sm text-sm text-fg-muted transition-colors duration-200 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
            >
              ← Volver al inicio
            </Link>
          </div>
        </div>
      </header>

      {/* ── Contenido principal ───────────────────────────────────────── */}
      <main className="flex-1">
        <div className="mx-auto grid max-w-5xl gap-10 px-6 py-14 md:grid-cols-2 md:items-start">
          {/* Carga de caso */}
          <div className="rounded-2xl border border-border bg-bg-subtle p-8">
            <h1 className="mb-1 font-serif text-2xl font-semibold">Cargar caso clínico</h1>
            <p className="mb-6 text-sm text-fg-muted">
              Subí la historia clínica en PDF o pegá el texto directamente.
            </p>
            <UploadForm onReady={handleReady} />
          </div>

          {/* Pasos del pipeline */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-accent">
              Pipeline de análisis
            </h2>
            <ol className="space-y-3">
              {PIPELINE_STEPS.map((step) => (
                <li
                  key={step.id}
                  className="flex items-start gap-4 rounded-xl border border-border bg-bg px-5 py-3"
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent font-serif text-sm font-semibold text-accent-fg">
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
