"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChatsCircleIcon,
  CheckIcon,
  CircleNotchIcon,
  ClipboardTextIcon,
  CompassIcon,
  DotsThreeIcon,
  FileTextIcon,
  HourglassIcon,
  ListChecksIcon,
  ScalesIcon,
  TextAaIcon,
  UsersThreeIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react/ssr";
import type { Icon } from "@phosphor-icons/react";
import { analyzeWithProgress } from "@/lib/api";
import { inputStore } from "@/lib/inputStore";
import { reportStore } from "@/lib/reportStore";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";
import AuthShell from "@/components/landing/AuthShell";
import DiagnosticNotice from "@/components/landing/DiagnosticNotice";
import { FORM_CARD, FormError } from "@/components/landing/FormPrimitives";
import { SUBMIT_BUTTON } from "@/components/landing/styles";

/**
 * Progress view shown while the analysis runs, in the landing visual system.
 *
 * The steps, their order and their texts come from `PIPELINE_STEPS` (shared
 * with the landing and `/analizar`, not edited here). This file only adds, by
 * step `id`, the icon of each one.
 *
 * The progress is the server's: `POST /api/analyze/stream` reports each step
 * and each debate round as it starts, and sends the report at the end. Nothing
 * here advances on a timer, so a step is never shown as started before it is.
 */

/** Icon per step, keyed by the shared step `id`. */
const STEP_ICONS: Record<string, Icon> = {
  "01": FileTextIcon,
  "02": TextAaIcon,
  "03": ListChecksIcon,
  "04": UsersThreeIcon,
  "05": ChatsCircleIcon,
  "06": ScalesIcon,
  "07": CompassIcon,
  "08": ClipboardTextIcon,
};

const TOTAL_STEPS = PIPELINE_STEPS.length;

/** The step whose rounds the server reports, and the last round of the debate. */
const DEBATE_STEP_ID = "05";
const LAST_DEBATE_ROUND = 4;

const ERROR_ID = "analisis-error";

type Status = "pending" | "active" | "done";

/** State of a step for assistive technology: the badge itself is decorative. */
const STATUS_LABEL: Record<Status, string> = {
  pending: "Pendiente",
  active: "En curso",
  done: "Completado",
};

const STEP_BADGE = "inline-flex size-8 shrink-0 items-center justify-center rounded-full border";

