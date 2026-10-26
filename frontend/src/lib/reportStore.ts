"use client";

import type { StructuredReport } from "@/lib/types";

/**
 * Almacén del reporte generado, persistido en `sessionStorage`.
 *
 * La página de análisis lo guarda al terminar el pipeline y la página de
 * reporte lo lee al montarse. Se usa `sessionStorage` (y no el almacén en
 * memoria de `inputStore`) para que el reporte sobreviva a un refresco de la
 * pestaña, pero no a cerrarla: es información clínica y no corresponde que
 * quede en el equipo más allá de la sesión.
 *
 * La lectura se expone con la interfaz de `useSyncExternalStore` en vez de un
 * `useEffect` que haga `setState`: ese patrón provoca un render en cascada
 * (primero sin reporte, después con él) y es lo que marcaba la regla
 * `react-hooks/set-state-in-effect`. Acá el reporte ya está disponible en el
 * primer render del cliente.
 *
 * `getSnapshot` tiene que devolver siempre la misma referencia mientras el
 * contenido no cambie, porque React la compara por identidad en cada render:
 * si se parseara el JSON en cada llamada se generaría un objeto nuevo cada vez
 * y el componente entraría en un bucle de renders. Por eso se cachea el texto
 * crudo junto con el objeto ya parseado.
 */

const STORAGE_KEY = "nexus_report";
const REPORT_EVENT = "nexus-report-change";

let cachedRaw: string | null = null;
let cachedReport: StructuredReport | null = null;

function readRaw(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    // Almacenamiento no disponible (modo privado, datos bloqueados).
    return null;
  }
}

function subscribe(onChange: () => void): () => void {
  // `storage` solo avisa de cambios hechos en otras pestañas; el evento propio
  // cubre los de esta misma.
  window.addEventListener(REPORT_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(REPORT_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function getSnapshot(): StructuredReport | null {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    try {
      cachedReport = raw === null ? null : (JSON.parse(raw) as StructuredReport);
    } catch {
      // Contenido corrupto: se trata como si no hubiera reporte.
      cachedReport = null;
    }
  }
  return cachedReport;
}

/**
 * En el servidor y durante la hidratación no hay `sessionStorage`, así que el
 * reporte vale null y la página no pinta nada. React vuelve a renderizar con
 * la instantánea real del cliente apenas termina de hidratar.
 */
function getServerSnapshot(): StructuredReport | null {
  return null;
}

function save(report: StructuredReport | null): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(report));
  } catch {
    // Sin almacenamiento disponible no se puede pasar el reporte a la otra
    // página; esta la redirige al inicio al no encontrarlo.
  }
  window.dispatchEvent(new Event(REPORT_EVENT));
}

export const reportStore = {
  subscribe,
  getSnapshot,
  getServerSnapshot,
  save,
};
