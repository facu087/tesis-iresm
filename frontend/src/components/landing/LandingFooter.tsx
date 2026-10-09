import Link from "next/link";
import type { NavLink } from "@/components/landing/IslandNav";
import { CONTAINER, FOCUS_RING, TRANSITION } from "@/components/landing/styles";

/**
 * Footer of the landing: scope notice, every navigation link again (the way
 * to reach each section on mobile without JavaScript) and the thesis credit.
 *
 * No privacy policy or terms links: those pages do not exist and no legal
 * text is invented here.
 */

const FOOTER_LINK = `rounded-sm text-sm font-semibold text-fg-muted ${TRANSITION} hover:text-accent active:translate-y-px ${FOCUS_RING}`;

export default function LandingFooter({ links }: { links: readonly NavLink[] }) {
  return (
    <footer className="bg-bg py-12">
      <div className={`${CONTAINER} grid gap-8 lg:grid-cols-12`}>
        <div className="lg:col-span-6">
          <p className="text-base font-bold text-accent">NEXUS</p>
          <p className="mt-3 max-w-[680px] text-sm text-pretty text-fg-muted">
            NEXUS no emite diagnósticos clínicos. Las hipótesis generadas son
            orientativas y deben ser evaluadas por el médico responsable.
          </p>
        </div>

        <nav aria-label="Pie de página" className="lg:col-span-6">
          <ul className="flex flex-wrap gap-x-6 gap-y-3 lg:justify-end">
            {links.map((link) => (
              <li key={link.href}>
                <a href={link.href} className={FOOTER_LINK}>
                  {link.label}
                </a>
              </li>
            ))}
            <li>
              <Link href="/ingresar" className={FOOTER_LINK}>
                Ingresar
              </Link>
            </li>
            <li>
              <Link href="/registro" className={FOOTER_LINK}>
                Solicitar acceso
              </Link>
            </li>
          </ul>
        </nav>

        <p className="text-xs text-fg-muted lg:col-span-12">
          Tesis final · Analista en Sistemas · IRESM, Villa Carlos Paz · 2026
        </p>
      </div>
    </footer>
  );
}
