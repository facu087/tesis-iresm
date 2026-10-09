"use client";

import { useEffect, useRef } from "react";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";

/**
 * Pipeline diagram of "Cómo funciona": the eight real stages as a vertical
 * flow whose nodes light up in order as the user scrolls through it.
 *
 * The stages, their order and their titles come from `PIPELINE_STEPS` (shared
 * with `/analizar`, not edited here). This file only adds the short line shown
 * under each title and the agents that run in each stage, so all six agents
 * appear on the diagram. Agent 06 writes the executive summary once the
 * structured report is built (`backend/agents/agent_06_synthesizer.py`).
 *
 * Progressive enhancement, same contract as `TaglineReveal`: the server sends
 * every stage lit, so the diagram is complete without JavaScript. After
 * mounting, and only if the user did not ask for reduced motion, the list is
 * marked as enhanced (pending stages dim, see `.landing-pipeline` in
 * `globals.css`) and one `IntersectionObserver` lights each stage when it
 * crosses the trigger line. Progress only moves forward: a lit stage never
 * dims again, and lighting a stage lights every stage before it.
 *
 * The drawing borrows the vocabulary of the NEXUS mark: round filled nodes
 * that alternate between two columns, joined by a thick stroke that curves
 * from one to the next. Lit, the column runs through the gradient of the mark
 * from the first stage to the last: each link fades between the tints of the
 * two nodes it joins (`--landing-stage-from` and `--landing-stage-to`).
 */

/** Short line and agents per stage, keyed by the shared step `id`. */
const STAGE_DETAILS: Record<string, { line: string; agents?: readonly string[] }> = {
  "01": { line: "Texto del PDF, nativo o escaneado." },
  "02": { line: "Nombres de fármacos y unidades de medida." },
  "03": { line: "Contexto clínico estructurado del caso." },
  "04": { line: "Tres agentes generan hipótesis sin verse.", agents: ["01", "02", "03"] },
  "05": { line: "Cada uno critica a los demás y revisa lo propio.", agents: ["01", "02", "03"] },
  "06": { line: "Citas contra PubMed, consenso y recitación.", agents: ["04"] },
  "07": { line: "ClinicalTrials.gov y Orphanet.", agents: ["05"] },
  "08": { line: "Niveles I, II y III, con resumen ejecutivo.", agents: ["06"] },
};

/** Share of the viewport, from the bottom, a stage must clear to light up. */
const TRIGGER_MARGIN = "0px 0px -25% 0px";

/** Display form of a shared step label: the dash becomes a colon. */
function displayLabel(label: string): string {
  return label.replace(" — ", ": ");
}

/** Horizontal centre of a node in the 64 px rail: left column or right one. */
const NODE_CENTER = { left: 20, right: 44 } as const;

/** Position of a stage along the gradient, as the tints of its node and link. */
function stagePosition(index: number, lastIndex: number): React.CSSProperties {
  const percent = (position: number) => `${Math.round((position / lastIndex) * 100)}%`;
  return {
    "--landing-stage-from": percent(index),
    "--landing-stage-to": percent(Math.min(index + 1, lastIndex)),
  } as React.CSSProperties;
}

/**
 * Curved stroke from the centre of a node to the centre of the next one.
 *
 * It is as tall as the stage and starts half a node down, which is exactly
 * centre to centre; stretched like that, the stroke keeps its width with
 * `vector-effect`. The page draws it twice: a neutral track and, on top, the
 * lit stroke painted with the gradient, which `globals.css` unveils downwards.
 */
function StageLink({
  id,
  fromOffset,
  lit = false,
}: {
  id: string;
  fromOffset: boolean;
  lit?: boolean;
}) {
  const from = fromOffset ? NODE_CENTER.right : NODE_CENTER.left;
  const to = fromOffset ? NODE_CENTER.left : NODE_CENTER.right;
  const gradientId = `landing-pipeline-link-${id}`;
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 64 100"
      preserveAspectRatio="none"
      className={`absolute top-5 left-0 h-full w-16 ${lit ? "landing-pipeline-link-lit" : "landing-pipeline-link"}`}
    >
      {lit && (
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" className="landing-pipeline-stop-from" />
            <stop offset="1" className="landing-pipeline-stop-to" />
          </linearGradient>
        </defs>
      )}
      <path
        d={`M${from} 0 C${from} 50 ${to} 50 ${to} 100`}
        fill="none"
        stroke={lit ? `url(#${gradientId})` : "currentColor"}
        strokeWidth="6"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export default function PipelineDiagram() {
  const ref = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const list = ref.current;
    if (!list) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const stages = Array.from(list.querySelectorAll<HTMLElement>("[data-stage]"));
    if (stages.length === 0) return;

    let lit = 0;
    const lightThrough = (index: number) => {
      while (lit <= index) {
        stages[lit].dataset.on = "true";
        lit += 1;
      }
      if (lit === stages.length) observer.disconnect();
    };

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // A stage counts once it is on or above the trigger line, so a
          // reload in the middle of the page starts with the passed ones lit.
          const line = entry.rootBounds?.bottom ?? window.innerHeight;
          if (entry.isIntersecting || entry.boundingClientRect.top < line) {
            lightThrough(stages.indexOf(entry.target as HTMLElement));
          }
        }
      },
      { rootMargin: TRIGGER_MARGIN },
    );

    list.dataset.enhanced = "true";
    for (const stage of stages) observer.observe(stage);

    return () => {
      observer.disconnect();
      // Leave the diagram fully lit if the component goes away.
      delete list.dataset.enhanced;
      for (const stage of stages) delete stage.dataset.on;
    };
  }, []);

  const lastIndex = PIPELINE_STEPS.length - 1;

  return (
    <ol ref={ref} className="landing-pipeline">
      {PIPELINE_STEPS.map((step, index) => {
        const detail = STAGE_DETAILS[step.id];
        const isLast = index === lastIndex;
        const isOffset = index % 2 === 1;
        return (
          <li
            key={step.id}
            data-stage
            style={stagePosition(index, lastIndex)}
            className={`relative grid grid-cols-[4rem_1fr] gap-4 ${isLast ? "" : "pb-8"}`}
          >
            {!isLast && (
              <>
                <StageLink id={step.id} fromOffset={isOffset} />
                <StageLink id={step.id} fromOffset={isOffset} lit />
              </>
            )}
            <span
              aria-hidden="true"
              className={`landing-pipeline-node relative flex size-10 items-center justify-center rounded-full border-2 font-mono text-sm font-semibold ${isOffset ? "ml-6" : ""}`}
            >
              {step.id}
            </span>
            <div className="landing-pipeline-body pt-1">
              <h3 className="text-lg font-semibold text-fg">
                <span className="sr-only">Etapa {step.id}: </span>
                {displayLabel(step.label)}
              </h3>
              <p className="mt-1 text-base text-pretty text-fg-muted">
                {detail?.line ?? step.description}
              </p>
              {detail?.agents && (
                <ul className="mt-3 flex flex-wrap gap-2">
                  {detail.agents.map((agent) => (
                    <li
                      key={agent}
                      className="rounded-md border border-accent px-2 py-1 font-mono text-xs font-semibold text-accent"
                    >
                      Agente {agent}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
