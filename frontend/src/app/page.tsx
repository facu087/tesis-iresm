import type { Metadata } from "next";
import ScrollReveal from "@/components/ScrollReveal";
import ReportDemo from "@/components/ReportDemo";
import AgentsSection from "@/components/landing/AgentsSection";
import BenefitsSection from "@/components/landing/BenefitsSection";
import FaqSection, { FAQ_ITEMS } from "@/components/landing/FaqSection";
import FinalCta from "@/components/landing/FinalCta";
import Hero, { HERO_ACTION_ID } from "@/components/landing/Hero";
import HowItWorksSection from "@/components/landing/HowItWorksSection";
import IslandNav, { type NavLink } from "@/components/landing/IslandNav";
import LandingFooter from "@/components/landing/LandingFooter";
import SectionHeading from "@/components/landing/SectionHeading";
import TaglineReveal from "@/components/landing/TaglineReveal";
import VerificationSection from "@/components/landing/VerificationSection";
import { CONTAINER, FOCUS_RING, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Public landing of NEXUS (`/`). One offer, one audience, one primary action:
 * licensed physicians request access (`/registro`).
 *
 * Long form story layout: the page has to educate and answer scepticism
 * about AI generated citations before asking for the registration, so the
 * argument runs problem and proof → core statement → benefits → the report →
 * how it works → the agents → questions → final call to action.
 *
 * Server Component. Interactivity is isolated in small Client Components
 * under `components/landing/` (navigation, tagline reveal) and in
 * `ScrollReveal`. The `.landing` wrapper scopes the visual system: see
 * `globals.css`.
 */

const TITLE = "NEXUS: hipótesis de investigación clínica con citas verificadas";
const DESCRIPTION =
  "Seis agentes de IA debaten un caso clínico, cada cita se contrasta con " +
  "PubMed y las hipótesis se ordenan por nivel de evidencia. NEXUS no emite " +
  "diagnósticos.";
const OG_IMAGE = {
  url: "/landing/og.jpg",
  width: 1200,
  height: 630,
  alt: "Ilustración de seis nodos cuyas líneas convergen en una hoja de reporte.",
};

export const metadata: Metadata = {
  // Public origin of the deployment, used to resolve the sharing image. There
  // is no production domain yet: set NEXT_PUBLIC_SITE_URL when there is one.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "es_AR",
    url: "/",
    siteName: "NEXUS",
    title: TITLE,
    description: DESCRIPTION,
    images: [OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: [OG_IMAGE],
  },
};

/** In page sections, in page order. Shared by the navigation and the footer. */
const NAV_LINKS: readonly NavLink[] = [
  { href: "#verificacion", label: "Verificación" },
  { href: "#reporte", label: "El reporte" },
  { href: "#como-funciona", label: "Cómo funciona" },
  { href: "#agentes", label: "Agentes" },
  { href: "#preguntas", label: "Preguntas" },
];

/** Core statement of the page, one line per thought. */
const TAGLINE_LINES = [
  "Las hipótesis se ordenan por la evidencia que las respalda,",
  "no por la seguridad con la que se enuncian.",
] as const;

/** FAQ structured data, built from the same list the page renders. */
const FAQ_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ_ITEMS.map((item) => ({
    "@type": "Question",
    name: item.question,
    acceptedAnswer: { "@type": "Answer", text: item.answer },
  })),
};

export default function LandingPage() {
  return (
    <div className="landing flex min-h-screen flex-col bg-bg font-sans text-fg">
      <a
        href="#contenido"
        className={`sr-only rounded-full bg-accent px-3 py-2 text-sm font-semibold text-accent-fg focus-visible:not-sr-only focus-visible:fixed focus-visible:top-4 focus-visible:left-4 focus-visible:z-60 ${FOCUS_RING}`}
      >
        Saltar al contenido
      </a>

      <IslandNav links={NAV_LINKS} heroActionId={HERO_ACTION_ID} />

      <main id="contenido" tabIndex={-1} className="flex-1 outline-none">
        <Hero />
        <VerificationSection />
        <TaglineSection />
        <BenefitsSection />
        <ReportSection />
        <HowItWorksSection />
        <AgentsSection />
        <FaqSection />
        <FinalCta />
      </main>

      <LandingFooter links={NAV_LINKS} />

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(FAQ_JSON_LD).replace(/</g, "\\u003c"),
        }}
      />
    </div>
  );
}

/* ── Tagline reveal: the core statement as its own moment ──────────────── */

function TaglineSection() {
  return (
    <section aria-label="Idea central" className={`bg-bg ${SECTION_PADDING}`}>
      <div className={CONTAINER}>
        <TaglineReveal
          lines={TAGLINE_LINES}
          className="max-w-[680px] text-4xl font-semibold text-balance text-fg sm:text-5xl"
        />
      </div>
    </section>
  );
}

/* ── The report: what the physician receives ───────────────────────────── */

function ReportSection() {
  return (
    <section
      id="reporte"
      aria-labelledby="reporte-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="reporte-heading"
            eyebrow="El reporte"
            title="Esto es lo que recibe el médico"
            lead="Hipótesis de consenso con su nivel de evidencia, el estado de verificación de cada fuente y los ensayos clínicos compatibles. El reporte se puede descargar en PDF."
          />
        </ScrollReveal>
        <ScrollReveal className="mt-12">
          <ReportDemo />
        </ScrollReveal>
      </div>
    </section>
  );
}
