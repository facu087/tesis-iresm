import type { Metadata } from "next";

/**
 * `/report` is a client page (it reads the stored report and keeps the tab
 * state) and a Client Component cannot export `metadata`, so this sibling
 * Server Component layout exposes it instead, as `/analizar` does.
 */
export const metadata: Metadata = {
  title: "Reporte de análisis — NEXUS",
  description: "Reporte del análisis de un caso clínico en NEXUS.",
};

export default function ReportLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
