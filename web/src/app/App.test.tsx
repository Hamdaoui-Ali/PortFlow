import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { snapshotCache } from "../data/cache";

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
    snapshotCache.clear();
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

  it("renders the equipment fleet for the equipment hash route", async () => {
    window.history.replaceState({}, "", "/#equipment");
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      equipment: {
        status: "ready" as const,
        records: [{
          alarm_count: 3,
          availability: 0.9444444444444444,
          available: true,
          current_state: "ACTIVE",
          downtime_minutes: 80,
          equipment_id: "QC-001",
          mtbf_hours: 24,
          mttr_minutes: 30,
          terminal_id: "TM-001",
          utilization: 0.7426470588235294,
        }],
      },
    })} />);

    expect(await screen.findByRole("heading", { name: "Equipment fleet" }))
      .toBeInTheDocument();
    expect(screen.queryByText("Terminal throughput (moves)")).not.toBeInTheDocument();
  });

  it("renders the Live Demo for the live-demo hash route", async () => {
    window.history.replaceState({}, "", "/#live-demo");
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      event_replay: [
        { available: true, equipment_id: "QC-001", event_id: "evt-1", event_timestamp: "2026-09-02T00:00:00Z", state: "ACTIVE", terminal_id: "TM-001" },
      ],
    })} />);

    expect(await screen.findByRole("heading", { name: "Live Demo" })).toBeInTheDocument();
    expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start replay" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Live Demo" })[0]).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("main")).not.toHaveAttribute("aria-live");
    expect(screen.getByRole("list", { name: "Replay activity" })).not.toHaveAttribute("aria-live");
  });

  it("distinguishes missing and empty replay datasets honestly", async () => {
    window.history.replaceState({}, "", "/#live-demo");
    const { rerender } = render(<App loadData={() => Promise.resolve(snapshot)} />);
    expect(await screen.findByText("Replay dataset not published")).toBeInTheDocument();

    rerender(<App loadData={() => Promise.resolve({ ...snapshot, event_replay: [] })} />);
    expect(await screen.findByText("Replay has no events")).toBeInTheDocument();
    expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
  });

  it("keeps the stale snapshot notice above the Live Demo", async () => {
    window.history.replaceState({}, "", "/#live-demo");
    const { rerender } = render(<App loadData={() => Promise.resolve({
      ...snapshot,
      event_replay: [
        { available: true, equipment_id: "QC-001", event_id: "evt-1", event_timestamp: "2026-09-02T00:00:00Z", state: "ACTIVE", terminal_id: "TM-001" },
      ],
    })} />);
    expect(await screen.findByRole("heading", { name: "Live Demo" })).toBeInTheDocument();

    rerender(<App loadData={() => Promise.reject(new Error("network down"))} />);
    expect(await screen.findByRole("status", { name: "Showing last valid snapshot" })).toBeInTheDocument();
    expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
  });

  it("falls back to Overview for an unknown hash route", async () => {
    window.history.replaceState({}, "", "/#not-a-portflow-route");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByText("Terminal throughput (moves)")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Equipment fleet" })).not.toBeInTheDocument();
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
    expect(screen.getAllByRole("group", { name: /About/ })).toHaveLength(6);
  });

  it("renders the availability trend when replay data is present", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      event_replay: [
        { available: true, equipment_id: "QC-001", event_id: "evt-1", event_timestamp: "2026-09-02T00:00:00Z", state: "ACTIVE", terminal_id: "TM-001" },
        { available: false, equipment_id: "QC-001", event_id: "evt-2", event_timestamp: "2026-09-02T00:05:00Z", state: "UNAVAILABLE", terminal_id: "TM-001" },
      ],
    })} />);

    expect(await screen.findByRole("img", { name: /Hourly availability trend/ })).toBeInTheDocument();
    expect(screen.getByText("Hourly availability ranged from 50.0% to 50.0%.")).toBeInTheDocument();
    expect(screen.getByText("00:00")).toBeInTheDocument();
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

  it("retains the last valid snapshot when the next load fails", async () => {
    const firstLoad = () => Promise.resolve(snapshot);
    const { rerender } = render(<App loadData={firstLoad} />);

    expect(await screen.findAllByText("94.4%")).toHaveLength(2);

    rerender(<App loadData={() => Promise.reject(new Error("network down"))} />);

    expect(await screen.findByRole("status", { name: "Showing last valid snapshot" })).toBeInTheDocument();
    expect(screen.getAllByText("94.4%")).toHaveLength(2);
  });
});
