"use client";

import { useCallback, useRef, useState } from "react";
import type { AnalysisInput } from "@/lib/inputStore";
import { CheckIcon, DocumentIcon } from "@/components/icons";

interface Props {
  onReady: (input: AnalysisInput) => void;
}

type InputMode = "file" | "text";

export default function UploadForm({ onReady }: Props) {
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Tabs */}
      <div className="flex rounded-lg border border-border bg-bg-subtle p-1">
        {(["file", "text"] as InputMode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => { setMode(m); setError(null); }}
            className={`flex-1 cursor-pointer rounded-md py-2 text-sm font-medium transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              mode === m
                ? "bg-bg text-fg shadow-sm ring-1 ring-border"
                : "text-fg-muted hover:text-accent"
            }`}
          >
            {m === "file" ? "Subir PDF" : "Ingresar texto"}
          </button>
        ))}
      </div>

      {/* Zona de archivo */}
      {mode === "file" && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer select-none rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            isDragging
              ? "border-accent bg-bg-subtle"
              : file
              ? "border-accent bg-bg"
              : "border-border hover:border-accent-muted hover:bg-bg-subtle"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          {file ? (
            <div className="space-y-1">
              <CheckIcon className="mx-auto h-8 w-8 text-fg" />
              <p className="font-medium text-fg">{file.name}</p>
              <p className="text-sm text-fg-muted">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="mt-2 cursor-pointer text-xs text-fg-muted underline hover:text-accent"
              >
                Cambiar archivo
              </button>
            </div>
          ) : (
            <div className="space-y-2 text-fg-muted">
              <DocumentIcon className="mx-auto h-10 w-10" />
              <p className="font-medium text-fg">Arrastrá un PDF aquí</p>
              <p className="text-sm">o hacé clic para seleccionar</p>
            </div>
          )}
        </div>
      )}

      {/* Textarea */}
      {mode === "text" && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Pegá el texto del caso clínico aquí..."
          rows={10}
          className="w-full resize-none rounded-xl border border-fg-muted bg-bg px-4 py-3 text-sm leading-relaxed text-fg placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-accent"
        />
      )}

      {/* Error */}
      {error && (
        <p className="rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-2 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full cursor-pointer rounded-xl bg-accent py-3 font-semibold text-accent-fg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:cursor-not-allowed disabled:bg-bg-subtle disabled:text-fg-muted disabled:ring-1 disabled:ring-border disabled:hover:opacity-100"
      >
        Analizar caso clínico →
      </button>
    </form>
  );
}
