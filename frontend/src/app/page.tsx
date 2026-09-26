import type { Metadata } from "next";
import Link from "next/link";
import ScrollReveal from "@/components/ScrollReveal";

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
