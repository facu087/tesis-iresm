"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { UserIcon } from "@phosphor-icons/react/ssr";
import LandingLogo from "@/components/landing/LandingLogo";
import {
  ACCESS_HINT,
  primaryActionFor,
  useLandingSession,
} from "@/components/landing/LandingSession";
import ThemeToggle from "@/components/ThemeToggle";
import {
  EASE,
  FOCUS_RING,
  HEADER_BUTTON,
  NAV_LINK,
  PRIMARY_BUTTON,
  TRANSITION,
} from "@/components/landing/styles";

/**
 * Floating navigation of the landing: a glass pill detached from the top.
 *
 * Desktop: section links, the account link and the theme selector. The
 * primary action joins the pill only once the hero button has scrolled out of
 * view, so there is a single primary action above the fold.
 *
 * The account link follows the landing session: "Ingresar" without one, the
 * user's name linking to `/cuenta` with one, plus "Cuentas pendientes" for an
 * admin. While the session loads the link is marked `data-session-pending`,
 * which hides it only when scripting is enabled (see `globals.css`), so
 * "Ingresar" never flashes into the name. The primary action comes from
 * `primaryActionFor`, the same helper the hero uses.
 *
 * Mobile: a hamburger whose two lines rotate into an X opens a screen filling
 * glass overlay with the links revealed in a staggered slide up. The overlay
 * is keyboard operable: `aria-expanded` on the trigger, focus moves into the
 * menu on open and back to the trigger on Escape, Tab cycles inside the
 * header while it is open, and the page behind does not scroll.
 *
 * Without JavaScript the pill still shows the wordmark and, from `lg` up, the
 * links; the footer repeats every link for the mobile case.
 */

export interface NavLink {
  href: string;
  label: string;
}

interface IslandNavProps {
  /** In page section links, in page order. */
  links: readonly NavLink[];
  /** `id` of the hero primary action, watched to reveal the pill action. */
  heroActionId: string;
}

/** Stagger of the overlay items, one step per item. */
const STAGGER = [
  "delay-100",
  "delay-150",
  "delay-200",
  "delay-250",
  "delay-300",
  "delay-350",
] as const;

const DESKTOP_QUERY = "(min-width: 1024px)";

/** A link that depends on the session, rendered by the pill and the overlay. */
interface AccountLink {
  href: string;
  label: string;
  /** Accessible name, when it says more than the visible label. */
  ariaLabel?: string;
  /** The link to the signed in user's account, drawn with a user icon. */
  isUser?: boolean;
}

