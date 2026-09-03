import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";

const snapshot = {
  manifest: {
    datasets: {
      overview: {
        path: "snapshots/demo-v1/overview.json",
        sha256: "13046979b100d92a07ea391dbbe003a3e58333da33916db1bb62666a88c7320d",
      },
    },
    generated_at: "2026-09-02T23:55:02Z",
    quality_status: "PASS" as const,
    record_counts: { telemetry: 288 },
    schema_version: 1 as const,
    snapshot_id: "demo-v1",
    source_period_end: "2026-09-02T23:55:00Z",
    source_period_start: "2026-09-02T00:00:00Z",
  },
  overview: {
    availability: {
      available_intervals: 272,
      scheduled_intervals: 288,
      value: 0.9444444444444444,
    },
    schema_version: 1 as const,
    terminal_id: "TM-001",
  },
};

describe("App", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("provides skip navigation and the approved product sections", () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getAllByRole("navigation", { name: "Primary navigation" })).toHaveLength(2);
    for (const label of ["Overview", "Equipment", "Incidents", "Live Demo", "Data Health"]) {
      expect(screen.getAllByRole("link", { name: label })).toHaveLength(2);
    }
  });

  it("updates the global filters in the URL", () => {
    window.history.replaceState({}, "", "/");
    render(<App loadData={() => new Promise(() => undefined)} />);

    fireEvent.change(screen.getByLabelText("Terminal"), { target: { value: "TM-002" } });
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "7d" } });

    expect(window.location.search).toBe("?terminal=TM-002&range=7d");
  });

  it("identifies the control tower and simulated data source", () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    expect(
      screen.getByRole("heading", { name: "Terminal Operations Control Tower" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Simulated terminal operations data")).toBeInTheDocument();
  });

  it("renders the validated availability snapshot", async () => {
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findAllByText("94.4%")).toHaveLength(2);
  });

  it("renders the overview KPI rail from validated snapshot fields", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      overview: {
        ...snapshot.overview,
        active_incidents: 1,
        average_dwell_minutes: 63.75,
        mttr_minutes: 30,
        throughput: 4,
      },
    })} />);

    expect(await screen.findByText("4 moves")).toBeInTheDocument();
    expect(screen.getByText("63.8 min")).toBeInTheDocument();
    expect(screen.getByText("30 min")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Terminal throughput trend" })).toBeInTheDocument();
    expect(screen.getByText("Trend data unavailable")).toBeInTheDocument();
  });

  it("shows an honest unavailable state when filters do not match the snapshot", async () => {
    window.history.replaceState({}, "", "/");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    fireEvent.change(screen.getByLabelText("Terminal"), { target: { value: "TM-002" } });

    expect(await screen.findByText("Snapshot unavailable for selected filters")).toBeInTheDocument();
    expect(screen.queryByText("94.4%")).not.toBeInTheDocument();
  });

  it("shows an explicit error without fabricating a KPI", async () => {
    render(<App loadData={() => Promise.reject(new Error("invalid snapshot"))} />);

    expect(await screen.findByText("Operational snapshot unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });
});
