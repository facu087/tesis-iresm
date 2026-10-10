"use client";

import { useEffect, useRef, useState } from "react";
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
import { analyzeFile, analyzeText } from "@/lib/api";
import { inputStore } from "@/lib/inputStore";
import { reportStore } from "@/lib/reportStore";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";
import type { StructuredReport } from "@/lib/types";
import AuthShell from "@/components/landing/AuthShell";
import DiagnosticNotice from "@/components/landing/DiagnosticNotice";
import { FORM_CARD, FormError } from "@/components/landing/FormPrimitives";
import { SUBMIT_BUTTON } from "@/components/landing/styles";

/**
 * Progress view shown while `POST /api/analyze` runs, in the landing visual
 * system.
 *
 * The steps, their order and their texts come from `PIPELINE_STEPS` (shared
 * with the landing and `/analizar`, not edited here). This file only adds, by
 * step `id`, what the view needs on top: an icon and the pacing of the
 * simulated progress.
 *
 * The backend answers once, with the finished report: it sends no progress
 * events. The steps therefore advance on timers, and the page says so. The
 * last step stays in progress until the request resolves, so the list never
 * reads as complete while the analysis is still running.
 */

/** Icon and simulated duration per step, keyed by the shared step `id`. */
const STEP_DETAILS: Record<string, { Icon: Icon; ms: number }> = {
  "01": { Icon: FileTextIcon, ms: 1500 },
  "02": { Icon: TextAaIcon, ms: 1000 },
  "03": { Icon: ListChecksIcon, ms: 4000 },
  "04": { Icon: UsersThreeIcon, ms: 8000 },
  "05": { Icon: ChatsCircleIcon, ms: 12000 },
  "06": { Icon: ScalesIcon, ms: 9000 },
  "07": { Icon: CompassIcon, ms: 5000 },
  "08": { Icon: ClipboardTextIcon, ms: 1500 },
};

/** Pacing of a shared step this file has no entry for yet. */
const DEFAULT_STEP_MS = 4000;

/** Pause between steps once the report is back and the rest only catch up. */
const CATCH_UP_MS = 350;

const TOTAL_STEPS = PIPELINE_STEPS.length;
const LAST_STEP = TOTAL_STEPS - 1;

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
  const [statuses, setStatuses] = useState<Status[]>(PIPELINE_STEPS.map(() => "pending"));
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const canceledRef = useRef(false);
  const apiDoneRef = useRef(false);
  const animDoneRef = useRef(false);
  const reportRef = useRef<StructuredReport | null>(null);

  /* Elapsed time. */
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      if (!canceledRef.current) setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  /* Simulated progress and the request. */
  useEffect(() => {
    // Reset the refs: StrictMode invokes the effect twice in development.
    canceledRef.current = false;
    apiDoneRef.current = false;
    animDoneRef.current = false;

    const input = inputStore.get();
    if (!input) {
      router.replace("/");
      return;
    }

    const navigate = () => {
      if (canceledRef.current) return;
      reportStore.save(reportRef.current);
      router.push("/report");
    };

    /* The report is back and every step was shown: close the list and leave. */
    const finish = () => {
      if (canceledRef.current) return;
      setStatuses((prev) => prev.map(() => "done"));
      navigate();
    };

    /* Runs through the remaining steps quickly (the request already resolved). */
    const finishFast = (from: number) => {
      if (canceledRef.current) return;
      let delay = 0;
      for (let i = from; i < TOTAL_STEPS; i++) {
        const idx = i;
        delay += CATCH_UP_MS;
        setTimeout(() => {
          if (canceledRef.current) return;
          setStatuses((prev) => prev.map((s, j) => (j <= idx ? "done" : s)));
          if (idx === LAST_STEP) navigate();
        }, delay);
      }
    };

    /* Regular pacing, one step after the other. */
    const runStep = (idx: number) => {
      if (canceledRef.current) return;
      setStatuses((prev) =>
        prev.map((_, j) => (j < idx ? "done" : j === idx ? "active" : "pending")),
      );
      setTimeout(() => {
        if (canceledRef.current) return;

        if (idx === LAST_STEP) {
          animDoneRef.current = true;
          // Without the report yet, the last step stays in progress: the
          // request block below closes the list when it resolves.
          if (apiDoneRef.current) finish();
          return;
        }

        setStatuses((prev) => prev.map((s, j) => (j <= idx ? "done" : s)));
        if (apiDoneRef.current) {
          // The request resolved during this step: catch up with the rest.
          finishFast(idx + 1);
        } else {
          runStep(idx + 1);
        }
      }, STEP_DETAILS[PIPELINE_STEPS[idx].id]?.ms ?? DEFAULT_STEP_MS);
    };

    runStep(0);

    /* The actual request. */
    (async () => {
      try {
        const report =
          input.mode === "file" ? await analyzeFile(input.file) : await analyzeText(input.text);
        if (canceledRef.current) return;
        reportRef.current = report;
        apiDoneRef.current = true;
        inputStore.clear();
        // If the steps are still running, the pacing above notices
        // `apiDoneRef` and catches up; otherwise leave now.
        if (animDoneRef.current) finish();
      } catch (err) {
        if (canceledRef.current) return;
        setError(err instanceof Error ? err.message : "Error inesperado.");
      }
    })();

    return () => {
      canceledRef.current = true;
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

  const activeIdx = statuses.findLastIndex((s) => s === "active");
  const doneCount = statuses.filter((s) => s === "done").length;
  const progress = Math.round((doneCount / TOTAL_STEPS) * 100);
  const statusText =
    doneCount === TOTAL_STEPS
      ? "Completado — redirigiendo…"
      : activeIdx >= 0
        ? `Paso ${activeIdx + 1} de ${TOTAL_STEPS}`
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
            El avance de los pasos es orientativo: esta pantalla no recibe el
            progreso real del servidor. El reporte se abre cuando termina el
            análisis.
          </p>
        </div>

        <ol className="flex flex-col gap-4">
          {PIPELINE_STEPS.map((step, i) => {
            const status = statuses[i];
            const StepIcon = STEP_DETAILS[step.id]?.Icon;
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
                      Procesando…
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
