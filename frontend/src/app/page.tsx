import type { Metadata } from "next";
import Link from "next/link";
import ScrollReveal from "@/components/ScrollReveal";
import ThemeToggle from "@/components/ThemeToggle";
import ReportDemo from "@/components/ReportDemo";
import BeforeAfter from "@/components/BeforeAfter";
import DebateDiagram from "@/components/DebateDiagram";
import { PIPELINE_STEPS, PIPELINE_SUMMARY } from "@/lib/pipelineSteps";
import {
  BookIcon,
  DnaIcon,
  PulseIcon,
  ScaleIcon,
  CompassIcon,
  DocumentIcon,
} from "@/components/icons";

export const metadata: Metadata = {
  title: "NEXUS — Sistema de Soporte Investigativo Clínico",
  description:
    "Pipeline multi-agente que analiza documentos clínicos, debate hipótesis " +
    "entre agentes de IA y verifica cada referencia contra PubMed. NEXUS no " +
    "emite diagnósticos: genera hipótesis de investigación para el médico " +
    "responsable.",
};

const focus =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent";

export default function LandingV2() {
  return (
    <div className="flex min-h-screen flex-col bg-bg font-body text-fg">
      <Header />
      <main className="flex-1">
        <ScrollReveal>
          <Hero />
        </ScrollReveal>
        <ScrollReveal>
          <ProductSection />
        </ScrollReveal>
        <ScrollReveal>
          <EvidenceSection />
        </ScrollReveal>
        <ScrollReveal>
          <HowSection />
        </ScrollReveal>
        <ScrollReveal>
          <AgentsSection />
        </ScrollReveal>
        <ScrollReveal>
          <ClosingSection />
        </ScrollReveal>
      </main>
      <Footer />
    </div>
  );
}

/* ── Encabezado ────────────────────────────────────────────────────────── */

function Header() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <span className="font-serif text-xl font-semibold tracking-tight text-accent">
          NEXUS
        </span>
        <div className="flex items-center gap-3 sm:gap-6">
          <nav className="hidden items-center gap-6 text-sm text-fg-muted md:flex">
            <a href="#reporte" className={`rounded-sm hover:text-accent ${focus}`}>
              El reporte
            </a>
            <a href="#verificacion" className={`rounded-sm hover:text-accent ${focus}`}>
              Verificación
            </a>
            <a href="#como-funciona" className={`rounded-sm hover:text-accent ${focus}`}>
              Cómo funciona
            </a>
            <a href="#agentes" className={`rounded-sm hover:text-accent ${focus}`}>
              Agentes
            </a>
            <Link href="/ingresar" className={`rounded-sm hover:text-accent ${focus}`}>
              Ingresar
            </Link>
          </nav>
          <ThemeToggle />
          <Link
            href="/analizar"
            className={`rounded-full bg-accent px-4 py-2 text-sm font-bold text-accent-fg transition-opacity duration-200 hover:opacity-85 ${focus}`}
          >
            Analizar un caso
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ── Marco común de sección: numeración grande + filete ───────────────── */

function Section({
  id,
  number,
  label,
  children,
}: {
  id?: string;
  number: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-label={label} className="border-t border-fg">
      <div className="mx-auto grid max-w-7xl gap-x-8 gap-y-6 px-6 py-14 sm:py-20 lg:grid-cols-12">
        <div className="lg:col-span-2">
          <p
            aria-hidden="true"
            className="font-serif text-6xl leading-none font-semibold text-ochre sm:text-7xl"
          >
            {number}
          </p>
          <p className="mt-3 text-xs font-bold uppercase tracking-widest text-fg-muted">
            {label}
          </p>
        </div>
        <div className="lg:col-span-10">{children}</div>
      </div>
    </section>
  );
}

