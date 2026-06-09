"use client";

import { useCallback, useRef, useState } from "react";
import { analyzeFile, analyzeText } from "@/lib/api";
import type { StructuredReport } from "@/lib/types";

type InputMode = "file" | "text";

interface Props {
  onSuccess: (report: StructuredReport) => void;
}

export default function UploadForm({ onSuccess }: Props) {
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === "file" && !file) {
      setError("Seleccioná un archivo PDF.");
      return;
    }
    if (mode === "text" && !text.trim()) {
      setError("Ingresá el texto del caso clínico.");
      return;
    }

    setIsLoading(true);
    try {
      const report =
        mode === "file" && file
          ? await analyzeFile(file)
          : await analyzeText(text);
      onSuccess(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado.");
    } finally {
      setIsLoading(false);
    }
  };

  const canSubmit =
    !isLoading &&
    ((mode === "file" && file !== null) ||
      (mode === "text" && text.trim().length > 0));

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Tabs de modo */}
      <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
        {(["file", "text"] as InputMode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => { setMode(m); setError(null); }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              mode === m
                ? "bg-white shadow text-slate-900"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {m === "file" ? "Subir PDF" : "Ingresar texto"}
          </button>
        ))}
      </div>

      {/* Área de archivo */}
      {mode === "file" && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer select-none rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            isDragging
              ? "border-blue-400 bg-blue-50"
              : file
              ? "border-green-400 bg-green-50"
              : "border-gray-300 hover:border-blue-300 hover:bg-gray-50"
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
              <p className="text-2xl">✓</p>
              <p className="font-medium text-green-700">{file.name}</p>
              <p className="text-sm text-gray-400">
                {(file.size / 1024).toFixed(1)} KB
              </p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="mt-2 text-xs text-gray-400 underline hover:text-gray-600"
              >
                Cambiar archivo
              </button>
            </div>
          ) : (
            <div className="space-y-2 text-gray-500">
              <p className="text-4xl">📄</p>
              <p className="font-medium">Arrastrá un PDF aquí</p>
              <p className="text-sm text-gray-400">
                o hacé clic para seleccionar
              </p>
            </div>
          )}
        </div>
      )}

      {/* Textarea de texto */}
      {mode === "text" && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Pegá el texto del caso clínico aquí..."
          rows={10}
          className="w-full resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm leading-relaxed placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
      )}

      {/* Error */}
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Botón de envío */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-xl bg-slate-900 py-3 font-semibold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            Analizando caso clínico…
          </span>
        ) : (
          "Analizar caso clínico"
        )}
      </button>
    </form>
  );
}
