import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppShell, useAppFilters, type SnapshotHeaderStatus } from "./AppShell";

const readyStatus: SnapshotHeaderStatus = {
  kind: "healthy",
  label: "Current snapshot",
  message: "Data is healthy and current.",
  generatedAt: "2026-09-02T23:55:02Z",
};

const filterScope = {
  terminalLabel: "Casablanca Terminal",
  periodLabel: "02 Sept 2026, 00:00–23:55 UTC",
};

function FilterProbe() {
  const { resetFilters } = useAppFilters();

  return (
    <button type="button" onClick={resetFilters}>
      Reset filters in test
    </button>
  );
}

describe("AppShell", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("shows the published scope and resets filters while preserving the route hash", () => {
    window.history.replaceState({}, "", "/?terminal=TM-002&range=7d#equipment");

    render(
      <AppShell snapshotStatus={readyStatus} filterScope={filterScope}>
        <FilterProbe />
      </AppShell>,
    );

    expect(screen.getByRole("note", { name: "Published snapshot scope" })).toHaveTextContent(
      "Published scope Casablanca Terminal 02 Sept 2026, 00:00–23:55 UTC",
    );

    fireEvent.click(screen.getByRole("button", { name: "Reset filters in test" }));

    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("#equipment");
    expect(screen.getByLabelText("Terminal")).toHaveValue("all");
    expect(screen.getByLabelText("Date range")).toHaveValue("24h");
  });

  it("returns keyboard focus to the main content after resetting filters", async () => {
    window.history.replaceState({}, "", "/?terminal=TM-002&range=7d#overview");

    render(
      <AppShell snapshotStatus={readyStatus} filterScope={filterScope}>
        <FilterProbe />
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reset filters in test" }));

    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });

  it("does not show a scope note while the snapshot is loading", () => {
    render(
      <AppShell
        snapshotStatus={{
          kind: "loading",
          label: "Loading snapshot",
          message: "Loading published data.",
        }}
      >
        <div />
      </AppShell>,
    );

    expect(screen.queryByRole("note", { name: "Published snapshot scope" })).not.toBeInTheDocument();
  });
});
