import type { Metadata } from "next";

/**
 * `/analizar` es una página cliente (formulario de carga, estado de UI); un
 * Client Component no puede exportar `metadata`, así que este layout —
 * Server Component hermano— la expone en su lugar (design D3).
 */
export const metadata: Metadata = {
  title: "Analizar caso clínico — NEXUS",
  description:
    "Cargá un caso clínico en PDF o texto para iniciar el análisis del " +
    "pipeline multi-agente de NEXUS.",
};

export default function AnalizarLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
