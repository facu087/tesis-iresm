import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import LandingLogo from "@/components/landing/LandingLogo";
import LandingMarkSprite from "@/components/landing/LandingMarkSprite";
import { FOCUS_RING, NAV_LINK, TRANSITION } from "@/components/landing/styles";

/**
 * Outer frame of every route outside the landing itself, in the landing
 * visual system: the `.landing` scope, the skip link, the logo sprite and the
 * same floating pill as the landing navigation (logo back to `/`, one plain
 * link or action, theme selector), then `main` and an optional footer.
 *
 * The frame does not lay out the body: `AuthShell` puts its two columns
 * inside, and a page that needs the full width passes its own container.
 * `main` clips whatever runs past its edges, so decorative marks placed by
 * the body cannot cause horizontal overflow.
 *
 * Presentation only: requests, guards and redirects stay in each page.
 */

interface ShellFrameProps {
  /** Plain link of the pill, pointing at a sibling page. */
  headerLink?: { href: string; label: string };
  /**
   * Control of the pill for pages whose header is not a plain sibling link
   * (e.g. the logout button). Style it with `NAV_LINK`.
   */
  headerAction?: React.ReactNode;
  /** Page footer, below the body (e.g. a standing notice). */
  footer?: React.ReactNode;
  children: React.ReactNode;
}

export default function ShellFrame({
  headerLink,
  headerAction,
  footer,
  children,
}: ShellFrameProps) {
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
        {children}
      </main>

      {footer}
    </div>
  );
}
