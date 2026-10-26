import { useId } from "react";

/**
 * One appearance of the NEXUS mark on the landing, drawn from the shared
 * sprite (`LandingMarkSprite`, rendered once by the page).
 *
 * The gradient lives here and not in the sprite: its stops read
 * `--landing-mark-from` and `--landing-mark-to` where this element sits, so
 * each surface (page, navy card) can rebind them in `globals.css`. Same
 * geometry as the shared `NexusMark`: bottom left to top right.
 *
 * Always decorative: the accessible name comes from the text beside it.
 */

/**
 * `id` of the sprite symbol. Declared here, not in the sprite, because that
 * file is a Client Component and Server Components cannot read its constants.
 */
export const LANDING_MARK_SYMBOL_ID = "landing-mark-symbol";

/** Coordinate system of the outline, shared by the symbol and its uses. */
export const LANDING_MARK_VIEW_BOX = "0 0 1640 1440";

export default function LandingMark({ className }: { className?: string }) {
  const gradientId = useId();
  return (
    <svg
      viewBox={LANDING_MARK_VIEW_BOX}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient
          id={gradientId}
          gradientUnits="userSpaceOnUse"
          x1="40"
          y1="1400"
          x2="1600"
          y2="40"
        >
          <stop offset="0" style={{ stopColor: "var(--landing-mark-from)" }} />
          <stop offset="1" style={{ stopColor: "var(--landing-mark-to)" }} />
        </linearGradient>
      </defs>
      <use href={`#${LANDING_MARK_SYMBOL_ID}`} fill={`url(#${gradientId})`} />
    </svg>
  );
}
