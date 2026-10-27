import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reportStore } from "@/lib/reportStore";
import { makeReport } from "@/test/fixtures";
import ReportPage from "./page";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/api", () => ({ downloadPdf: vi.fn() }));

const TAB_NAMES = [/^Hipótesis/, /^Caso clínico/, /^Debate/, /^Ensayos clínicos/, /^Bibliografía/];

function renderReport() {
  reportStore.save(makeReport());
  render(<ReportPage />);
  return screen.getAllByRole("tab");
}

/** Asserts `index` is the only selected, tabbable and focused tab. */
function expectSelected(tabs: HTMLElement[], index: number) {
  tabs.forEach((tab, i) => {
    expect(tab).toHaveAttribute("aria-selected", String(i === index));
    expect(tab).toHaveAttribute("tabindex", i === index ? "0" : "-1");
  });
  expect(tabs[index]).toHaveFocus();
  expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", tabs[index].id);
  expect(tabs[index]).toHaveAttribute("aria-controls", "reporte-panel");
}

describe("ReportPage tabs keyboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("renders the five tabs with the first one selected", () => {
    const tabs = renderReport();

    expect(tabs).toHaveLength(5);
    tabs.forEach((tab, i) => expect(tab).toHaveAccessibleName(TAB_NAMES[i]));
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[0]).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Test hypothesis");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("moves right with ArrowRight and wraps from the last tab to the first", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();
    tabs[0].focus();

    for (let i = 1; i < tabs.length; i++) {
      await user.keyboard("{ArrowRight}");
      expectSelected(tabs, i);
    }
    await user.keyboard("{ArrowRight}");
    expectSelected(tabs, 0);
  });

  it("moves left with ArrowLeft and wraps from the first tab to the last", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();
    tabs[0].focus();

    await user.keyboard("{ArrowLeft}");
    expectSelected(tabs, 4);
    await user.keyboard("{ArrowLeft}");
    expectSelected(tabs, 3);
  });

  it("jumps to the last tab with End and to the first with Home", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();
    tabs[0].focus();

    await user.keyboard("{End}");
    expectSelected(tabs, 4);
    await user.keyboard("{Home}");
    expectSelected(tabs, 0);
  });

  it("shows the panel of the tab it lands on", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();
    tabs[0].focus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Test narrative.");
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent("Test hypothesis");
  });

  it("ignores Alt+ArrowLeft and other modified arrows", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();
    tabs[0].focus();

    await user.keyboard("{Alt>}{ArrowLeft}{/Alt}");
    expectSelected(tabs, 0);
    await user.keyboard("{Control>}{ArrowRight}{/Control}");
    expectSelected(tabs, 0);
    await user.keyboard("{Shift>}{End}{/Shift}");
    expectSelected(tabs, 0);
  });

  it("selects a tab on click", async () => {
    const user = userEvent.setup();
    const tabs = renderReport();

    await user.click(tabs[2]);
    expectSelected(tabs, 2);
  });
});
