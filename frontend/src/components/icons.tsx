/**
 * Iconos SVG inline, hechos a medida (design D7). Trazo con `currentColor`
 * para heredar el color de texto del contenedor (y adaptarse a claro/oscuro
 * sin lógica extra).
 *
 * Only the theme toggle still draws from here: every other icon of the
 * product comes from Phosphor (`@phosphor-icons/react`).
 */

type IconProps = { className?: string };

const BASE_PROPS = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

/** Selector de tema — sol: acción "cambiar a tema claro". */
export function SunIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
    </svg>
  );
}

/** Selector de tema — luna: acción "cambiar a tema oscuro". */
export function MoonIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
    </svg>
  );
}
