"use client";

import { useCallback, useRef, useState } from "react";
import type { AnalysisInput } from "@/lib/inputStore";

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

      {/* Zona de archivo */}
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
              ? "border-emerald-400 bg-emerald-50"
              : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
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
              <p className="font-medium text-emerald-700">{file.name}</p>
              <p className="text-sm text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="mt-2 text-xs text-slate-400 underline hover:text-slate-600"
              >
                Cambiar archivo
              </button>
            </div>
          ) : (
            <div className="space-y-2 text-slate-400">
              <p className="text-4xl">📄</p>
              <p className="font-medium text-slate-600">Arrastrá un PDF aquí</p>
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
          className="w-full resize-none rounded-xl border border-slate-200 px-4 py-3 text-sm leading-relaxed placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300"
        />
      )}

      {/* Error */}
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-xl bg-slate-900 py-3 font-semibold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
      >
        Analizar caso clínico →
      </button>
    </form>
  );
}
