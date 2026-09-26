"use client";

import { useEffect, useRef } from "react";

/**
 * Animación de aparición al hacer scroll, como mejora progresiva (design D6).
 *
 * El HTML servido por el servidor ya trae las clases de "visible"
 * (`opacity-100 translate-y-0`): sin JavaScript el contenido se ve completo.
 * Recién después de montarse — y solo si el usuario no pidió
 * `prefers-reduced-motion` — el efecto oculta el nodo (8–16px, opacity 0)
 * manipulando `classList` directamente (sin pasar por estado de React, para
 * no disparar un re-render en cascada) hasta que un `IntersectionObserver`
 * compartido lo revela (300ms) al entrar en el viewport. Deja de observar
 * tras revelar: nunca vuelve a ocultarse.
 *
 * Renderiza siempre un `div`: para envolver un `<section>` u otro landmark,
 * anidarlo adentro (`<ScrollReveal><section>…</section></ScrollReveal>`).
 */

const HIDDEN_CLASSES = ["opacity-0", "translate-y-3"];
const VISIBLE_CLASSES = ["opacity-100", "translate-y-0"];

let sharedObserver: IntersectionObserver | null = null;
const revealCallbacks = new WeakMap<Element, () => void>();

function getSharedObserver(): IntersectionObserver | null {
  if (typeof window === "undefined") return null;
  if (sharedObserver) return sharedObserver;

  sharedObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const reveal = revealCallbacks.get(entry.target);
        reveal?.();
        sharedObserver?.unobserve(entry.target);
        revealCallbacks.delete(entry.target);
      }
    },
    { threshold: 0.15, rootMargin: "0px 0px -10% 0px" },
  );
  return sharedObserver;
}

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
}

export default function ScrollReveal({
  children,
  className = "",
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReducedMotion) return; // queda visible, sin animar

    const observer = getSharedObserver();
    if (!observer) return;

    // Manipulación directa del DOM (no estado de React): oculta recién acá,
    // como mejora progresiva, sin provocar un re-render.
    node.classList.remove(...VISIBLE_CLASSES);
    node.classList.add(...HIDDEN_CLASSES);

    revealCallbacks.set(node, () => {
      node.classList.remove(...HIDDEN_CLASSES);
      node.classList.add(...VISIBLE_CLASSES);
    });
    observer.observe(node);

    return () => {
      observer.unobserve(node);
      revealCallbacks.delete(node);
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`${className} translate-y-0 opacity-100 transition-all duration-300 ease-out motion-reduce:transition-none`}
    >
      {children}
    </div>
  );
}
