"use client";

import Link from "next/link";
import { ArrowRightIcon } from "@phosphor-icons/react/ssr";
import {
  ACCESS_HINT,
  primaryActionFor,
  useLandingSession,
} from "@/components/landing/LandingSession";
import { PRIMARY_BUTTON, PRIMARY_BUTTON_ON_BRAND } from "@/components/landing/styles";

/**
 * The single primary action of the landing. Without a session it is
 * "Solicitar acceso" → `/registro`, with the licence requirement stated right
 * below it; with one, it is whatever `primaryActionFor` gives that account.
 *
 * The server render, and the page without JavaScript, always show the action
 * of a visitor without a session. The action is not hidden while the session
 * loads: it changes once the session resolves.
 *
 * The hero and the closing section render this same component, so the top and
 * the final call to action cannot drift apart. `tone` only adapts the colours
 * to the surface it sits on.
 */

interface AccessCtaProps {
  /** `id` of the link, used by the navigation to watch the hero action. */
  id?: string;
  tone?: "page" | "brand";
}

export default function AccessCta({ id, tone = "page" }: AccessCtaProps) {
  const { cuenta } = useLandingSession();
  const action = primaryActionFor(cuenta);
  const onBrand = tone === "brand";
  return (
    <div>
      <Link
        id={id}
        href={action.href}
        className={onBrand ? PRIMARY_BUTTON_ON_BRAND : PRIMARY_BUTTON}
      >
        {action.label}
        <ArrowRightIcon aria-hidden="true" weight="bold" className="size-4" />
      </Link>
      {action.showHint && (
        <p
          className={`mt-3 text-sm text-pretty ${onBrand ? "text-brand-fg-muted" : "text-fg-muted"}`}
        >
          {ACCESS_HINT}
        </p>
      )}
    </div>
  );
}
