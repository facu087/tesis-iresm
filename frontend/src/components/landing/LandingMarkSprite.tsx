"use client";

import {
  LANDING_MARK_SYMBOL_ID,
  LANDING_MARK_VIEW_BOX,
} from "@/components/landing/LandingMark";
import { NEXUS_MARK_PATH } from "@/components/nexus-mark-path";

/**
 * Single definition of the NEXUS mark outline for the landing.
 *
 * The outline is about 34 kB of path data. The landing shows the mark in
 * several places (navigation, hero, closing card), so the page renders this
 * hidden sprite once and every appearance points at it with `<use>` through
 * `LandingMark`.
 *
 * Client Component on purpose: the output of a Server Component is also
 * serialised into the inline flight payload, which would put the path data
 * in the HTML a second time. A Client Component is rendered to HTML once and
 * its markup is not part of that payload.
 *
 * The path carries no fill, so each `<use>` paints it with its own gradient.
 */

export default function LandingMarkSprite() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="0"
      height="0"
      className="pointer-events-none absolute"
    >
      <symbol id={LANDING_MARK_SYMBOL_ID} viewBox={LANDING_MARK_VIEW_BOX}>
        <path d={NEXUS_MARK_PATH} />
      </symbol>
    </svg>
  );
}
