/**
 * Pasos del pipeline de análisis de NEXUS.
 *
 * Fuente única de verdad para la landing (`/`, sección "Cómo funciona") y para
 * la lista compacta que se muestra en `/analizar`. Refleja el flujo real
 * descrito en `.claude/architecture.md`, no una versión simplificada aparte:
 * evita que ambas vistas describan el pipeline de forma distinta con el
 * tiempo (design D4 de `openspec/changes/archive/2026-10-04-landing-explicativa/design.md`).
 *
 * No confundir con los `STEPS` de `app/analyzing/page.tsx`: esa vista anima
 * el progreso mientras la API corre y necesita una granularidad de tiempos
 * (`minMs`) propia; esta lista es la explicación estática del flujo.
 */

export interface PipelineStep {
  /** Orden dentro del pipeline, como string de dos dígitos ("01", "02", …). */
  id: string;
  /** Título corto del paso. */
  label: string;
  /** Descripción de una línea, sin tecnicismos de implementación. */
  description: string;
}

export const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "01",
    label: "Ingesta",
    description: "Extracción de texto desde PDF nativo o escaneado (OCR).",
  },
  {
    id: "02",
    label: "Normalización",
    description: "Nombres de fármacos (INN) y unidades de medida.",
  },
  {
    id: "03",
    label: "Síntesis PICO",
    description: "Construcción del contexto clínico estructurado del caso.",
  },
  {
    id: "04",
    label: "Ronda 1 — Análisis paralelo",
    description:
      "Los agentes 01 (Literatura), 02 (Genómica) y 03 (Clínico) generan hipótesis en simultáneo, sin verse entre sí.",
  },
  {
    id: "05",
    label: "Debate — Rondas 2 a 4",
    description:
      "Cada agente recibe las hipótesis de los demás, las critica y revisa las propias.",
  },
  {
    id: "06",
    label: "Verificación y arbitraje",
    description:
      "El Agente 04 contrasta cada referencia citada contra PubMed, agrupa el consenso y pide una recitación (Ronda 5) a las hipótesis que quedaron sin respaldo.",
  },
  {
    id: "07",
    label: "Navegación de ensayos",
    description:
      "El Agente 05 busca ensayos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet.",
  },
  {
    id: "08",
    label: "Reporte",
    description:
      "Hipótesis priorizadas por nivel de evidencia (I, II, III), con sus fuentes y ensayos compatibles.",
  },
];

/** Resumen en una oración, para el `aria-label` del diagrama del pipeline. */
export const PIPELINE_SUMMARY =
  "Flujo del pipeline: " +
  PIPELINE_STEPS.map((s) => s.label).join(" → ") +
  ".";
