/**
 * Shared class strings of the landing.
 *
 * Every value resolves through the landing visual system: Tailwind's type
 * scale, the closed spacing table (0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80
 * and 96 px), Tailwind radii and one easing curve for every transition.
 */

/** Spring like curve used by every transition of the landing. */
export const EASE = "ease-[cubic-bezier(0.32,0.72,0,1)]";

/** Standard transition: all properties, 700 ms, landing curve. */
export const TRANSITION = `transition-all duration-700 ${EASE}`;

/** Visible focus ring on regular (light or dark page) surfaces. */
export const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

/** Visible focus ring on the navy brand surface. */
export const FOCUS_RING_ON_BRAND =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-fg";

/** Hover, active and focus feedback shared by every button like link. */
const BUTTON_STATES = `${TRANSITION} hover:opacity-90 motion-safe:hover:-translate-y-0.5 active:scale-[0.98]`;

/** Main button: 16 px semibold, 8 px vertical and 12 px horizontal padding. */
export const PRIMARY_BUTTON = `inline-flex items-center justify-center gap-2 rounded-full bg-accent px-3 py-2 text-base font-semibold text-accent-fg ${BUTTON_STATES} ${FOCUS_RING}`;

/** Main button on the navy brand surface. */
export const PRIMARY_BUTTON_ON_BRAND = `inline-flex items-center justify-center gap-2 rounded-full bg-brand-btn px-3 py-2 text-base font-semibold text-brand-btn-fg ${BUTTON_STATES} ${FOCUS_RING_ON_BRAND}`;

/** Smaller header button: 14 px semibold. */
export const HEADER_BUTTON = `inline-flex items-center justify-center gap-2 rounded-full bg-accent px-3 py-2 text-sm font-semibold whitespace-nowrap text-accent-fg ${BUTTON_STATES} ${FOCUS_RING}`;

/** Plain text link (navigation, footer, inline references). */
export const TEXT_LINK = `rounded-sm font-semibold text-accent underline-offset-4 ${TRANSITION} hover:underline active:translate-y-px ${FOCUS_RING}`;

/** Navigation link inside the header pill. */
export const NAV_LINK = `rounded-full px-3 py-2 text-sm font-semibold whitespace-nowrap text-fg-muted ${TRANSITION} hover:text-accent active:translate-y-px aria-[current=location]:text-accent ${FOCUS_RING}`;

/** Full width submit button of a form, with its pending (disabled) state. */
export const SUBMIT_BUTTON = `${PRIMARY_BUTTON} w-full cursor-pointer disabled:pointer-events-none disabled:opacity-60`;

/** Horizontal page container. */
export const CONTAINER = "mx-auto w-full max-w-6xl px-4 sm:px-6";

/** Vertical rhythm of a regular section. */
export const SECTION_PADDING = "py-16 sm:py-24";

/** Card: border all the way around, flat surface. */
export const CARD = "rounded-2xl border border-border bg-surface p-6";
