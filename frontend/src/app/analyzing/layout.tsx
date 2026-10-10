import type { Metadata } from "next";

/**
 * `/analyzing` is a client page (timers, the request, UI state) and a Client
 * Component cannot export `metadata`, so this sibling Server Component layout
 * exposes it instead, as `/analizar` does.
 */
export const metadata: Metadata = {
  title: "Analizando caso clínico — NEXUS",
  description: "Vista de progreso del análisis de un caso clínico en NEXUS.",
};

export default function AnalyzingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
