import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { OverviewV1 } from "../../data/schema";
import { OverviewKpiRail } from "./OverviewKpiRail";

const overview: OverviewV1 = {
  availability: {
    available_intervals: 272,
    scheduled_intervals: 288,
    value: 0.9444444444444444,
  },
  active_incidents: 3,
  schema_version: 1,
  terminal_id: "TM-001",
};

describe("OverviewKpiRail", () => {
  it("offers native drill-down links for equipment and incident KPIs", () => {
    render(<OverviewKpiRail overview={overview} />);

    expect(screen.getByRole("link", { name: "Open equipment" })).toHaveAttribute(
      "href",
      "#equipment",
    );
    expect(screen.getByRole("link", { name: "Open incidents" })).toHaveAttribute(
      "href",
      "#incidents",
    );
  });
});
