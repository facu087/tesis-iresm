import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import LandingLogo from "@/components/landing/LandingLogo";
import LandingMark from "@/components/landing/LandingMark";
import LandingMarkSprite from "@/components/landing/LandingMarkSprite";
import { CONTAINER, FOCUS_RING, NAV_LINK, TRANSITION } from "@/components/landing/styles";

/**
 * Page frame of the access routes (`/registro`, `/ingresar`) and of the
 * signed in routes (`/cuenta`, `/analizar`), in the landing visual system: the
 * `.landing` scope, the same floating pill as the landing navigation (logo
 * back to `/`, one plain link or action, theme selector) and a two column
 * body with the page heading beside the form.
 *
 * The NEXUS mark sits below the heading as a faint watermark on wide screens
 * only. It is decorative, never under text, and `main` clips whatever runs
 * past its edges, so it cannot cause overflow. A page that passes `aside`
 * gets that content under the heading instead, and no watermark.
 *
 * Presentation only: forms, requests and redirects stay in each page.
 */

interface AuthShellProps {
  /** Plain link of the pill, pointing at the sibling access page. */
  headerLink?: { href: string; label: string };
  /**
   * Control of the pill for pages whose header is not a plain sibling link
   * (e.g. the logout button). Style it with `NAV_LINK`.
   */
  headerAction?: React.ReactNode;
  /** Decorative icon shown above the heading. */
  icon: React.ReactNode;
  title: string;
  /** Optional sentence under the heading. */
  lead?: string;
  /**
   * Secondary content. On wide screens it sits under the heading, beside the
   * main column; on narrow screens it follows the main column.
   */
  aside?: React.ReactNode;
  /** Page footer, below the body (e.g. a standing notice). */
  footer?: React.ReactNode;
  children: React.ReactNode;
}

function rise(delayMs: number): React.CSSProperties {
  return { "--landing-delay": `${delayMs}ms` } as React.CSSProperties;
}

export default function AuthShell({
  headerLink,
  headerAction,
  icon,
  title,
  lead,
  aside,
  footer,
  children,
}: AuthShellProps) {
  return (
    <div className="landing flex min-h-screen flex-col bg-bg font-sans text-fg">
      <a
        href="#contenido"
        className={`sr-only rounded-full bg-accent px-3 py-2 text-sm font-semibold text-accent-fg focus-visible:not-sr-only focus-visible:fixed focus-visible:top-4 focus-visible:left-4 focus-visible:z-60 ${FOCUS_RING}`}
      >
        Saltar al contenido
      </a>

      <LandingMarkSprite />

      <header className="px-4">
        <div className="mx-auto mt-6 flex w-max max-w-full items-center gap-2 rounded-full border border-border bg-white/80 p-2 backdrop-blur-xl dark:bg-black/80">
          <Link
            href="/"
            aria-label="NEXUS, inicio"
            className={`inline-flex items-center rounded-full px-3 py-2 text-base font-bold text-accent ${TRANSITION} hover:opacity-80 active:translate-y-px ${FOCUS_RING}`}
          >
            <LandingLogo fromSprite />
          </Link>
          {headerLink && (
            <Link href={headerLink.href} className={NAV_LINK}>
              {headerLink.label}
            </Link>
          )}
          {headerAction}
          {/* Below `sm` the selector keeps its icon and accessible name only. */}
          <ThemeToggle className="max-sm:[&>span]:hidden" />
        </div>
      </header>

      <main id="contenido" tabIndex={-1} className="flex-1 overflow-clip outline-none">
        <div
          className={`${CONTAINER} grid items-start gap-8 pt-12 pb-16 lg:grid-cols-12 lg:pb-24 ${aside ? "lg:grid-rows-[auto_1fr]" : ""}`}
        >
          <div className="relative lg:col-span-5">
            {!aside && (
              <div
                aria-hidden="true"
                className="landing-hero-mark pointer-events-none absolute top-full -left-24 mt-12 hidden h-96 lg:block"
              >
                <LandingMark className="block h-full w-auto max-w-none" />
              </div>
            )}
            <div className="relative">
              <span className="landing-rise inline-flex size-12 items-center justify-center rounded-full border border-border bg-bg-subtle text-accent">
                {icon}
              </span>
              <h1
                className="landing-hero-heading landing-rise mt-6 max-w-[680px] pb-2 text-4xl font-semibold text-balance sm:text-5xl"
                style={rise(80)}
              >
                {title}
              </h1>
              {lead && (
                <p
                  className="landing-rise mt-4 max-w-[680px] text-lg text-pretty text-fg-muted"
                  style={rise(160)}
                >
                  {lead}
                </p>
              )}
            </div>
          </div>

          <div
            className={`landing-rise relative lg:col-span-7 ${aside ? "lg:row-span-2" : ""}`}
            style={rise(160)}
          >
            {children}
          </div>

          {aside && (
            <div className="landing-rise lg:col-span-5 lg:col-start-1 lg:row-start-2" style={rise(240)}>
              {aside}
            </div>
          )}
        </div>
      </main>

      {footer}
    </div>
  );
}
