"use client";

import { useSyncExternalStore } from "react";
import { MoonIcon, SunIcon } from "@/components/icons";

/**
 * Selector de tema claro/oscuro para la barra de navegación.
 *
 * La fuente de verdad es el atributo `data-theme` de `<html>`: lo fija el
 * script en línea del `layout` antes del primer pintado (para no parpadear)
 * y este componente lo alterna. La elección se guarda en `localStorage` con
 * una clave propia; si el almacenamiento falla (modo privado, datos
 * bloqueados) el cambio sigue funcionando en la sesión, sin recordarse.
 *
 * Se lee con `useSyncExternalStore`: en el servidor y durante la hidratación
 * el tema es "light", y recién después se sincroniza con el atributo real,
 * sin desajustes de hidratación.
 */

export const THEME_STORAGE_KEY = "nexus-theme";
const THEME_EVENT = "nexus-theme-change";

type Theme = "light" | "dark";

function subscribe(onChange: () => void): () => void {
  window.addEventListener(THEME_EVENT, onChange);
  return () => window.removeEventListener(THEME_EVENT, onChange);
}

function getSnapshot(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function getServerSnapshot(): Theme {
  return "light";
}

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const next: Theme = theme === "dark" ? "light" : "dark";

  const handleClick = () => {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Sin almacenamiento disponible: el tema vale solo para esta sesión.
    }
    window.dispatchEvent(new Event(THEME_EVENT));
  };

  const Icon = next === "dark" ? MoonIcon : SunIcon;

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={`Cambiar a tema ${next === "dark" ? "oscuro" : "claro"}`}
      className={`inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-1.5 rounded-full px-3 text-sm text-fg-muted transition-colors duration-200 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span suppressHydrationWarning>{next === "dark" ? "Oscuro" : "Claro"}</span>
    </button>
  );
}
