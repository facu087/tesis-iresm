import type { Metadata } from "next";
import Link from "next/link";
import ScrollReveal from "@/components/ScrollReveal";
import { PIPELINE_STEPS, PIPELINE_SUMMARY } from "@/lib/pipelineSteps";

export const metadata: Metadata = {
  title: "NEXUS — Sistema de Soporte Investigativo Clínico",
  description:
    "Pipeline multi-agente que analiza documentos clínicos, debate hipótesis " +
    "entre agentes de IA y verifica cada referencia contra PubMed. NEXUS no " +
    "emite diagnósticos: genera hipótesis de investigación para el médico " +
    "responsable.",
};

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <SiteHeader />
      <main className="flex-1">
        <ScrollReveal>
          <HeroSection />
        </ScrollReveal>
        <ScrollReveal>
          <HowItWorksSection />
        </ScrollReveal>
      </main>
    </div>
  );
}

/* ── Header ────────────────────────────────────────────────────────────── */

function SiteHeader() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <span className="text-sm font-semibold tracking-tight">NEXUS</span>

        {/*
          Fila flexible enlaces — CTA (design D9): deja lugar para insertar un
          futuro enlace/botón "Ingresar" antes o después del CTA, sin agregarlo
          en este cambio.
        */}
        <div className="flex items-center gap-6">
          <nav className="hidden items-center gap-6 text-sm text-fg-muted sm:flex">
            <a
              href="#como-funciona"
              className="cursor-pointer rounded-sm transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
            >
              Cómo funciona
            </a>
            <a
              href="#agentes"
              className="cursor-pointer rounded-sm transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
            >
              Agentes
            </a>
            <a
              href="#funcionalidades"
              className="cursor-pointer rounded-sm transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
            >
              Funcionalidades
            </a>
          </nav>
          <Link
            href="/analizar"
            className="cursor-pointer rounded-full bg-fg px-4 py-2 text-sm font-semibold text-bg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            Analizar un caso
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ── Hero ──────────────────────────────────────────────────────────────── */

function HeroSection() {
  return (
    <section className="mx-auto max-w-5xl px-6 pt-14 pb-16 sm:pt-20">
      <div className="max-w-2xl space-y-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
          Tesis final · Analista en Sistemas · IRESM
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-balance sm:text-5xl">
          Hipótesis de investigación clínica, respaldadas por evidencia
          verificable
        </h1>
        <p className="text-lg leading-relaxed text-fg-muted">
          NEXUS analiza documentos clínicos con un pipeline de agentes de IA
          que debaten entre sí en rondas adversariales, y verifica cada
          referencia bibliográfica contra PubMed antes de mostrarla.
        </p>
        <div className="flex flex-wrap items-center gap-5 pt-1">
          <Link
            href="/analizar"
            className="cursor-pointer rounded-full bg-fg px-6 py-3 text-sm font-semibold text-bg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            Analizar un caso →
          </Link>
          <a
            href="#como-funciona"
            className="cursor-pointer rounded-sm text-sm font-medium text-fg-muted transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            Ver cómo funciona
          </a>
        </div>
        <p className="rounded-xl border border-border bg-bg-subtle px-4 py-3 text-sm leading-relaxed text-fg-muted">
          <strong className="font-semibold text-fg">
            NEXUS no emite diagnósticos.
          </strong>{" "}
          Genera hipótesis de investigación para que las evalúe el médico
          responsable.
        </p>
      </div>
    </section>
  );
}

/* ── Cómo funciona ─────────────────────────────────────────────────────── */

function HowItWorksSection() {
  return (
    <section
      id="como-funciona"
      aria-labelledby="como-funciona-heading"
      className="border-t border-border"
    >
      <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
        <p className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
          Cómo funciona
        </p>
        <h2
          id="como-funciona-heading"
          className="mt-2 max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          Un pipeline de agentes que debaten, verifican y recién entonces
          reportan.
        </h2>

        {/*
          Diagrama del flujo: `role="img"` + `aria-label` lo describe como una
          sola imagen para lectores de pantalla; el contenido visual queda
          `aria-hidden`, y la alternativa textual completa (misma secuencia,
          mismo orden) vive en la lista `sr-only` de abajo (design, tarea 4.2).
        */}
        <div
          role="img"
          aria-label={PIPELINE_SUMMARY}
          className="mt-12 max-w-2xl"
        >
          <div aria-hidden="true">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.id} className="relative flex gap-5 pb-8 last:pb-0">
                {i < PIPELINE_STEPS.length - 1 && (
                  <span className="absolute top-9 left-4 h-[calc(100%-1rem)] w-px bg-border" />
                )}
                <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-fg text-xs font-bold text-bg">
                  {step.id}
                </span>
                <div className="pt-0.5">
                  <p className="text-sm font-semibold">{step.label}</p>
                  <p className="mt-1 text-sm text-fg-muted">
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Alternativa textual accesible (design, tarea 4.2): mismos pasos,
            mismo orden que el diagrama, para lectores de pantalla. */}
        <ol className="sr-only">
          {PIPELINE_STEPS.map((step) => (
            <li key={step.id}>
              Paso {step.id}: {step.label}. {step.description}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
