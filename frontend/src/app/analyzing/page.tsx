"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { analyzeFile, analyzeText } from "@/lib/api";
import { inputStore } from "@/lib/inputStore";
import type { StructuredReport } from "@/lib/types";

const STEPS = [
  { icon: "📄", label: "Ingesta y extracción de texto",    sub: "PDF nativo · OCR Tesseract",        minMs: 1500  },
  { icon: "🔤", label: "Normalización terminológica",      sub: "Nombres INN · unidades de medida",  minMs: 1000  },
  { icon: "🧠", label: "Síntesis PICO",                    sub: "Construcción del contexto clínico", minMs: 4000  },
  { icon: "🔬", label: "Análisis paralelo — Ronda 1",      sub: "Agentes 01, 02 y 03 en simultáneo",     minMs: 8000  },
  { icon: "⚖️", label: "Debate adversarial — Rondas 2–4", sub: "Crítica cruzada y revisión",        minMs: 12000 },
  { icon: "🔎", label: "Verificación bibliográfica",       sub: "Los PMID citados se contrastan contra PubMed",  minMs: 5000  },
  { icon: "🧑‍⚖️", label: "Arbitraje — Ronda 5",             sub: "Agente 04: consenso, contradicciones y recitación", minMs: 9000  },
  { icon: "📋", label: "Generación del reporte",           sub: "Agente 05: ensayos y compatibilidad · bibliografía", minMs: 1500 },
];

type Status = "pending" | "active" | "done";

