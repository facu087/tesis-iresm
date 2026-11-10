import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { NONCE_HEADER } from "@/lib/csp";
import { resolveSiteUrl } from "@/lib/siteUrl";

/**
 * Fija el tema elegido antes del primer pintado, para que quien eligió oscuro
 * no vea un destello claro. Por defecto el tema es claro, sin mirar el sistema.
 * La clave debe coincidir con `THEME_STORAGE_KEY` de `ThemeToggle`.
 * Lleva el nonce del pedido: sin él, la Content-Security-Policy lo bloquea
 * (ver `src/proxy.ts` y `lib/csp.ts`).
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

export const metadata: Metadata = {
  // Base of every URL based metadata field, sharing image included.
  metadataBase: resolveSiteUrl(),
  title: "NEXUS — Sistema de Soporte Investigativo Clínico",
  description:
    "Pipeline multi-agente para generación de hipótesis clínicas basadas en evidencia. " +
    "NEXUS no emite diagnósticos — genera hipótesis de investigación para el médico responsable.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Leer los encabezados vuelve dinámico el renderizado, que el nonce exige.
  const nonce = (await headers()).get(NONCE_HEADER) ?? undefined;
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
