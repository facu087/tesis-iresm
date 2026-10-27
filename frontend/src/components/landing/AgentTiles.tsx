"use client";

import { useState } from "react";
import {
  BookOpenTextIcon,
  CompassIcon,
  DnaIcon,
  FileTextIcon,
  PlusIcon,
  ScalesIcon,
  StethoscopeIcon,
} from "@phosphor-icons/react/ssr";
import { FOCUS_RING, TRANSITION } from "@/components/landing/styles";

/**
 * The six agents as compact tiles: icon, number and role name. The one
 * sentence description sits behind the face of each tile and shows on hover
 * (pointer devices), on keyboard focus and on tap or click, which pins it
 * until the tile is activated again. One tile is pinned at a time.
 *
 * Face and description share one grid cell, so a tile is always as tall as
 * its tallest layer and revealing a description never shifts the layout. The
 * description is in the document from the server render and is the accessible
 * description of its button, so it is announced without any interaction.
 * Hover and focus are pure CSS (`.landing-agent` in `globals.css`) and keep
 * working without JavaScript.
 *
 * Descriptions checked against the code: `backend/agents/agent_0{1..6}_*.py`,
 * `.claude/architecture.md` and `.claude/CLAUDE.md`.
 */
const AGENTS = [
  {
    id: "01",
    name: "Analista de Literatura",
    Icon: BookOpenTextIcon,
    description:
      "Genera hipótesis a partir de literatura médica publicada, con búsqueda semántica sobre PubMed como contexto.",
  },
  {
    id: "02",
    name: "Especialista Genómica",
    Icon: DnaIcon,
    description:
      "Analiza el caso desde la genética y la biología molecular, con contexto farmacogenómico de PharmGKB.",
  },
  {
    id: "03",
    name: "Consultor Clínico",
    Icon: StethoscopeIcon,
    description:
      "Razona desde la práctica clínica: diagnóstico diferencial, causas tratables a descartar primero y guías de sociedades médicas.",
  },
  {
    id: "04",
    name: "Árbitro Verificador",
    Icon: ScalesIcon,
    description:
      "Verifica cada referencia contra PubMed, agrupa las hipótesis equivalentes en un consenso y documenta las objeciones sin resolver.",
  },
  {
    id: "05",
    name: "Navegador de Ensayos",
    Icon: CompassIcon,
    description:
      "Busca ensayos clínicos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet.",
  },
  {
    id: "06",
    name: "Sintetizador",
    Icon: FileTextIcon,
    description:
      "Redacta el resumen ejecutivo en prosa una vez armado el reporte estructurado.",
  },
] as const;

const LAYER = "col-start-1 row-start-1 rounded-2xl p-6";

export default function AgentTiles() {
  const [pinned, setPinned] = useState<string | null>(null);

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {AGENTS.map((agent) => {
        const open = pinned === agent.id;
        const detailId = `agente-${agent.id}-detalle`;
        return (
          <li
            key={agent.id}
            data-open={open}
            className="landing-agent grid rounded-2xl border border-border bg-surface"
          >
            <button
              type="button"
              aria-expanded={open}
              aria-describedby={detailId}
              onClick={() => setPinned(open ? null : agent.id)}
              className={`${LAYER} flex cursor-pointer flex-col justify-between gap-4 text-left active:scale-[0.98] ${TRANSITION} ${FOCUS_RING}`}
            >
              <span className="flex items-center justify-between gap-4">
                <agent.Icon aria-hidden="true" className="size-8 text-accent" />
                <span className="font-mono text-sm font-semibold text-fg-muted">
                  <span className="sr-only">Agente </span>
                  {agent.id}
                </span>
              </span>
              <span className="flex items-end justify-between gap-4">
                <span className="text-xl font-semibold text-fg">{agent.name}</span>
                <PlusIcon
                  aria-hidden="true"
                  weight="bold"
                  className="landing-agent-toggle relative z-10 size-5 shrink-0 text-fg-muted"
                />
              </span>
            </button>
            <p
              id={detailId}
              className={`landing-agent-detail ${LAYER} pointer-events-none bg-surface pr-12 text-base text-pretty text-fg`}
            >
              {agent.description}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