export default function IslandNav({ links, heroActionId }: IslandNavProps) {
  const [open, setOpen] = useState(false);
  const [heroActionVisible, setHeroActionVisible] = useState(true);
  const [activeHref, setActiveHref] = useState<string | null>(null);

  const { status, cuenta } = useLandingSession();
  const action = primaryActionFor(cuenta);
  const sessionPending = status === "loading";

  const accountLinks: AccountLink[] = [];
  if (cuenta === null) {
    accountLinks.push({ href: "/ingresar", label: "Ingresar" });
  } else {
    const nombre = cuenta.nombre?.trim() ?? "";
    accountLinks.push({
      href: "/cuenta",
      label: nombre || "Mi cuenta",
      ariaLabel: nombre ? `Mi cuenta, ${nombre}` : "Mi cuenta",
      isUser: true,
    });
    if (cuenta.rol === "admin") {
      accountLinks.push({ href: "/admin/pendientes", label: "Cuentas pendientes" });
    }
  }
  // Overlay list: the section links first, then the session dependent ones.
  const menuItems: AccountLink[] = [...links, ...accountLinks];
  // When an account link already leads where the primary action does (an
  // admin, a physician whose account is not verified), the action is not
  // repeated next to it.
  const actionIsAccountLink = accountLinks.some((link) => link.href === action.href);

  const headerRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLAnchorElement>(null);

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  }, []);

  // Reveal the pill action once the hero action leaves the viewport.
  useEffect(() => {
    const heroAction = document.getElementById(heroActionId);
    if (!heroAction) return;
    // A batch can queue several records for the same target: the last one is
    // the current state.
    const observer = new IntersectionObserver((entries) => {
      const latest = entries[entries.length - 1];
      if (latest) setHeroActionVisible(latest.isIntersecting);
    });
    observer.observe(heroAction);
    return () => observer.disconnect();
  }, [heroActionId]);

  // Mark the section currently crossing the middle band of the viewport.
  useEffect(() => {
    const sections = links
      .map((link) => document.getElementById(link.href.slice(1)))
      .filter((section): section is HTMLElement => section !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const href = `#${entry.target.id}`;
          if (entry.isIntersecting) setActiveHref(href);
          else setActiveHref((current) => (current === href ? null : current));
        }
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [links]);

  // While the overlay is open: lock page scroll, move focus into the menu,
  // handle Escape and the focus trap, and close it if the viewport grows into
  // the desktop layout.
  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    firstItemRef.current?.focus();

    const desktop = window.matchMedia(DESKTOP_QUERY);
    const onChange = () => {
      if (desktop.matches) setOpen(false);
    };
    desktop.addEventListener("change", onChange);

    // Listened on the document, not on the header: a tap on an empty area of
    // the overlay moves focus to the body, and the keys must keep working.
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close(true);
        return;
      }
      const header = headerRef.current;
      if (event.key !== "Tab" || !header) return;

      // Focus trap: cycle through what is focusable and rendered in the header.
      const focusable = Array.from(
        header.querySelectorAll<HTMLElement>("a[href], button"),
      ).filter(
        (element) =>
          element.closest("[inert]") === null &&
          element.getClientRects().length > 0 &&
          // The account link is hidden, not removed, while the session loads.
          getComputedStyle(element).visibility !== "hidden",
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (!header.contains(active)) {
        // Focus escaped the menu: bring it back in.
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      desktop.removeEventListener("change", onChange);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, close]);

  const showPillAction = !heroActionVisible && !actionIsAccountLink;

  return (
    <header
      ref={headerRef}
      className="pointer-events-none fixed inset-x-0 top-0 z-50 px-4"
    >
      {/* Closed state: floating glass pill */}
      <div
        className={`pointer-events-auto relative z-10 mx-auto mt-6 flex w-max max-w-full items-center gap-2 rounded-full border border-border bg-white/80 p-2 backdrop-blur-xl dark:bg-black/80 ${TRANSITION}`}
      >
        <Link
          href="/"
          aria-current="page"
          aria-label="NEXUS, inicio"
          className={`inline-flex items-center rounded-full px-3 py-2 text-base font-bold text-accent ${TRANSITION} hover:opacity-80 active:translate-y-px ${FOCUS_RING}`}
        >
          <LandingLogo fromSprite />
        </Link>

        <nav aria-label="Principal" className="hidden items-center lg:flex">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              aria-current={activeHref === link.href ? "location" : undefined}
              className={NAV_LINK}
            >
              {link.label}
            </a>
          ))}
          {accountLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.ariaLabel}
              data-session-pending={sessionPending ? "" : undefined}
              className={link.isUser ? `inline-flex items-center gap-2 ${NAV_LINK}` : NAV_LINK}
            >
              {link.isUser && (
                <UserIcon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
              )}
              {link.isUser ? <span className="max-w-32 truncate">{link.label}</span> : link.label}
            </Link>
          ))}
        </nav>

        <ThemeToggle />

        {/* Pill action: collapsed while the hero action is on screen */}
        <div
          inert={!showPillAction}
          className={`hidden transition-[grid-template-columns,opacity] duration-700 lg:grid ${EASE} ${
            showPillAction ? "grid-cols-[1fr] opacity-100" : "grid-cols-[0fr] opacity-0"
          }`}
        >
          <div className="min-w-0 overflow-hidden rounded-full">
            <Link href={action.href} className={HEADER_BUTTON}>
              {action.label}
            </Link>
          </div>
        </div>

        {/* Hamburger: two lines that rotate into an X, never disappear */}
        <button
          ref={triggerRef}
          type="button"
          aria-expanded={open}
          aria-controls="landing-menu"
          aria-label={open ? "Cerrar el menú" : "Abrir el menú"}
          onClick={() => (open ? close(false) : setOpen(true))}
          className={`relative size-10 shrink-0 cursor-pointer rounded-full lg:hidden ${TRANSITION} hover:bg-bg-subtle active:scale-[0.98] ${FOCUS_RING}`}
        >
          <span
            aria-hidden="true"
            className={`absolute inset-0 m-auto h-0.5 w-4 rounded-full bg-fg ${TRANSITION} ${
              open ? "rotate-45" : "-translate-y-1"
            }`}
          />
          <span
            aria-hidden="true"
            className={`absolute inset-0 m-auto h-0.5 w-4 rounded-full bg-fg ${TRANSITION} ${
              open ? "-rotate-45" : "translate-y-1"
            }`}
          />
        </button>
      </div>

      {/* Expanded state: screen filling glass overlay */}
      <div
        id="landing-menu"
        role="dialog"
        aria-modal="true"
        aria-label="Menú de navegación"
        inert={!open}
        className={`fixed inset-0 overflow-y-auto bg-white/80 backdrop-blur-3xl lg:hidden dark:bg-black/80 ${TRANSITION} ${
          open
            ? "pointer-events-auto visible opacity-100"
            : "pointer-events-none invisible opacity-0"
        }`}
      >
        <nav
          aria-label="Menú"
          className="mx-auto flex min-h-full max-w-6xl flex-col justify-center px-6 pt-24 pb-12"
        >
          <ul className="flex flex-col gap-2">
            {menuItems.map((link, index) => (
              // The list item is the "invisible box" the link slides out of.
              <li key={link.href} className="overflow-hidden p-1">
                <Link
                  ref={index === 0 ? firstItemRef : undefined}
                  href={link.href}
                  aria-label={link.ariaLabel}
                  data-session-pending={
                    sessionPending && index >= links.length ? "" : undefined
                  }
                  onClick={() => close(false)}
                  className={`${
                    link.isUser ? "flex items-center gap-2" : "block"
                  } rounded-lg py-2 text-3xl font-semibold text-fg ${TRANSITION} hover:text-accent ${FOCUS_RING} ${
                    open
                      ? `translate-y-0 opacity-100 ${STAGGER[index % STAGGER.length]}`
                      : "translate-y-12 opacity-0"
                  }`}
                >
                  {link.isUser && (
                    <UserIcon aria-hidden="true" weight="bold" className="size-6 shrink-0" />
                  )}
                  {link.isUser ? (
                    <span className="min-w-0 truncate">{link.label}</span>
                  ) : (
                    link.label
                  )}
                </Link>
              </li>
            ))}
          </ul>

          {!actionIsAccountLink && (
            <div
              className={`mt-10 p-1 ${TRANSITION} ${
                open ? "translate-y-0 opacity-100 delay-500" : "translate-y-12 opacity-0"
              }`}
            >
              <Link
                href={action.href}
                onClick={() => close(false)}
                className={PRIMARY_BUTTON}
              >
                {action.label}
              </Link>
              {action.showHint && (
                <p className="mt-3 text-sm text-pretty text-fg-muted">{ACCESS_HINT}</p>
              )}
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
