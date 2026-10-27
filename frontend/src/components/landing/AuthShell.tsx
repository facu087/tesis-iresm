import LandingMark from "@/components/landing/LandingMark";
import ShellFrame from "@/components/landing/ShellFrame";
import { CONTAINER } from "@/components/landing/styles";

/**
 * Page frame of the access routes (`/registro`, `/ingresar`) and of the
 * signed in routes (`/cuenta`, `/analizar`, `/admin/pendientes`), in the
 * landing visual system: the shared `ShellFrame` (the `.landing` scope and
 * the floating pill) around a two column body with the page heading beside
 * the form.
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
    <ShellFrame headerLink={headerLink} headerAction={headerAction} footer={footer}>
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
    </ShellFrame>
  );
}
