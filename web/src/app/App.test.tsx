import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
  it("identifies the control tower and simulated data source", () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    expect(
      screen.getByRole("heading", { name: "Terminal Operations Control Tower" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Simulated terminal operations data")).toBeInTheDocument();
  });

  it("renders the validated availability snapshot", async () => {
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByText("94.4%")).toBeInTheDocument();
  });

  it("shows an explicit error without fabricating a KPI", async () => {
    render(<App loadData={() => Promise.reject(new Error("invalid snapshot"))} />);

    expect(await screen.findByText("Operational snapshot unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });
});
