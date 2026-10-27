"use client";

import { useCallback, useId, useRef, useState } from "react";
import { CheckCircleIcon, FilePdfIcon } from "@phosphor-icons/react/ssr";
import type { AnalysisInput } from "@/lib/inputStore";
import { FormError } from "@/components/landing/FormPrimitives";
import { EASE, FOCUS_RING, PRIMARY_BUTTON, TRANSITION } from "@/components/landing/styles";

/**
 * Upload form of `/analizar`, in the landing visual system (it relies on the
 * `.landing` scope of the page). Two input modes: a PDF or pasted text.
 */

interface Props {
  onReady: (input: AnalysisInput) => void;
}

type InputMode = "file" | "text";

/** Submit button: the disabled state reads as unavailable, not as pending. */
const SUBMIT = `${PRIMARY_BUTTON} w-full cursor-pointer border border-transparent disabled:pointer-events-none disabled:border-border disabled:bg-bg-subtle disabled:text-fg-muted`;

const DROPZONE_STATE = {
  dragging: "border-accent bg-bg-subtle",
  filled: "border-accent bg-bg",
  invalid: "border-red-700 bg-bg hover:bg-bg-subtle dark:border-red-400",
  empty: "border-fg-muted bg-bg hover:border-accent hover:bg-bg-subtle",
} as const;

export default function UploadForm({ onReady }: Props) {
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const baseId = useId();
  const tabId = (m: InputMode) => `${baseId}-tab-${m}`;
  const errorId = `${baseId}-error`;

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      setFile(dropped);
      setMode("file");
      setError(null);
    } else {
      setError("Solo se aceptan archivos PDF.");
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setError(null);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "file") {
      if (!file) { setError("Seleccioná un archivo PDF."); return; }
      onReady({ mode: "file", file });
    } else {
      if (!text.trim()) { setError("Ingresá el texto del caso clínico."); return; }
      onReady({ mode: "text", text });
    }
  };

  const canSubmit =
    (mode === "file" && file !== null) ||
    (mode === "text" && text.trim().length > 0);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      {/* Mode selector */}
      <div className="flex gap-1 rounded-xl border border-border bg-bg-subtle p-1">
        {(["file", "text"] as InputMode[]).map((m) => (
          <button
            key={m}
            id={tabId(m)}
            type="button"
            aria-pressed={mode === m}
            onClick={() => { setMode(m); setError(null); }}
            className={`flex-1 cursor-pointer rounded-lg border px-3 py-2 text-sm font-semibold ${TRANSITION} active:scale-[0.98] ${FOCUS_RING} ${
              mode === m
                ? "border-border bg-surface text-fg"
                : "border-transparent text-fg-muted hover:text-accent"
            }`}
          >
            {m === "file" ? "Subir PDF" : "Ingresar texto"}
          </button>
        ))}
      </div>

      {/* File zone */}
      {mode === "file" && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center select-none transition-colors duration-700 ${EASE} has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-accent ${
            DROPZONE_STATE[isDragging ? "dragging" : file ? "filled" : error ? "invalid" : "empty"]
          }`}
        >
          {/* Visually hidden, not `display: none`, so the keyboard reaches it.
              Its own click must not bubble into the zone, which would open
              the picker a second time. */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            onClick={(e) => e.stopPropagation()}
            aria-labelledby={tabId("file")}
            aria-describedby={error ? errorId : undefined}
            className="sr-only"
          />
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <CheckCircleIcon aria-hidden="true" weight="bold" className="size-8 text-accent" />
              <p className="max-w-full text-base font-semibold wrap-anywhere text-fg">{file.name}</p>
              <p className="font-mono text-sm text-fg-muted">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className={`cursor-pointer rounded-sm text-sm font-semibold text-accent underline underline-offset-4 ${TRANSITION} hover:opacity-80 active:translate-y-px ${FOCUS_RING}`}
              >
                Cambiar archivo
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-fg-muted">
              <FilePdfIcon aria-hidden="true" className="size-10" />
              <p className="text-base font-semibold text-fg">Arrastrá un PDF aquí</p>
              <p className="text-sm">o hacé clic para seleccionar</p>
            </div>
          )}
        </div>
      )}

      {/* Pasted text */}
      {mode === "text" && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Pegá el texto del caso clínico aquí..."
          rows={10}
          aria-labelledby={tabId("text")}
          aria-describedby={error ? errorId : undefined}
          className={`w-full resize-none rounded-xl border border-fg-muted bg-bg px-4 py-3 text-base text-fg placeholder:text-fg-muted transition-colors duration-700 ${EASE} hover:border-accent focus-visible:border-accent ${FOCUS_RING}`}
        />
      )}

      {error && <FormError id={errorId}>{error}</FormError>}

      <button type="submit" disabled={!canSubmit} className={SUBMIT}>
        Analizar caso clínico →
      </button>
    </form>
  );
}
