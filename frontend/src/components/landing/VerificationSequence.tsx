"use client";

import { useCallback, useEffect, useRef } from "react";
import { ArrowCounterClockwiseIcon } from "@phosphor-icons/react/ssr";
import { FOCUS_RING, TRANSITION } from "@/components/landing/styles";

/**
 * Frame of the citation comparison (`BeforeAfter`) that plays the check as a
 * short sequence the first time the comparison scrolls into view.
 *
 * Progressive enhancement, same contract as `TaglineReveal` and
 * `PipelineDiagram`: the server sends the resolved comparison, which is also
 * what shows without JavaScript and under reduced motion. After mounting, the
 * figure is armed (`data-beat="idle"`) and an `IntersectionObserver` starts
 * the sequence once; `data-beat` then walks through the beats and is removed
 * at the end, so the resting state is exactly the server render.
 *
 *   idle    nothing resolved yet (armed, waiting for the viewport)
 *   cited   beat 1: the title the model declared
 *   lookup  beat 2: the PubMed side shows a skeleton for that PMID
 *   result  beat 3: the title PubMed returns
 *   (none)  the verdict resolves; final state
 *
 * Only opacity and a small offset change (`.landing-verify` in
 * `globals.css`): every part stays in the DOM, in reading order and in the
 * accessibility tree, so the block never changes height and a screen reader
 * reads the whole comparison at any moment. Nothing is a live region.
 *
 * The DOM is touched directly instead of going through React state, as the
 * other landing reveals do.
 */

/** Share of the comparison that must be on screen to start the sequence. */
const TRIGGER_RATIO = 0.35;
/** A block taller than the viewport also counts once it fills this much of it. */
const TRIGGER_VIEWPORT_SHARE = 0.5;
/** Thresholds observed, so the callback also fires while a tall block enters. */
const THRESHOLDS = [0.1, 0.2, TRIGGER_RATIO, 0.5, 0.75];

/** Start of each beat after the sequence begins, in milliseconds. */
const LOOKUP_AT_MS = 800;
const RESULT_AT_MS = 1900;
const VERDICT_AT_MS = 2600;

interface VerificationSequenceProps {
  /** The comparison card, server rendered in its final state. */
  children: React.ReactNode;
  /** Caption of the figure; its text also names the figure. */
  caption: React.ReactNode;
  captionId: string;
}

export default function VerificationSequence({
  children,
  caption,
  captionId,
}: VerificationSequenceProps) {
  const ref = useRef<HTMLElement>(null);
  const timers = useRef<number[]>([]);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  /** Runs the sequence from the start, dropping any run in progress. */
  const play = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    clearTimers();
    // Any run, the replay button included, spends the automatic one: without
    // this, replaying before the trigger point would play it twice.
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      delete node.dataset.beat; // final state, at once
      return;
    }

    const at = (delay: number, beat: string | null) => {
      timers.current.push(
        window.setTimeout(() => {
          if (beat) node.dataset.beat = beat;
          else delete node.dataset.beat;
        }, delay),
      );
    };

    // Hiding is instant; the reflow makes the first beat a real transition.
    node.dataset.beat = "idle";
    void node.offsetWidth;
    node.dataset.beat = "cited";
    at(LOOKUP_AT_MS, "lookup");
    at(RESULT_AT_MS, "result");
    at(VERDICT_AT_MS, null);
  }, [clearTimers]);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // The last record of a batch is the current state.
        const latest = entries[entries.length - 1];
        if (!latest?.isIntersecting) return;
        const viewport = latest.rootBounds?.height ?? window.innerHeight;
        const inView =
          latest.intersectionRatio >= TRIGGER_RATIO ||
          latest.intersectionRect.height >= viewport * TRIGGER_VIEWPORT_SHARE;
        if (!inView) return;
        play(); // disconnects: scrolling past never replays it
      },
      { threshold: THRESHOLDS },
    );
    observerRef.current = observer;

    node.dataset.beat = "idle";
    observer.observe(node);

    // Failsafe: printing before the section was reached shows it resolved.
    const resolve = () => {
      clearTimers();
      observer.disconnect();
      observerRef.current = null;
      delete node.dataset.beat;
    };
    window.addEventListener("beforeprint", resolve);

    return () => {
      window.removeEventListener("beforeprint", resolve);
      observer.disconnect();
      observerRef.current = null;
      clearTimers();
      // Never leave the comparison unresolved behind an unmounted component.
      delete node.dataset.beat;
    };
  }, [play, clearTimers]);

  return (
    <figure ref={ref} aria-labelledby={captionId} className="landing-verify m-0">
      {children}
      <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-xs text-fg-muted">
        <span id={captionId}>{caption}</span>
        <button
          type="button"
          onClick={play}
          className={`landing-verify-replay inline-flex shrink-0 cursor-pointer items-center gap-2 rounded-sm py-1 text-sm font-semibold text-accent underline-offset-4 hover:underline active:translate-y-px ${TRANSITION} ${FOCUS_RING}`}
        >
          <ArrowCounterClockwiseIcon aria-hidden="true" weight="bold" className="size-4" />
          Ver de nuevo
        </button>
      </figcaption>
    </figure>
  );
}