/** Round marker of a step: its number, a spinner or a check. */
function StepBadge({ id, status }: { id: string; status: Status }) {
  if (status === "done") {
    return (
      <span aria-hidden="true" className={`${STEP_BADGE} border-accent bg-accent text-accent-fg`}>
        <CheckIcon weight="bold" className="size-4" />
      </span>
    );
  }
  if (status === "active") {
    return (
      <span aria-hidden="true" className={`${STEP_BADGE} border-accent text-accent`}>
        {/* Under reduced motion the spinner gives way to a still icon. */}
        <CircleNotchIcon weight="bold" className="size-4 animate-spin motion-reduce:hidden" />
        <DotsThreeIcon weight="bold" className="size-4 motion-safe:hidden" />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${STEP_BADGE} border-border bg-bg-subtle font-mono text-xs font-semibold text-fg-muted`}
    >
      {id}
    </span>
  );
}

export default function AnalyzingPage() {
  const router = useRouter();
  /** Index of the step in progress; -1 until the server reports the first. */
  const [activeIdx, setActiveIdx] = useState(-1);
  /** Debate round in progress, while the debate step is the active one. */
  const [round, setRound] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  /* Elapsed time. */
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  /* The request, and the progress it reports. */
  useEffect(() => {
    // StrictMode invokes the effect twice in development: a run that was
    // cleaned up must not touch the state or navigate.
    let canceled = false;

    const input = inputStore.get();
    if (!input) {
      // No case to analyze: send the user to the upload view, not the landing.
      router.replace("/analizar");
      return;
    }

    (async () => {
      try {
        const report = await analyzeWithProgress(input, (event) => {
          if (canceled) return;
          if (event.evento === "paso") {
            const idx = PIPELINE_STEPS.findIndex((step) => step.id === event.paso);
            // An unknown step is ignored and the list never moves backwards.
            if (idx < 0) return;
            setActiveIdx((prev) => Math.max(prev, idx));
            setRound(null);
          } else {
            setRound(event.ronda);
          }
        });
        if (canceled) return;
        inputStore.clear();
        setFinished(true);
        reportStore.save(report);
        router.push("/report");
      } catch (err) {
        if (canceled) return;
        // fetch() rejects with a TypeError when the server cannot be reached;
        // its message ("Failed to fetch") is browser jargon, so replace it.
        setError(
          err instanceof TypeError
            ? "No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo."
            : err instanceof Error
              ? err.message
              : "Error inesperado.",
        );
      }
    })();

    return () => {
      canceled = true;
    };
  }, [router]);

  if (error) {
    return (
      <AuthShell
        icon={<WarningCircleIcon aria-hidden="true" weight="bold" className="size-6" />}
        title="Error en el análisis"
        footer={<DiagnosticNotice />}
      >
        <div className={FORM_CARD}>
          <FormError id={ERROR_ID}>{error}</FormError>
          <button
            type="button"
            onClick={() => router.push("/analizar")}
            aria-describedby={ERROR_ID}
            className={SUBMIT_BUTTON}
          >
            Volver a cargar el caso
          </button>
        </div>
      </AuthShell>
    );
  }

  const statuses: Status[] = PIPELINE_STEPS.map((_, i) =>
    finished || i < activeIdx ? "done" : i === activeIdx ? "active" : "pending",
  );
  const doneCount = statuses.filter((status) => status === "done").length;
  const progress = Math.round((doneCount / TOTAL_STEPS) * 100);
  const roundText =
    round !== null && PIPELINE_STEPS[activeIdx]?.id === DEBATE_STEP_ID
      ? `Ronda ${round} de ${LAST_DEBATE_ROUND}`
      : null;
  const statusText = finished
    ? "Completado — redirigiendo…"
    : activeIdx >= 0
      ? `Paso ${activeIdx + 1} de ${TOTAL_STEPS}${roundText ? ` — ${roundText}` : ""}`
      : "Iniciando…";

  return (
    <AuthShell
      icon={<HourglassIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Analizando caso clínico"
      lead="El pipeline multi-agente está procesando el documento…"
      footer={<DiagnosticNotice />}
    >
      <div className={FORM_CARD}>
        <div>
          {/* The seconds tick outside the live region: only a change of step
              is announced. */}
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
            <p role="status" className="font-semibold text-fg">
              {statusText}
            </p>
            <p className="text-fg-muted">
              <span className="font-mono tabular-nums">{elapsed}</span> s transcurridos
            </p>
          </div>
          <div
            role="progressbar"
            aria-label="Avance del análisis"
            aria-valuemin={0}
            aria-valuemax={TOTAL_STEPS}
            aria-valuenow={doneCount}
            aria-valuetext={statusText}
            className="mt-3 h-2 w-full overflow-hidden rounded-full bg-border"
          >
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-3 text-xs text-pretty text-fg-muted">
            El servidor informa cada paso cuando empieza. El reporte se abre
            cuando termina el análisis.
          </p>
        </div>

        <ol className="flex flex-col gap-4">
          {PIPELINE_STEPS.map((step, i) => {
            const status = statuses[i];
            const StepIcon = STEP_ICONS[step.id];
            return (
              <li
                key={step.id}
                aria-current={status === "active" ? "step" : undefined}
                className="flex items-start gap-3"
              >
                <StepBadge id={step.id} status={status} />
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-semibold ${status === "pending" ? "text-fg-muted" : "text-fg"}`}
                  >
                    {step.label}
                    <span className="sr-only"> ({STATUS_LABEL[status]})</span>
                  </p>
                  <p className="text-sm text-pretty text-fg-muted">{step.description}</p>
                  {status === "active" && (
                    <p aria-hidden="true" className="mt-1 text-sm font-semibold text-accent">
                      {roundText ?? "Procesando…"}
                    </p>
                  )}
                </div>
                {StepIcon && (
                  <StepIcon
                    aria-hidden="true"
                    className={`mt-1 size-5 shrink-0 ${status === "pending" ? "text-fg-muted opacity-50" : "text-accent"}`}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </AuthShell>
  );
}
