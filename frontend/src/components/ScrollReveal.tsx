"use client";

import { useEffect, useRef } from "react";

/**
 * Scroll reveal as progressive enhancement, used only by the landing.
 *
 * The server sends the content fully visible: without JavaScript nothing is
 * hidden. After mounting, and only if the user did not ask for reduced motion
 * and the node is still below the viewport, the effect marks the node as
 * hidden (`data-reveal="hidden"`: 64 px down, blurred, transparent) until a
 * shared `IntersectionObserver` reveals it with a heavy fade up of 900 ms on
 * the landing curve. The styles live in `globals.css` (`.landing-reveal`).
 *
 * The DOM is touched directly instead of going through React state, so
 * arming a reveal never triggers a cascading render. A revealed node is no
 * longer observed: it never hides again.
 *
 * Always renders a `div`: to wrap a `<section>` or another landmark, nest it
 * inside (`<ScrollReveal><section>…</section></ScrollReveal>`).
 */

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
    // The hidden state shifts the node 64 px down; a small threshold keeps
    // tall blocks (the report example) from waiting too long to appear.
    { threshold: 0.05, rootMargin: "0px 0px -8% 0px" },
  );
  return sharedObserver;
}

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  /** Delay of the reveal in milliseconds, to stagger sibling blocks. */
  delay?: number;
}

export default function ScrollReveal({
  children,
  className = "",
  delay = 0,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReducedMotion) return; // stays visible, no animation

    // What is already on screen when mounting stays visible: hiding it here
    // would make it appear, vanish and come back.
    if (node.getBoundingClientRect().top < window.innerHeight) return;

    const observer = getSharedObserver();
    if (!observer) return;

    node.dataset.reveal = "hidden";
    revealCallbacks.set(node, () => {
      node.dataset.reveal = "shown";
    });
    observer.observe(node);

    return () => {
      observer.unobserve(node);
      revealCallbacks.delete(node);
      // Never leave content hidden behind an unmounted observer.
      if (node.dataset.reveal === "hidden") delete node.dataset.reveal;
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`landing-reveal ${className}`}
      style={
        delay > 0
          ? ({ "--landing-delay": `${delay}ms` } as React.CSSProperties)
          : undefined
      }
    >
      {children}
    </div>
  );
}
