import type { Metadata } from "next";
import AgentsSection from "@/components/landing/AgentsSection";
import FaqSection, { FAQ_ITEMS } from "@/components/landing/FaqSection";
import FinalCta from "@/components/landing/FinalCta";
import Hero, { HERO_ACTION_ID } from "@/components/landing/Hero";
import HowItWorksSection from "@/components/landing/HowItWorksSection";
import IslandNav, { type NavLink } from "@/components/landing/IslandNav";
import LandingFooter from "@/components/landing/LandingFooter";
import LandingMarkSprite from "@/components/landing/LandingMarkSprite";
import ReportSection from "@/components/landing/ReportSection";
import TaglineReveal from "@/components/landing/TaglineReveal";
import VerificationSection from "@/components/landing/VerificationSection";
import { CONTAINER, FOCUS_RING, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Public landing of NEXUS (`/`). One offer, one audience, one primary action:
 * licensed physicians request access (`/registro`).
 *
 * Long form story layout, told with the product instead of prose: a report
 * card in the hero → the measured citation mismatch → core statement → the
 * annotated example report → the pipeline diagram → the agents → questions →
 * final call to action.
 *
 * Server Component. Interactivity is isolated in small Client Components
 * under `components/landing/` (navigation, tagline reveal, pipeline diagram,
 * agent tiles) and in `ScrollReveal`. The `.landing` wrapper scopes the
 * visual system: see `globals.css`.
 */

const TITLE = "NEXUS: hipótesis de investigación clínica con citas verificadas";
const DESCRIPTION =
  "Seis agentes de IA debaten un caso clínico, cada cita se contrasta con " +
  "PubMed y las hipótesis se ordenan por nivel de evidencia. NEXUS no emite " +
  "diagnósticos.";
const LOCAL_ORIGIN = "http://localhost:3000";

/**
 * Public origin of the deployment, used to resolve the sharing image (the
 * generated card of `opengraph-image.tsx`, which Next.js adds to the tags). There is
 * no production domain yet: set NEXT_PUBLIC_SITE_URL when there is one. An
 * empty or malformed value falls back to the local origin instead of throwing
 * while the route module is evaluated.
 */
function resolveSiteUrl(): URL {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (configured) {
    try {
      const url = new URL(configured);
      if (url.protocol === "http:" || url.protocol === "https:") return url;
    } catch {
      // Not an absolute URL: fall through to the local origin.
    }
    console.warn(
      `NEXT_PUBLIC_SITE_URL is not a valid http(s) URL; using ${LOCAL_ORIGIN} for sharing metadata.`,
    );
  }
  return new URL(LOCAL_ORIGIN);
}

export const metadata: Metadata = {
  metadataBase: resolveSiteUrl(),
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
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
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

      <LandingMarkSprite />

      <IslandNav links={NAV_LINKS} heroActionId={HERO_ACTION_ID} />

      <main id="contenido" tabIndex={-1} className="flex-1 outline-none">
        <Hero />
        <VerificationSection />
        <TaglineSection />
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
