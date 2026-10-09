/**
 * Diagram of the NEXUS mechanism for the "Cómo funciona" section.
 *
 * Three agents generate hypotheses in parallel (Round 1), criticise each
 * other (Rounds 2 to 4), the Arbiter verifies against PubMed and groups the
 * consensus (with a recitation, Round 5, for what was left unbacked), the
 * Navigator looks for trials, the structured report is built and the
 * Synthesizer adds the executive summary.
 *
 * Decorative for screen readers (`aria-hidden`): the same sequence lives as a
 * text list in the section (`PIPELINE_STEPS`). Colours come from the semantic
 * tokens, so they follow the light and the dark theme. Font sizes are SVG
 * user units on the Tailwind scale steps (12 and 14).
 */

const AGENTS = [
  { x: 20, id: "01", name: "Analista de Literatura" },
  { x: 200, id: "02", name: "Especialista Genómica" },
  { x: 380, id: "03", name: "Consultor Clínico" },
] as const;

export default function DebateDiagram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="-34 0 594 606"
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

      {/* Round 1: parallel analysis */}
      <text x="20" y="22" className="fill-fg-muted" fontSize="12" fontWeight="600">
        Ronda 1 · análisis en paralelo
      </text>
      {AGENTS.map((a) => (
        <g key={a.id}>
          <rect x={a.x} y="36" width="160" height="56" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
          <text x={a.x + 14} y="60" className="fill-accent" fontFamily="var(--font-geist-mono), monospace" fontSize="14" fontWeight="600">
            {a.id}
          </text>
          <text x={a.x + 14} y="80" className="fill-fg" fontSize="12" fontWeight="500">
            {a.name}
          </text>
          <path d={`M${a.x + 80} 94V114`} className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
        </g>
      ))}

      {/* Rounds 2 to 4: cross criticism */}
      <rect x="20" y="118" width="520" height="44" rx="10" fill="none" className="stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="280" y="145" textAnchor="middle" className="fill-fg" fontSize="12" fontWeight="500">
        Rondas 2 a 4 · cada agente critica a los otros dos
      </text>

      {/* Round 5: the way back for what was left unbacked */}
      <path d="M40 232H10V140H20" fill="none" className="stroke-accent" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <text transform="rotate(-90 -8 186)" x="-8" y="186" textAnchor="middle" className="fill-accent" fontSize="12" fontWeight="600">
        Ronda 5 · recitación
      </text>

      {/* Arbiter */}
      <path d="M190 162V196" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="200" width="300" height="64" rx="10" className="fill-accent" />
      <text x="58" y="226" className="fill-accent-fg" fontSize="14" fontWeight="600">
        Agente 04 · Árbitro Verificador
      </text>
      <text x="58" y="247" className="fill-accent-fg" fontSize="12">
        Verifica las citas y agrupa el consenso
      </text>

      {/* PubMed */}
      <path d="M340 232H398" className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
      <rect x="402" y="208" width="138" height="48" rx="10" className="fill-bg stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="471" y="237" textAnchor="middle" className="fill-fg" fontSize="12" fontWeight="500">
        PubMed
      </text>

      {/* Trial navigator */}
      <path d="M190 264V326" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="330" width="300" height="64" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
      <text x="58" y="356" className="fill-fg" fontSize="14" fontWeight="600">
        Agente 05 · Navegador de Ensayos
      </text>
      <text x="58" y="377" className="fill-fg-muted" fontSize="12">
        Busca ensayos y enfermedades raras
      </text>

      {/* External sources of the navigator */}
      <path d="M340 362H398" className="stroke-fg-muted" strokeWidth="1.5" markerStart="url(#debate-arrow)" markerEnd="url(#debate-arrow)" />
      <rect x="402" y="330" width="138" height="64" rx="10" className="fill-bg stroke-fg-muted" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x="471" y="357" textAnchor="middle" className="fill-fg" fontSize="12" fontWeight="500">
        ClinicalTrials.gov
      </text>
      <text x="471" y="378" textAnchor="middle" className="fill-fg" fontSize="12" fontWeight="500">
        Orphanet
      </text>

      {/* Structured report */}
      <path d="M190 394V436" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="440" width="300" height="48" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
      <text x="58" y="469" className="fill-fg" fontSize="14" fontWeight="600">
        Reporte · niveles I, II y III
      </text>

      {/* Synthesizer: adds the executive summary to the built report */}
      <path d="M190 488V526" className="stroke-fg-muted" strokeWidth="1.5" markerEnd="url(#debate-arrow)" />
      <rect x="40" y="530" width="300" height="64" rx="10" className="fill-bg-subtle stroke-accent" strokeWidth="1.5" />
      <text x="58" y="556" className="fill-fg" fontSize="14" fontWeight="600">
        Agente 06 · Sintetizador
      </text>
      <text x="58" y="577" className="fill-fg-muted" fontSize="12">
        Agrega el resumen ejecutivo al reporte
      </text>
    </svg>
  );
}
