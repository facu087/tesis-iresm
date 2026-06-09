/**
 * Almacén en memoria para pasar el input del usuario entre páginas.
 * Funciona dentro de la misma pestaña sin serialización.
 */

export type AnalysisInput =
  | { mode: "text"; text: string }
  | { mode: "file"; file: File };

let _input: AnalysisInput | null = null;

export const inputStore = {
  set(input: AnalysisInput) {
    _input = input;
  },
  get(): AnalysisInput | null {
    return _input;
  },
  clear() {
    _input = null;
  },
};
