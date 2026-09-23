import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SnapshotFilterScope } from "./filterScope";
import { FilterRecoveryState } from "./FilterRecoveryState";

const filterScope: SnapshotFilterScope = {
  terminalId: "TM-001",
  terminalLabel: "Casablanca Terminal",
  periodLabel: "02 Sept 2026, 00:00-23:55 UTC",
};

describe("FilterRecoveryState", () => {
  it("keeps the Overview recovery copy and exposes the published scope", () => {
    render(
      <FilterRecoveryState
        filterScope={filterScope}
        onResetFilters={vi.fn()}
        resource="overview"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Snapshot unavailable for selected filters",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "These filters do not match the published snapshot.",
    );
    expect(screen.getByText("Published scope:")).toBeInTheDocument();
    expect(screen.getByText("Casablanca Terminal")).toBeInTheDocument();
    expect(screen.getByText("02 Sept 2026, 00:00-23:55 UTC")).toBeInTheDocument();
  });

  it.each(["equipment", "incidents"] as const)(
    "describes unsupported filters for the %s route",
    (resource) => {
      render(
        <FilterRecoveryState
          filterScope={filterScope}
          onResetFilters={vi.fn()}
          resource={resource}
        />,
      );

      expect(screen.getByRole("heading", { name: `${resource[0].toUpperCase()}${resource.slice(1)} unavailable for selected filters` })).toBeInTheDocument();
      expect(screen.getByText("The selected filters are outside the published snapshot scope.")).toBeInTheDocument();
    },
  );

  it("calls the shared reset action", () => {
    const onResetFilters = vi.fn();
    render(
      <FilterRecoveryState
        filterScope={filterScope}
        onResetFilters={onResetFilters}
        resource="equipment"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reset filters to published scope" }));

    expect(onResetFilters).toHaveBeenCalledOnce();
  });
});
