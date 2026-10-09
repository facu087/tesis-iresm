import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeftIcon } from "@phosphor-icons/react/ssr";
import ThemeToggle from "@/components/ThemeToggle";
import { CONTAINER, FOCUS_RING, PRIMARY_BUTTON, TRANSITION } from "@/components/landing/styles";
import LandingLogo from "@/components/landing/LandingLogo";

/**
 * Branded 404. Shares the landing visual system through the `.landing`
 * wrapper and always offers a way back to the home page.
 */

export const metadata: Metadata = {
  title: "Página no encontrada · NEXUS",
  description: "La dirección solicitada no existe en NEXUS.",
};

export default function NotFound() {
  return (
    <div className="landing flex min-h-screen flex-col bg-bg font-sans text-fg">
      <header className={`${CONTAINER} flex items-center justify-between py-6`}>
        <Link
          href="/"
          aria-label="NEXUS, inicio"
          className={`rounded-full px-3 py-2 text-base font-bold text-accent ${TRANSITION} hover:opacity-80 active:translate-y-px ${FOCUS_RING}`}
        >
          <LandingLogo />
        </Link>
        <ThemeToggle />
      </header>

      <main className={`${CONTAINER} flex flex-1 flex-col justify-center py-16`}>
        <p className="landing-rise font-mono text-sm font-semibold text-ochre">Error 404</p>
        <h1
          className="landing-hero-heading landing-rise mt-4 max-w-[680px] pb-2 text-4xl font-semibold text-balance sm:text-5xl"
          style={{ "--landing-delay": "80ms" } as React.CSSProperties}
        >
          No encontramos esa página
        </h1>
        <p
          className="landing-rise mt-4 max-w-[680px] text-lg text-pretty text-fg-muted"
          style={{ "--landing-delay": "160ms" } as React.CSSProperties}
        >
          La dirección no existe o cambió de lugar. Desde el inicio se llega a
          todas las secciones de NEXUS.
        </p>
        <div
          className="landing-rise mt-8"
          style={{ "--landing-delay": "240ms" } as React.CSSProperties}
        >
          <Link href="/" className={PRIMARY_BUTTON}>
            <ArrowLeftIcon aria-hidden="true" weight="bold" className="size-4" />
            Volver al inicio
          </Link>
        </div>
      </main>
    </div>
  );
}
