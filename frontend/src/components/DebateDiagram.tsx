/**
 * Diagrama del mecanismo de NEXUS para la sección "Cómo funciona".
 *
 * Tres agentes generan hipótesis en paralelo (Ronda 1), se critican entre sí
 * (Rondas 2 a 4), el Árbitro verifica contra PubMed y agrupa el consenso
 * (con una recitación, Ronda 5, para lo que quedó sin respaldo), el
 * Navegador busca ensayos y sale el reporte.
 *
 * Es decorativo para lectores de pantalla (`aria-hidden`): la misma
 * secuencia vive como lista textual en la sección (`PIPELINE_STEPS`). Los
 * colores salen de los tokens semánticos, así que siguen claro y oscuro.
 */

const AGENTS = [
  { x: 20, id: "01", name: "Analista de Literatura" },
  { x: 200, id: "02", name: "Especialista Genómica" },
  { x: 380, id: "03", name: "Consultor Clínico" },
] as const;

export default function DebateDiagram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="-34 0 594 500"
      aria-hidden="true"
      focusable="false"
      className={className}
      fontFamily="inherit"
    >
      <defs>
        <marker
          id="debate-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M1 1.5 8.5 5 1 8.5Z" className="fill-fg-muted" />
        </marker>
      </defs>

      {/* Ronda 1: análisis en paralelo */}
      <text x="20" y="22" className="fill-fg-muted" fontSize="11" fontWeight="600" letterSpacing="1.4">
        RONDA 1 · ANÁLISIS EN PARALELO
      </text>
      {AGENTS.map((a) => (
        <g key={a.id}>
          <rect x={a.x} y="36" width="160" height="56" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
          <text x={a.x + 14} y="60" className="fill-accent" fontFamily="var(--font-newsreader), Georgia, serif" fontSize="15" fontWeight="600">
            {a.id}
          </text>
          <text x={a.x + 14} y="80" className="fill-fg" fontSize="12.5" fontWeight="500">
            {a.name}
          </text>
          <path d={`M${a.x + 80} 94V114`} className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
        </g>
      ))}

      {/* Rondas 2 a 4: críticas cruzadas */}
      <rect x="20" y="118" width="520" height="44" rx="10" fill="none" className="stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="280" y="145" textAnchor="middle" className="fill-fg" fontSize="12.5" fontWeight="500">
        Rondas 2 a 4 · cada agente critica a los otros dos
      </text>

      {/* Ronda 5: vuelta hacia atrás para lo que quedó sin respaldo */}
      <path d="M40 232H10V140H20" fill="none" className="stroke-accent" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <text transform="rotate(-90 -8 186)" x="-8" y="186" textAnchor="middle" className="fill-accent" fontSize="11" fontWeight="600" letterSpacing="1.2">
        RONDA 5 · RECITACIÓN
      </text>

      {/* Árbitro */}
      <path d="M190 162V196" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="200" width="300" height="64" rx="10" className="fill-accent" />
      <text x="58" y="226" className="fill-accent-fg" fontSize="13.5" fontWeight="600">
        Agente 04 · Árbitro Verificador
      </text>
      <text x="58" y="247" className="fill-accent-fg" fontSize="12">
        Verifica las citas y agrupa el consenso
      </text>

      {/* PubMed */}
      <path d="M340 232H398" className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
      <rect x="402" y="208" width="138" height="48" rx="10" className="fill-bg stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="471" y="237" textAnchor="middle" className="fill-fg" fontSize="12.5" fontWeight="500">
        PubMed
      </text>

      {/* Navegador de ensayos */}
      <path d="M190 264V326" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="330" width="300" height="64" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
      <text x="58" y="356" className="fill-fg" fontSize="13.5" fontWeight="600">
        Agente 05 · Navegador de Ensayos
      </text>
      <text x="58" y="377" className="fill-fg-muted" fontSize="12">
        Busca ensayos y enfermedades raras
      </text>

      {/* Fuentes externas del Navegador */}
      <path d="M340 362H398" className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
      <rect x="402" y="330" width="138" height="64" rx="10" className="fill-bg stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="471" y="357" textAnchor="middle" className="fill-fg" fontSize="12.5" fontWeight="500">
        ClinicalTrials.gov
      </text>
      <text x="471" y="378" textAnchor="middle" className="fill-fg" fontSize="12.5" fontWeight="500">
        Orphanet
      </text>

      {/* Reporte */}
      <path d="M190 394V436" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="440" width="300" height="48" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
      <text x="58" y="469" className="fill-fg" fontSize="13.5" fontWeight="600">
        Reporte · hipótesis por nivel I, II, III
      </text>
    </svg>
  );
}
