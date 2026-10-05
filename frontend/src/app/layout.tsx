import type { Metadata } from "next";
import { Atkinson_Hyperlegible, Geist, Geist_Mono, Newsreader } from "next/font/google";
import "./globals.css";
import ThemeScope from "@/components/ThemeScope";

/**
 * Fija el tema elegido antes del primer pintado, para que quien eligió oscuro
 * no vea un destello claro. Por defecto el tema es claro, sin mirar el sistema.
 * La clave debe coincidir con `THEME_STORAGE_KEY` de `ThemeToggle`.
 */
const THEME_INIT_SCRIPT =
  "try{if(localStorage.getItem('nexus-theme')==='dark')document.documentElement.dataset.theme='dark'}catch(e){}";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const atkinson = Atkinson_Hyperlegible({
  variable: "--font-atkinson",
  weight: ["400", "700"],
  subsets: ["latin"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NEXUS — Sistema de Soporte Investigativo Clínico",
  description:
    "Pipeline multi-agente para generación de hipótesis clínicas basadas en evidencia. " +
    "NEXUS no emite diagnósticos — genera hipótesis de investigación para el médico responsable.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${newsreader.variable} ${atkinson.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col bg-gray-50 text-gray-900">
        <ThemeScope />
        {children}
      </body>
    </html>
  );
}
