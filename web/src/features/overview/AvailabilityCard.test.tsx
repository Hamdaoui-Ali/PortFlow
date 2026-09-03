import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AvailabilityCard } from "./AvailabilityCard";

describe("AvailabilityCard", () => {
  it("renders a percentage, definition, and UTC snapshot time", () => {
    render(<AvailabilityCard value={0.944444} generatedAt="2026-09-02T23:55:02Z" />);

    expect(screen.getByText("94.4%")).toBeInTheDocument();
    expect(
      screen.getAllByText(/available intervals divided by scheduled intervals/i),
    ).toHaveLength(2);
    expect(screen.getByText(/2 September 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/23:55 UTC/i)).toBeInTheDocument();
  });

  it("does not invent a percentage without a denominator", () => {
    render(<AvailabilityCard value={null} generatedAt="2026-09-02T23:55:02Z" />);

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });
});