/* ── Hero ──────────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <section className="mx-auto max-w-7xl px-6 pt-12 pb-14 sm:pt-16">
      <p className="text-xs font-bold uppercase tracking-widest text-ochre">
        Tesis final · Analista en Sistemas · IRESM
      </p>
      <h1 className="mt-4 max-w-5xl font-serif text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
        Cada hipótesis, con la evidencia a la vista.
      </h1>
      <div className="mt-10 grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <p className="max-w-xl text-lg leading-relaxed text-fg-muted">
            NEXUS analiza documentos clínicos con agentes de IA que debaten
            entre sí, y contrasta cada referencia con PubMed antes de
            mostrarla.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-5">
            <Link
              href="/analizar"
              className={`rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-fg transition-opacity duration-200 hover:opacity-85 ${focus}`}
            >
              Analizar un caso →
            </Link>
            <a
              href="#reporte"
              className={`rounded-sm text-sm font-bold text-fg-muted hover:text-accent ${focus}`}
            >
              Ver un reporte de ejemplo
            </a>
          </div>
        </div>
        <p className="self-start border-l-4 border-ochre bg-bg-subtle px-5 py-4 text-sm leading-relaxed text-fg-muted lg:col-span-5 lg:col-start-8">
          <strong className="text-fg">NEXUS no emite diagnósticos.</strong>{" "}
          Genera hipótesis de investigación para que las evalúe el médico
          responsable.
        </p>
      </div>
    </section>
  );
}

/* ── 01 El producto ────────────────────────────────────────────────────── */

function ProductSection() {
  return (
    <Section id="reporte" number="01" label="El reporte">
      <h2 className="max-w-3xl font-serif text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
        Esto es lo que recibe el médico: hipótesis ordenadas por evidencia y
        no por seguridad con la que se enuncian.
      </h2>
      <div className="mt-10">
        <ReportDemo />
      </div>
    </Section>
  );
}

/* ── 02 Antes y después + cifras ───────────────────────────────────────── */

const FIGURES = [
  { value: "6", label: "agentes especializados", note: "El Agente 06 está en desarrollo." },
  { value: "5", label: "rondas", note: "Análisis paralelo, tres de debate y una de recitación." },
  { value: "3", label: "fuentes externas", note: "PubMed, ClinicalTrials.gov y Orphanet." },
] as const;

