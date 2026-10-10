"use client";

import { NexusMark } from "@/components/NexusLogo";
import LandingMark from "@/components/landing/LandingMark";

/**
 * Brand lockup for the landing pill and the 404: mark plus wordmark.
 *
 * The shared mark fades from `--color-accent` to `--color-brand-line`. Inside
 * the landing that second token is a border grey in the dark theme, which
 * makes half of the mark disappear, so `.landing-logo` rebinds it (see
 * `globals.css`) instead of changing the shared component.
 *
 * `fromSprite` draws the mark from the sprite the landing page renders once
 * (`LandingMarkSprite`) instead of inlining the outline again. Only pass it
 * where that sprite is on the page: the 404 has none and keeps the default.
 *
 * Client Component on purpose: the 404 is a Server Component whose output
 * travels in the flight payload of every page, so rendering the outline on
 * the server put its 34 kB in the landing HTML as well.
 */
export default function LandingLogo({ fromSprite = false }: { fromSprite?: boolean }) {
  return (
    <span className="landing-logo inline-flex items-center gap-2">
      {fromSprite ? (
        <LandingMark className="h-8 w-auto" />
      ) : (
        <NexusMark className="h-8 w-auto" />
      )}
      <span>NEXUS</span>
    </span>
  );
}
