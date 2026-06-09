"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { StructuredReport } from "@/lib/types";

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<StructuredReport | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem("nexus_report");
    if (!stored) {
      router.replace("/");
      return;
    }
    setReport(JSON.parse(stored) as StructuredReport);
  }, [router]);

  if (!report) return null;

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl text-center space-y-4">
        <p className="text-2xl font-bold text-blue-900">✓ Análisis completado</p>
        <p className="text-gray-500">
          Se generaron{" "}
          <span className="font-semibold text-gray-700">
            {report.hypotheses.length} hipótesis
          </span>{" "}
          en{" "}
          <span className="font-semibold text-gray-700">
            {report.metadata.processing_time_seconds.toFixed(1)} s
          </span>
          .
        </p>
        <p className="text-sm text-gray-400">
          Vista completa del reporte — en construcción (próxima tarea).
        </p>
        <button
          onClick={() => router.push("/")}
          className="mt-4 rounded-xl border border-gray-200 px-6 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          Analizar otro caso
        </button>
      </div>
    </main>
  );
}
