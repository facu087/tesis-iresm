/**
 * Iconos SVG inline, hechos a medida (design D7): sin librería de iconos,
 * coherente con "sin librerías de UI" del stack. Trazo con `currentColor`
 * para heredar el color de texto del contenedor (y adaptarse a claro/oscuro
 * sin lógica extra).
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

/** Agente 01 — Analista de Literatura: libro abierto. */
export function BookIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M4 5.5C4 4.67 4.67 4 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5v-13Z" />
      <path d="M20 5.5c0-.83-.67-1.5-1.5-1.5H13v16h5.5c.83 0 1.5-.67 1.5-1.5v-13Z" />
    </svg>
  );
}

/** Agente 02 — Especialista Genómica: doble hélice esquemática. */
export function DnaIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M7 3c0 4-3 4.5-3 8.5S7 20 7 20" />
      <path d="M17 3c0 4 3 4.5 3 8.5S17 20 17 20" />
      <path d="M5.5 7h13" />
      <path d="M4.5 11.5h15" />
      <path d="M5.5 16h13" />
    </svg>
  );
}

/** Agente 03 — Consultor Clínico: pulso clínico. */
export function PulseIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M3 12h4l2-6 4 12 2-6h6" />
    </svg>
  );
}

/** Agente 04 — Árbitro Verificador: balanza. */
export function ScaleIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M5 6h14" />
      <path d="M12 6v13" />
      <path d="M8 21h8" />
      <path d="M5 6 3 11a2.5 2.5 0 0 0 5 0L5 6Z" />
      <path d="M19 6l-2 5a2.5 2.5 0 0 0 5 0l-2-5Z" />
    </svg>
  );
}

/** Agente 05 — Navegador de Ensayos: brújula. */
export function CompassIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <circle cx="12" cy="12" r="9" />
      <polygon points="15.5 8.5 13.3 13.3 8.5 15.5 10.7 10.7 15.5 8.5" />
    </svg>
  );
}

/** Agente 06 — Sintetizador (pendiente): documento en blanco. */
export function DocumentIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M7 3.5h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-16a1 1 0 0 1 1-1Z" />
      <path d="M14 3.5V8h4" />
      <path d="M9 13h6" strokeDasharray="1.5 2.5" />
      <path d="M9 16.5h6" strokeDasharray="1.5 2.5" />
    </svg>
  );
}

/** Formulario de carga — archivo seleccionado: check dentro de un círculo. */
export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.2 2.3 2.3 4.7-4.9" />
    </svg>
  );
}

/** Funcionalidad — verificación bibliográfica: escudo con check. */
export function ShieldCheckIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="M12 3.5 5 6v6c0 4.5 3 7.5 7 8.5 4-1 7-4 7-8.5V6l-7-2.5Z" />
      <path d="m9 12 2 2 4-4.5" />
    </svg>
  );
}

/** Funcionalidad — clasificación EBM: capas/niveles. */
export function LayersIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <path d="m12 3.5 8 4.5-8 4.5-8-4.5 8-4.5Z" />
      <path d="m4 12 8 4.5 8-4.5" />
      <path d="m4 15.5 8 4.5 8-4.5" />
    </svg>
  );
}

/** Funcionalidad — navegación de ensayos: lupa. */
export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m20 20-4.3-4.3" />
    </svg>
  );
}

/** Funcionalidad — debate adversarial multi-agente: dos burbujas de diálogo. */
export function DebateIcon({ className }: IconProps) {
  return (
    <svg {...BASE_PROPS} className={className}>
      <rect x="2.5" y="4.5" width="13" height="8" rx="3" />
      <rect x="8.5" y="12.5" width="13" height="7" rx="3" />
    </svg>
  );
}