function EvidenceSection() {
  return (
    <Section id="verificacion" number="02" label="Verificación">
      <h2 className="max-w-3xl font-serif text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
        Un modelo puede citar con aplomo un artículo que no existe como lo
        describe. NEXUS lo contrasta.
      </h2>
      <div className="mt-10 grid gap-10 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <BeforeAfter />
        </div>
        <div className="lg:col-span-4">
          <div className="bg-brand p-6 text-brand-fg sm:p-8">
            <p className="font-serif text-6xl leading-none font-semibold">
              14 <span className="text-3xl">de 18</span>
            </p>
            <p className="mt-3 text-sm font-bold uppercase tracking-widest">
              citas no coincidieron con PubMed
            </p>
            <p className="mt-3 text-sm text-brand-fg-muted">
              Corrida real del caso de prueba, 22 de septiembre de 2026: 3
              coincidieron y 1 no traía PMID. Es un caso medido, no una tasa
              general.
            </p>
          </div>
          <dl className="mt-6 divide-y divide-border border-y border-border">
            {FIGURES.map((f) => (
              <div key={f.label} className="flex items-baseline gap-4 py-3">
                <dt className="flex items-baseline gap-3">
                  <span className="font-serif text-4xl font-semibold text-accent">
                    {f.value}
                  </span>
                  <span className="text-sm font-bold">{f.label}</span>
                </dt>
                <dd className="text-xs text-fg-muted">{f.note}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </Section>
  );
}

/* ── 03 Cómo funciona ──────────────────────────────────────────────────── */

function HowSection() {
  return (
    <Section id="como-funciona" number="03" label="Cómo funciona">
      <h2 className="max-w-3xl font-serif text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
        Ocho etapas, de la ingesta al reporte.
      </h2>
      <div className="mt-10 grid gap-10 lg:grid-cols-12">
        {/*
          El diagrama se ve en todos los anchos. Bajo 768 px conserva un ancho
          mínimo legible y se desplaza dentro de su propio contenedor, sin
          provocar scroll horizontal de la página. La alternativa textual es la
          lista de al lado (mismos pasos, mismo orden).
        */}
        <div
          role="img"
          aria-label={PIPELINE_SUMMARY}
          tabIndex={0}
          className={`overflow-x-auto rounded-sm md:overflow-visible lg:sticky lg:top-8 lg:col-span-5 lg:self-start ${focus}`}
        >
          <DebateDiagram className="min-w-[30rem] w-full max-w-md md:min-w-0" />
        </div>
        <ol className="divide-y divide-border border-y border-border lg:col-span-7">
          {PIPELINE_STEPS.map((step) => (
            <li
              key={step.id}
              className="grid gap-x-6 gap-y-1 py-5 sm:grid-cols-[3.5rem_1fr]"
            >
              <span
                aria-hidden="true"
                className="font-serif text-3xl leading-none font-semibold text-accent"
              >
                {step.id}
              </span>
              <div>
                <p className="font-bold">
                  <span className="sr-only">Paso {step.id}: </span>
                  {step.label}
                </p>
                <p className="mt-1 text-sm text-fg-muted">{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </Section>
  );
}


/* ── 04 Agentes ────────────────────────────────────────────────────────── */

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
    <Section id="agentes" number="04" label="Agentes">
      <h2 className="max-w-3xl font-serif text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
        Seis agentes especializados, un solo consenso.
      </h2>
      <ul className="mt-10 divide-y divide-border border-y border-border">
        {AGENTS.map((agent) => (
          <li
            key={agent.id}
            className="grid gap-x-8 gap-y-2 py-6 md:grid-cols-12"
          >
            <div className="flex items-start gap-4 md:col-span-4">
              <agent.Icon
                className={`mt-0.5 h-7 w-7 shrink-0 ${agent.pending ? "text-fg-muted" : "text-accent"}`}
              />
              <div>
                <p className="font-serif text-2xl leading-none font-semibold text-fg-muted">
                  {agent.id}
                </p>
                <p className="mt-1 font-bold">{agent.name}</p>
                {agent.pending && (
                  <span className="mt-2 inline-block rounded-full border border-dashed border-fg-muted px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-widest text-fg-muted">
                    En desarrollo
                  </span>
                )}
              </div>
            </div>
            <p className="max-w-prose text-sm leading-relaxed text-fg-muted md:col-span-8">
              {agent.description}
            </p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/* ── Cierre ────────────────────────────────────────────────────────────── */

function ClosingSection() {
  return (
    <section aria-labelledby="cierre-heading" className="bg-brand text-brand-fg">
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-16 sm:py-20 lg:grid-cols-12 lg:items-end">
        <div className="lg:col-span-8">
          <h2
            id="cierre-heading"
            className="font-serif text-3xl leading-tight font-semibold tracking-tight sm:text-5xl"
          >
            ¿Tenés un caso clínico para analizar?
          </h2>
          <p className="mt-4 max-w-xl text-brand-fg-muted">
            Subí el documento o pegá el texto: el pipeline hace el resto y
            devuelve un reporte con hipótesis priorizadas, junto con sus
            fuentes.
          </p>
        </div>
        <div className="lg:col-span-4 lg:justify-self-end">
          <Link
            href="/analizar"
            className="inline-block rounded-full bg-brand-btn px-8 py-3 text-center text-sm font-bold text-brand-btn-fg transition-opacity duration-200 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-fg"
          >
            Analizar un caso →
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ── Pie ───────────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-xs leading-relaxed text-fg-muted">
          <span className="font-bold text-fg">NEXUS</span> no emite
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
