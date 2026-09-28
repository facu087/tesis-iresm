import type { Metadata } from "next";
import Link from "next/link";
import ScrollReveal from "@/components/ScrollReveal";
import { PIPELINE_STEPS, PIPELINE_SUMMARY } from "@/lib/pipelineSteps";
import {
  BookIcon,
  DnaIcon,
  PulseIcon,
  ScaleIcon,
  CompassIcon,
  DocumentIcon,
  ShieldCheckIcon,
  LayersIcon,
  SearchIcon,
  DebateIcon,
} from "@/components/icons";

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
        <ScrollReveal>
          <AgentsSection />
        </ScrollReveal>
        <ScrollReveal>
          <FeaturesSection />
        </ScrollReveal>
        <ScrollReveal>
          <CtaSection />
        </ScrollReveal>
      </main>
      <SiteFooter />
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

/* ── Agentes ───────────────────────────────────────────────────────────── */

/**
 * Descripciones verificadas contra el código y la documentación fuente de
 * verdad (design D8): `backend/agents/agent_02_genomics.py`,
 * `.claude/architecture.md` y `.claude/backlog.md` — no `.claude/CLAUDE.md`,
 * desactualizado en el estado del Agente 02. El único agente sin capacidad
 * activa descripta es el 06: el reporte final lo arma hoy un módulo
 * determinista (`pipeline/report_builder.py`), no un agente propio.
 */
const AGENTS = [
  {
    id: "01",
    name: "Analista de Literatura",
    Icon: BookIcon,
    description:
      "Genera hipótesis a partir de literatura médica publicada, con búsqueda semántica sobre PubMed (RAG) como contexto.",
    pending: false,
  },
  {
    id: "02",
    name: "Especialista Genómica",
    Icon: DnaIcon,
    description:
      "Analiza el caso desde la genética y la biología molecular, con contexto farmacogenómico de PharmGKB. Una guarda anti-invención degrada cualquier hipótesis que cite un hallazgo genético que no está en el caso.",
    pending: false,
  },
  {
    id: "03",
    name: "Consultor Clínico",
    Icon: PulseIcon,
    description:
      "Razona desde la práctica clínica: diagnóstico diferencial, causas tratables a descartar primero y guías de sociedades médicas.",
    pending: false,
  },
  {
    id: "04",
    name: "Árbitro Verificador",
    Icon: ScaleIcon,
    description:
      "Verifica cada referencia citada contra PubMed, agrupa las hipótesis equivalentes en un consenso y documenta las objeciones sin resolver. Pide una recitación (Ronda 5) a las hipótesis sin respaldo.",
    pending: false,
  },
  {
    id: "05",
    name: "Navegador de Ensayos",
    Icon: CompassIcon,
    description:
      "Busca ensayos clínicos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet, con una compatibilidad orientativa que nunca excluye resultados.",
    pending: false,
  },
  {
    id: "06",
    name: "Sintetizador",
    Icon: DocumentIcon,
    description:
      "Va a ensamblar el reporte final asistido por un agente dedicado. Hoy ese reporte lo arma un módulo determinista, sin agente propio todavía.",
    pending: true,
  },
] as const;

function AgentsSection() {
  return (
    <section
      id="agentes"
      aria-labelledby="agentes-heading"
      className="border-t border-border"
    >
      <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
        <p className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
          Agentes
        </p>
        <h2
          id="agentes-heading"
          className="mt-2 max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          Seis agentes especializados, un solo consenso.
        </h2>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((agent) => (
            <div
              key={agent.id}
              className={`rounded-2xl border p-6 transition-colors duration-200 hover:border-fg-muted ${
                agent.pending
                  ? "border-dashed border-border text-fg-muted"
                  : "border-border"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <agent.Icon className="h-6 w-6 shrink-0" />
                {agent.pending && (
                  <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-semibold tracking-wide text-fg-muted uppercase">
                    En desarrollo
                  </span>
                )}
              </div>
              <p className="mt-4 text-sm font-semibold text-fg">
                Agente {agent.id} · {agent.name}
              </p>
              <p className="mt-1.5 text-sm text-fg-muted">
                {agent.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Funcionalidades clave ─────────────────────────────────────────────── */

const FEATURES = [
  {
    Icon: ShieldCheckIcon,
    title: "Verificación bibliográfica",
    description:
      "Cada referencia citada por los agentes se contrasta contra PubMed —título real contra título citado— antes de mostrarla en el reporte.",
  },
  {
    Icon: LayersIcon,
    title: "Clasificación EBM (I, II, III)",
    description:
      "Las hipótesis se priorizan por nivel de evidencia según el tipo de publicación verificado en PubMed, nunca por lo que el agente declara sin respaldo.",
  },
  {
    Icon: SearchIcon,
    title: "Navegación de ensayos clínicos",
    description:
      "Búsqueda de ensayos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet, con compatibilidad orientativa por caso.",
  },
  {
    Icon: DebateIcon,
    title: "Debate adversarial multi-agente",
    description:
      "Los agentes exponen sus hipótesis, se critican entre sí en varias rondas y ajustan su postura antes de llegar a un consenso.",
  },
] as const;

function FeaturesSection() {
  return (
    <section
      id="funcionalidades"
      aria-labelledby="funcionalidades-heading"
      className="border-t border-border"
    >
      <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
        <p className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
          Funcionalidades clave
        </p>
        <h2
          id="funcionalidades-heading"
          className="mt-2 max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          Evidencia verificable en cada paso, no solo en el resultado.
        </h2>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-2xl border border-border p-6 transition-colors duration-200 hover:border-fg-muted"
            >
              <feature.Icon className="h-6 w-6" />
              <p className="mt-4 text-sm font-semibold text-fg">
                {feature.title}
              </p>
              <p className="mt-1.5 text-sm text-fg-muted">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── CTA final ─────────────────────────────────────────────────────────── */

function CtaSection() {
  return (
    <section className="border-t border-border">
      <div className="mx-auto max-w-5xl px-6 py-20 text-center">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          ¿Tenés un caso clínico para analizar?
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-fg-muted">
          Subí el documento o pegá el texto: el pipeline hace el resto y
          devuelve un reporte con hipótesis priorizadas, junto con sus
          fuentes.
        </p>
        <div className="mt-8">
          <Link
            href="/analizar"
            className="cursor-pointer rounded-full bg-fg px-8 py-3 text-sm font-semibold text-bg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            Analizar un caso →
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ── Footer ────────────────────────────────────────────────────────────── */

function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-xs leading-relaxed text-fg-muted">
          <span className="font-semibold text-fg">NEXUS</span> no emite
          diagnósticos clínicos. Las hipótesis generadas son orientativas y
          deben ser evaluadas por el médico responsable.
        </p>
        <p className="shrink-0 text-xs text-fg-muted">
          Tesis Final · Analista en Sistemas · IRESM, Villa Carlos Paz · 2026
        </p>
      </div>
    </footer>
  );
}
