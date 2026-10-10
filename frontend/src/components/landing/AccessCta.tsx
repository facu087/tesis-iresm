import Link from "next/link";
import { ArrowRightIcon } from "@phosphor-icons/react/ssr";
import { PRIMARY_BUTTON, PRIMARY_BUTTON_ON_BRAND } from "@/components/landing/styles";

/**
 * The single primary action of the landing: "Solicitar acceso" → `/registro`,
 * with the licence requirement stated right below it.
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
  const onBrand = tone === "brand";
  return (
    <div>
      <Link
        id={id}
        href="/registro"
        className={onBrand ? PRIMARY_BUTTON_ON_BRAND : PRIMARY_BUTTON}
      >
        Solicitar acceso
        <ArrowRightIcon aria-hidden="true" weight="bold" className="size-4" />
      </Link>
      <p
        className={`mt-3 text-sm text-pretty ${onBrand ? "text-brand-fg-muted" : "text-fg-muted"}`}
      >
        Requiere matrícula médica. Un administrador revisa cada solicitud.
      </p>
    </div>
  );
}
