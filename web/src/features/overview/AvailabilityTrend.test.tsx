import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReplayEvent } from "./hourlyAvailability";
import { AvailabilityTrend } from "./AvailabilityTrend";

const events: ReplayEvent[] = Array.from({ length: 24 }, (_, hour) => ({
  available: true,
  equipment_id: "QC-001",
  event_id: `evt-${String(hour + 1).padStart(2, "0")}`,
  event_timestamp: `2026-09-02T${String(hour).padStart(2, "0")}:00:00Z`,
  state: "ACTIVE",
  terminal_id: "TM-001",
}));

describe("AvailabilityTrend", () => {
  it("shows readable checkpoint labels while retaining every hourly point", () => {
    render(<AvailabilityTrend events={events} />);

    const chart = screen.getByRole("img", { name: /hourly equipment availability chart/i });
    const labels = within(chart).getAllByText(/^\d{2}:00$/);
    const visibleLabels = labels.filter((label) => label.classList.contains("trend-label-visible"));

    expect(labels).toHaveLength(24);
    expect(visibleLabels.map((label) => label.textContent)).toEqual([
      "00:00",
      "04:00",
      "08:00",
      "12:00",
      "16:00",
      "20:00",
      "23:00",
    ]);
    expect(screen.getByText("100%")).toBeVisible();
    expect(screen.getByText("50%")).toBeVisible();
    expect(screen.getByText("0%")).toBeVisible();
  });
});
