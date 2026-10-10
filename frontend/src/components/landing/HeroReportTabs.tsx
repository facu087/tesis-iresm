"use client";

import { useRef, useState } from "react";
import {
  EXAMPLE_HYPOTHESES,
  ExampleHypothesis,
} from "@/components/landing/reportExample";
import { FOCUS_RING, TRANSITION } from "@/components/landing/styles";

/**
 * Body of the hero report card: one tab per hypothesis status (Respaldada,
 * Pendiente, Especulativa), each showing the matching example hypothesis with
 * its evidence level, its status and what the report says about its citation.
 *
 * Tabs pattern with automatic activation: the arrow keys (wrapping), Home and
 * End move the focus and select the tab they land on; a click, Enter or Space
 * select it too. Only the selected tab is in the tab order (roving tabindex).
 *
 * The three panels share one grid cell, so the card is always as tall as the
 * tallest of them and switching never moves the rest of the hero. The first
 * panel is selected in the server render; without JavaScript the tab row is
 * hidden (`globals.css`) and the card shows that hypothesis alone.
 */
const TABS = EXAMPLE_HYPOTHESES.map((hypothesis) => ({
  hypothesis,
  tabId: `hero-report-tab-${hypothesis.id.toLowerCase()}`,
  panelId: `hero-report-panel-${hypothesis.id.toLowerCase()}`,
}));

const NEXT_INDEX: Record<string, (current: number) => number> = {
  ArrowRight: (current) => (current + 1) % TABS.length,
  ArrowLeft: (current) => (current - 1 + TABS.length) % TABS.length,
  Home: () => 0,
  End: () => TABS.length - 1,
};

export default function HeroReportTabs() {
  const [selected, setSelected] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    // Leave browser shortcuts such as Alt+ArrowLeft (history back) alone.
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const move = NEXT_INDEX[event.key];
    if (!move) return;
    event.preventDefault();
    const next = move(selected);
    setSelected(next);
    tabRefs.current[next]?.focus();
  }

  return (
    <>
      <div className="landing-hero-tabs bg-surface px-2 py-3 min-[360px]:px-4 sm:px-6">
        {/* Nested radius: both shapes are full pills, 4 px apart. */}
        <div
          role="tablist"
          aria-label="Estado de la hipótesis"
          onKeyDown={onKeyDown}
          className="grid grid-cols-3 gap-1 rounded-full bg-bg-subtle p-1"
        >
          {TABS.map(({ hypothesis, tabId, panelId }, index) => {
            const isSelected = index === selected;
            return (
              <button
                key={tabId}
                ref={(node) => {
                  tabRefs.current[index] = node;
                }}
                type="button"
                role="tab"
                id={tabId}
                aria-selected={isSelected}
                aria-controls={panelId}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => setSelected(index)}
                className={`cursor-pointer rounded-full px-1 py-2 text-center text-xs font-semibold whitespace-nowrap min-[360px]:text-sm active:scale-[0.98] sm:px-3 ${TRANSITION} ${FOCUS_RING} ${
                  isSelected
                    ? "bg-accent text-accent-fg"
                    : "text-fg-muted hover:text-accent"
                }`}
              >
                {hypothesis.status}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid bg-surface">
        {TABS.map(({ hypothesis, tabId, panelId }, index) => {
          const isSelected = index === selected;
          return (
            <div
              key={panelId}
              role="tabpanel"
              id={panelId}
              aria-labelledby={tabId}
              tabIndex={isSelected ? 0 : -1}
              data-selected={isSelected}
              className="landing-hero-panel rounded-b-2xl p-6 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
            >
              <ExampleHypothesis hypothesis={hypothesis} lead />
            </div>
          );
        })}
      </div>
    </>
  );
}
