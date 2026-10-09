import { useId } from "react";
import { NEXUS_MARK_PATH } from "./nexus-mark-path";

/**
 * Isotipo NEXUS. El degradé usa los tokens semánticos (`--color-accent` →
 * `--color-brand-line`), así que sigue solo al tema claro/oscuro sin lógica extra.
 * Decorativo por defecto: el nombre accesible lo da el texto que lo acompaña.
 */
export function NexusMark({ className }: { className?: string }) {
  const gradId = useId();
  return (
    <svg
      viewBox="0 0 1640 1440"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient
          id={gradId}
          gradientUnits="userSpaceOnUse"
          x1="40"
          y1="1400"
          x2="1600"
          y2="40"
        >
          <stop offset="0" style={{ stopColor: "var(--color-accent)" }} />
          <stop offset="1" style={{ stopColor: "var(--color-brand-line)" }} />
        </linearGradient>
      </defs>
      <path d={NEXUS_MARK_PATH} fill={`url(#${gradId})`} />
    </svg>
  );
}

/** Marca de cabecera: isotipo + nombre, con el mismo tipo de letra de siempre. */
export default function BrandLockup() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <NexusMark className="h-7 w-auto" />
      <span>NEXUS</span>
    </span>
  );
}
