import type { Metadata } from "next";
import { Atkinson_Hyperlegible } from "next/font/google";

/**
 * Layout de la variante /v2: carga Atkinson Hyperlegible solo para esta ruta
 * y fija el contenedor `data-variant="v2"`, que sobrescribe los tokens de
 * color en `globals.css`. El resto del sitio no cambia.
 */
const atkinson = Atkinson_Hyperlegible({
  variable: "--font-atkinson",
  weight: ["400", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NEXUS — Variante de la landing (v2)",
  robots: { index: false },
};

export default function V2Layout({ children }: { children: React.ReactNode }) {
  return (
    <div data-variant="v2" className={`${atkinson.variable} bg-bg text-fg`}>
      {children}
    </div>
  );
}
