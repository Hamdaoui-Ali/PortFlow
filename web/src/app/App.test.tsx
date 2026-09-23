import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App, loadDefaultSnapshot } from "./App";
import { snapshotCache } from "../data/cache";
import { incidentRecords } from "../test/incidentFixtures";

vi.mock("../data/loadSnapshot", () => ({
  loadSnapshot: vi.fn(),
}));

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
  quality: {
    status: "ready" as const,
    data: {
      bronze_rows: 305,
      silver_rows: 305,
      quarantine_rows: 0,
      reason_counts: {},
      dbt_test_status: "PASS" as const,
    },
  },
};

describe("App", () => {
  afterEach(() => {
    vi.useRealTimers();
    window.history.replaceState({}, "", "/");
    snapshotCache.clear();
  });

  it("shows current snapshot status and its UTC generation time across routes", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T23:55:02Z"));
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    await act(async () => { await Promise.resolve(); });

    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Current snapshot");
    expect(status).toHaveTextContent("Data is healthy and current.");
    expect(status.querySelector("time")).toHaveAttribute("datetime", "2026-09-02T23:55:02Z");
    expect(status).toHaveTextContent("Updated 02 Sept 2026, 23:55 UTC");

    fireEvent.click(screen.getAllByRole("link", { name: "Equipment" })[0]);
    act(() => vi.advanceTimersByTime(0));

    expect(screen.getByRole("heading", { name: "Equipment dataset not published" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Current snapshot");
  });

  it("offers a direct Data Health review from a ready snapshot status", async () => {
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    await act(async () => { await Promise.resolve(); });

    const reviewLink = screen.getByRole("link", { name: "Review Data Health" });
    expect(reviewLink).toHaveAttribute("href", "#data-health");

    fireEvent.click(reviewLink);
    expect(await screen.findByRole("heading", { name: "Data Health" })).toBeInTheDocument();
  });

  it("shows stale ready snapshots instead of claiming they are healthy", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-04T23:55:02.001Z"));
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    await act(async () => { await Promise.resolve(); });

    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Stale snapshot");
    expect(status).toHaveTextContent("Data is healthy but stale.");
  });

  it("updates freshness when a ready snapshot crosses the stale threshold without navigation", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T23:55:02Z"));
    const nearStaleSnapshot = {
      ...snapshot,
      manifest: { ...snapshot.manifest, generated_at: "2026-09-02T23:55:03Z" },
    };
    render(<App loadData={() => Promise.resolve(nearStaleSnapshot)} />);
    await act(async () => { await Promise.resolve(); });

    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Current snapshot");

    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Current snapshot");

    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Stale snapshot");
  });

  it("rechecks freshness when the snapshot timestamp is beyond the browser timer limit", async () => {
    const browserTimerLimitMs = 2_147_000_000;
    const now = new Date("2026-09-03T23:55:02Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const futureSnapshot = {
      ...snapshot,
      manifest: {
        ...snapshot.manifest,
        generated_at: new Date(now.getTime() + browserTimerLimitMs + 10_000).toISOString(),
      },
    };
    render(<App loadData={() => Promise.resolve(futureSnapshot)} />);
    await act(async () => { await Promise.resolve(); });

    act(() => vi.advanceTimersByTime(browserTimerLimitMs));
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Current snapshot");

    act(() => vi.advanceTimersByTime(10_000 + 24 * 60 * 60 * 1000));
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Current snapshot");

    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Stale snapshot");
  });

  it("flags unavailable quality evidence in the shared snapshot status", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      quality: { status: "unavailable" as const },
    })} />);
    await act(async () => { await Promise.resolve(); });

    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Snapshot needs attention");
    expect(status).toHaveTextContent("Quality evidence is unavailable.");
    expect(status.querySelector("time")).toHaveAttribute("datetime", "2026-09-02T23:55:02Z");
  });

  it("shows loading status without inventing snapshot metadata", () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Loading snapshot");
    expect(status.querySelector("time")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Review Data Health" })).not.toBeInTheDocument();
  });

  it("provides skip navigation and the approved product sections", () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Mobile primary navigation" })).toBeInTheDocument();
    for (const label of ["Overview", "Equipment", "Incidents", "Live Demo", "Data Health"]) {
      expect(screen.getAllByRole("link", { name: label })).toHaveLength(2);
    }
  });

  it("moves focus to the main content after route navigation", async () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    fireEvent.click(screen.getAllByRole("link", { name: "Equipment" })[0]);

    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });

  it("keeps main focus after route navigation settles", async () => {
    render(<App loadData={() => new Promise(() => undefined)} />);

    const equipmentLink = screen.getAllByRole("link", { name: "Equipment" })[0];
    fireEvent.click(equipmentLink);
    equipmentLink.focus();

    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });

  it("resets the viewport before focusing main content after route navigation", async () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    try {
      render(<App loadData={() => new Promise(() => undefined)} />);

      fireEvent.click(screen.getAllByRole("link", { name: "Data Health" })[0]);

      await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
      expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "auto" });
    } finally {
      scrollTo.mockRestore();
    }
  });

  it("keeps the active navigation link aligned with the selected route", async () => {
    render(
      <App
        loadData={() =>
          Promise.resolve({
            ...snapshot,
            incidents: {
              status: "ready" as const,
              records: [
                {
                  equipment_id: "QC-001",
                  incident_id: "inc-000001",
                  opened_at: "2026-09-02T03:00:00Z",
                  resolved_at: "2026-09-02T03:30:00Z",
                  root_cause: "Hydraulic leak",
                  severity: "MAJOR" as const,
                  status: "RESOLVED" as const,
                  terminal_id: "TM-001",
                },
              ],
            },
          })
        }
      />
    );

    fireEvent.click(screen.getAllByRole("link", { name: "Data Health" })[0]);
    expect(await screen.findByRole("heading", { name: "Data Health" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Data Health" })[0]).toHaveAttribute("aria-current", "page");

    fireEvent.click(screen.getAllByRole("link", { name: "Incidents" })[0]);
    expect(await screen.findByRole("heading", { name: "Incident exploration" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Incidents" })[0]).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { name: "Data Health" })[0]).not.toHaveAttribute("aria-current");
  });

  it("renders the selected page in the same navigation interaction", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      equipment: {
        status: "ready" as const,
        records: [],
      },
    })} />);

    expect(await screen.findByText("Hourly equipment availability")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("link", { name: "Equipment" })[0]);

    expect(screen.getByRole("heading", { name: "Equipment fleet" })).toBeInTheDocument();
    expect(screen.queryByText("Loading selected view")).not.toBeInTheDocument();
  });

  it("preserves the active route when global filters change", () => {
    window.history.replaceState({}, "", "/?terminal=TM-001#equipment");
    render(<App loadData={() => new Promise(() => undefined)} />);

    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "7d" } });

    expect(window.location.search).toBe("?terminal=TM-001&range=7d");
    expect(window.location.hash).toBe("#equipment");
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

  it("renders snapshot equipment context on the Overview route", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      equipment: {
        status: "ready" as const,
        records: [{
          alarm_count: 3,
          availability: 0.8,
          available: false,
          current_state: "DOWN",
          downtime_minutes: 40,
          equipment_id: "QC-002",
          mtbf_hours: 24,
          mttr_minutes: 30,
          terminal_id: "TM-002",
          utilization: 0.4,
        }],
      },
    })} />);

    expect(await screen.findByRole("heading", { name: "Equipment pulse" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open equipment QC-002" })).toHaveAttribute(
      "href",
      "?equipment=QC-002#equipment",
    );
    expect(screen.getByText("80.0%")).toBeInTheDocument();
  });

  it("renders the incident pulse on the Overview route", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      incidents: { status: "ready" as const, records: [incidentRecords[1]] },
    })} />);

    expect(await screen.findByRole("heading", { name: "Incident pulse" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open incident inc-000002" })).toHaveAttribute(
      "href",
      "?incident=inc-000002#incidents",
    );
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
    expect(screen.queryByText("Hourly equipment availability")).not.toBeInTheDocument();
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

  it("renders Data Health independently of global filter matching", async () => {
    window.history.replaceState({}, "", "/?terminal=TM-002&range=7d#data-health");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("heading", { name: "Data Health" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Data Health" })[0]).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText("Snapshot unavailable for selected filters")).not.toBeInTheDocument();
  });

  it("keeps Overview usable when optional quality loading fails", async () => {
    render(<App loadData={() => Promise.resolve({
      ...snapshot,
      quality: { status: "unavailable" as const },
    })} />);

    expect(await screen.findAllByText("94.4%")).toHaveLength(2);
    expect(screen.getByText("Hourly equipment availability")).toBeInTheDocument();
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
    expect(await screen.findByRole("note", { name: "Refresh details" })).toBeInTheDocument();
    expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
  });

  it("keeps the stale snapshot notice above Data Health after reload failure", async () => {
    window.history.replaceState({}, "", "/#data-health");
    const { rerender } = render(<App loadData={() => Promise.resolve(snapshot)} />);
    expect(await screen.findByRole("heading", { name: "Data Health" })).toBeInTheDocument();

    rerender(<App loadData={() => Promise.reject(new Error("network down"))} />);

    const staleNotice = await screen.findByRole("note", { name: "Refresh details" });
    expect(staleNotice).toHaveTextContent("Refresh issue");
    expect(screen.getByRole("status", { name: "Snapshot freshness" })).toHaveTextContent("Showing last valid snapshot");
    expect(screen.getByRole("heading", { name: "Data Health" })).toBeInTheDocument();
    expect(staleNotice.compareDocumentPosition(screen.getByRole("heading", { name: "Data Health" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("falls back to Overview for an unknown hash route", async () => {
    window.history.replaceState({}, "", "/#not-a-portflow-route");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByText("Hourly equipment availability")).toBeInTheDocument();
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
    expect(screen.getByRole("region", { name: "Hourly equipment availability" })).toBeInTheDocument();
    expect(screen.getByText("Hourly availability data unavailable")).toBeInTheDocument();
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

    expect(await screen.findByRole("img", { name: /Hourly equipment availability chart/ })).toBeInTheDocument();
    expect(screen.getByText("Hourly equipment availability ranged from 50.0% to 50.0%.")).toBeInTheDocument();
    expect(screen.getByText(
      "Bars show equipment availability for each hour. The throughput value above is the total for the selected period; hourly throughput data is not available.",
    )).toBeInTheDocument();
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
    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Snapshot unavailable");
    expect(status.querySelector("time")).not.toBeInTheDocument();
  });

  it("uses only the shared freshness live region while loading", () => {
    const { container } = render(<App loadData={() => new Promise(() => undefined)} />);

    const liveRegions = container.querySelectorAll('[aria-live], [role="status"], [role="alert"]');
    expect(liveRegions).toHaveLength(1);
    expect(liveRegions[0]).toHaveAttribute("aria-label", "Snapshot freshness");
  });

  it("uses only the shared freshness live region for initial errors", async () => {
    const { container } = render(<App loadData={() => Promise.reject(new Error("invalid snapshot"))} />);

    expect(await screen.findByText("Operational snapshot unavailable")).toBeInTheDocument();
    const liveRegions = container.querySelectorAll('[aria-live], [role="status"], [role="alert"]');
    expect(liveRegions).toHaveLength(1);
    expect(liveRegions[0]).toHaveAttribute("aria-label", "Snapshot freshness");
  });

  it("retains the last valid snapshot when the next load fails", async () => {
    const firstLoad = () => Promise.resolve(snapshot);
    const { rerender } = render(<App loadData={firstLoad} />);

    expect(await screen.findAllByText("94.4%")).toHaveLength(2);

    rerender(<App loadData={() => Promise.reject(new Error("network down"))} />);

    expect(await screen.findByRole("note", { name: "Refresh details" })).toBeInTheDocument();
    expect(screen.getAllByText("94.4%")).toHaveLength(2);
    const status = screen.getByRole("status", { name: "Snapshot freshness" });
    expect(status).toHaveTextContent("Showing last valid snapshot");
    expect(status).toHaveTextContent("Using saved data after the latest refresh failed.");
    expect(status.querySelector("time")).toHaveAttribute("datetime", snapshot.manifest.generated_at);
  });

  it("loads the default snapshot through the deferred data module", async () => {
    const { loadSnapshot } = await import("../data/loadSnapshot");
    vi.mocked(loadSnapshot).mockResolvedValue(snapshot);

    await expect(loadDefaultSnapshot()).resolves.toBe(snapshot);
    expect(loadSnapshot).toHaveBeenCalledWith(undefined, undefined);
  });
});
