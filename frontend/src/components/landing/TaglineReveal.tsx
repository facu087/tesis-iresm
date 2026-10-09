"use client";

import { Fragment, useEffect, useRef } from "react";

/**
 * Tagline reveal: a large type statement whose words light up one by one, in
 * reading order, as the block scrolls through the viewport.
 *
 * Progressive enhancement. The server sends every word at full colour, so the
 * text is readable without JavaScript. After mounting, and only if the user
 * did not ask for reduced motion, the block is marked as enhanced (words drop
 * to a muted tone, see `.landing-tagline` in `globals.css`) and each word is
 * switched on as the scroll position advances.
 *
 * Words on the same line cross any trigger line at the same instant, so an
 * observer per word would flip whole lines at once. The position is read
 * instead from a single passive scroll listener throttled through
 * `requestAnimationFrame`, and that listener is only attached while an
 * `IntersectionObserver` reports the block on screen. Progress only moves
 * forward: a lit word never fades back.
 */

/** Viewport fraction (from the top) where the reveal starts. */
const START_LINE = 0.85;
/** Viewport fraction (from the top) the block's bottom reaches when done. */
const END_LINE = 0.45;
/** Stagger between words lit within the same frame, in milliseconds. */
const WORD_STAGGER_MS = 40;

interface TaglineRevealProps {
  /** Lines of the statement; each one breaks where the thought breaks. */
  lines: readonly string[];
  className?: string;
}

export default function TaglineReveal({ lines, className = "" }: TaglineRevealProps) {
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const words = Array.from(node.querySelectorAll<HTMLElement>("[data-word]"));
    if (words.length === 0) return;

    let lit = 0;
    let frame = 0;
    let listening = false;

    const update = () => {
      frame = 0;
      const rect = node.getBoundingClientRect();
      const viewport = window.innerHeight;
      const start = viewport * START_LINE;
      const end = viewport * END_LINE;
      const progress = (start - rect.top) / (start - end + rect.height);
      const target = Math.round(Math.min(1, Math.max(0, progress)) * words.length);

      const batchStart = lit;
      while (lit < target) {
        const word = words[lit];
        word.style.transitionDelay = `${(lit - batchStart) * WORD_STAGGER_MS}ms`;
        word.dataset.on = "true";
        lit += 1;
      }
      if (lit === words.length) stop();
    };

    const onScroll = () => {
      if (frame === 0) frame = requestAnimationFrame(update);
    };

    const listen = (active: boolean) => {
      if (active === listening) return;
      listening = active;
      if (active) {
        window.addEventListener("scroll", onScroll, { passive: true });
        window.addEventListener("resize", onScroll, { passive: true });
      } else {
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
      }
    };

    const observer = new IntersectionObserver(([entry]) => {
      listen(entry.isIntersecting);
      if (entry.isIntersecting) onScroll();
    });

    function stop() {
      observer.disconnect();
      listen(false);
      if (frame !== 0) cancelAnimationFrame(frame);
      frame = 0;
    }

    node.dataset.enhanced = "true";
    update(); // words already above the trigger (reload mid page) start lit
    if (lit < words.length) observer.observe(node);

    return () => {
      stop();
      // Leave the text at full colour if the component goes away.
      delete node.dataset.enhanced;
    };
  }, []);

  return (
    <p ref={ref} className={`landing-tagline ${className}`}>
      {lines.map((line, lineIndex) => (
        <span key={line} className="block">
          {line.split(" ").map((word, wordIndex) => (
            <Fragment key={`${lineIndex}-${wordIndex}`}>
              <span data-word>{word}</span>{" "}
            </Fragment>
          ))}
        </span>
      ))}
    </p>
  );
}
