import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DiagnosticNotice from "@/components/landing/DiagnosticNotice";

describe("test runner", () => {
  it("renders a component through the @/ alias with jest-dom matchers", () => {
    const { container } = render(<DiagnosticNotice />);
    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText(/diagn/i)).toBeVisible();
  });
});
