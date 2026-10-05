"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

/** Rutas con colores fijos (sin tokens ni selector): siempre en claro. */
const FIXED_LIGHT_ROUTES = ["/report", "/analyzing"];

/**
 * Marca en `<html>` que la ruta actual es de colores fijos. El atributo
 * `data-theme` sobrevive a la navegación del lado del cliente, así que sin
 * esta marca /report y /analyzing heredarían `color-scheme: dark` (barras de
 * desplazamiento y controles nativos oscuros sobre tarjetas blancas).
 */
export default function ThemeScope() {
  const pathname = usePathname();
  useEffect(() => {
    const fixed = FIXED_LIGHT_ROUTES.some((r) => pathname.startsWith(r));
    document.documentElement.toggleAttribute("data-fixed-light", fixed);
  }, [pathname]);
  return null;
}