export default function AnalyzingPage() {
  const router = useRouter();
  const [statuses, setStatuses] = useState<Status[]>(STEPS.map(() => "pending"));
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const canceledRef  = useRef(false);
  const apiDoneRef   = useRef(false);
  const animDoneRef  = useRef(false);
  const reportRef    = useRef<StructuredReport | null>(null);

  /* ── Timer ─────────────────────────────────────────────────────────── */
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      if (!canceledRef.current) setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  /* ── Animación + llamada a la API ──────────────────────────────────── */
  useEffect(() => {
    // Resetear refs para el double-invoke de StrictMode en desarrollo
    canceledRef.current = false;
    apiDoneRef.current = false;
    animDoneRef.current = false;

    const input = inputStore.get();
    if (!input) { router.replace("/"); return; }

    const navigate = () => {
      if (canceledRef.current) return;
      sessionStorage.setItem("nexus_report", JSON.stringify(reportRef.current));
      router.push("/report");
    };

    /* Avanza los pasos restantes rápido (cuando la API ya terminó) */
    const finishFast = (from: number) => {
      if (canceledRef.current) return;
      let delay = 0;
      for (let i = from; i < STEPS.length; i++) {
        const idx = i;
        delay += 350;
        setTimeout(() => {
          if (canceledRef.current) return;
          setStatuses((prev) =>
            prev.map((s, j) => (j <= idx ? "done" : s))
          );
          if (idx === STEPS.length - 1) navigate();
        }, delay);
      }
    };

    /* Animación secuencial normal */
    const runStep = (idx: number) => {
      if (canceledRef.current) return;
      setStatuses((prev) =>
        prev.map((_, j) => (j < idx ? "done" : j === idx ? "active" : "pending"))
      );
      setTimeout(() => {
        if (canceledRef.current) return;
        setStatuses((prev) => prev.map((s, j) => (j <= idx ? "done" : s)));

        if (idx === STEPS.length - 1) {
          animDoneRef.current = true;
          if (apiDoneRef.current) navigate();
          /* Si la API aún no terminó, el último paso queda "done" y
             navigate() se llama desde el bloque de la API (abajo). */
        } else if (apiDoneRef.current) {
          /* API ya terminó mientras animábamos — saltamos los pasos restantes */
          finishFast(idx + 1);
        } else {
          runStep(idx + 1);
        }
      }, STEPS[idx].minMs);
    };

    runStep(0);

    /* Llamada real a la API */
    (async () => {
      try {
        const report =
          input.mode === "file"
            ? await analyzeFile(input.file)
            : await analyzeText(input.text);
        if (canceledRef.current) return;
        reportRef.current = report;
        apiDoneRef.current = true;
        inputStore.clear();
        if (animDoneRef.current) navigate();
        /* Si la animación ya terminó → navegar; si no, la animación
           detectará apiDoneRef y acelerará los pasos restantes. */
      } catch (err) {
        if (canceledRef.current) return;
        setError(err instanceof Error ? err.message : "Error inesperado.");
      }
    })();

    return () => { canceledRef.current = true; };
  }, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Error ──────────────────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="min-h-screen flex flex-col">
        <NexusHeader />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-8 text-center space-y-4">
            <p className="text-4xl">⚠️</p>
            <p className="text-lg font-semibold text-slate-800">
              Error en el análisis
            </p>
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-2">
              {error}
            </p>
            <button
              onClick={() => router.push("/")}
              className="rounded-xl bg-slate-900 px-6 py-2 text-sm font-semibold text-white hover:bg-slate-700"
            >
              Volver al inicio
            </button>
          </div>
        </main>
      </div>
    );
  }

  const activeIdx = statuses.findLastIndex((s) => s === "active");
  const doneCount = statuses.filter((s) => s === "done").length;
  const progress  = Math.round((doneCount / STEPS.length) * 100);

  return (
    <div className="min-h-screen flex flex-col">
      <NexusHeader />

      <main className="flex-1 bg-slate-50 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-xl space-y-6">

          {/* Título + progreso */}
          <div className="text-center space-y-1">
            <p className="text-2xl font-bold text-slate-800">
              Analizando caso clínico
            </p>
            <p className="text-sm text-slate-400">
              El pipeline multi-agente está procesando el documento…
            </p>
          </div>

          {/* Barra de progreso */}
          <div className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-slate-900 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Pasos */}
          <div className="rounded-2xl border border-slate-200 bg-white divide-y divide-slate-100">
            {STEPS.map((step, i) => {
              const status = statuses[i];
              return (
                <div
                  key={step.label}
                  className={`flex items-center gap-4 px-6 py-4 transition-colors ${
                    status === "active" ? "bg-slate-50" : ""
                  }`}
                >
                  {/* Indicador de estado */}
                  <div className="shrink-0 w-8 h-8 flex items-center justify-center">
                    {status === "done" && (
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500 text-white text-sm font-bold">
                        ✓
                      </span>
                    )}
                    {status === "active" && (
                      <span className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-900 border-t-transparent animate-spin" />
                    )}
                    {status === "pending" && (
                      <span className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-200 text-xs font-medium text-slate-400">
                        {i + 1}
                      </span>
                    )}
                  </div>

                  {/* Texto */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${
                      status === "pending" ? "text-slate-400" : "text-slate-800"
                    }`}>
                      {step.label}
                    </p>
                    <p className={`text-xs truncate ${
                      status === "active"
                        ? "text-blue-500"
                        : "text-slate-400"
                    }`}>
                      {status === "active" ? "Procesando…" : step.sub}
                    </p>
                  </div>

                  {/* Emoji del paso */}
                  <span className={`text-lg transition-opacity ${
                    status === "pending" ? "opacity-30" : "opacity-100"
                  }`}>
                    {step.icon}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Footer de estado */}
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span>
              {doneCount === STEPS.length
                ? "Completado — redirigiendo…"
                : activeIdx >= 0
                ? `Paso ${activeIdx + 1} de ${STEPS.length}`
                : "Iniciando…"}
            </span>
            <span>{elapsed}s transcurridos</span>
          </div>

        </div>
      </main>
    </div>
  );
}

function NexusHeader() {
  return (
    <header className="bg-slate-900 text-white px-6 py-4 flex items-center gap-3">
      <span className="text-xl font-bold">NEXUS</span>
      <span className="text-slate-500 text-sm">·</span>
      <span className="text-slate-400 text-sm">Sistema de Soporte Investigativo Clínico</span>
    </header>
  );
}
