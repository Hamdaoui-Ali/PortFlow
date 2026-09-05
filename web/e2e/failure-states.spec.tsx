import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/app/App";
import { snapshotCache } from "../src/data/cache";
import { SnapshotLoadError } from "../src/data/errors";
import { loadSnapshot, type SnapshotFetch } from "../src/data/loadSnapshot";
import type { ManifestV1, OverviewV1, SnapshotV1 } from "../src/data/schema";
import "../src/styles.css";

type Fixture = unknown | Error;

const overview: OverviewV1 = {
  availability: { available_intervals: 9, scheduled_intervals: 10, value: 0.9 },
  schema_version: 1,
  terminal_id: "TM-001",
  throughput: 120,
};

const quality = {
  bronze_rows: 10,
  silver_rows: 10,
  quarantine_rows: 0,
  reason_counts: { late: 0 },
  dbt_test_status: "PASS" as const,
};

function manifest(overrides: Partial<ManifestV1> = {}): ManifestV1 {
  return {
    datasets: {
      overview: { path: "snapshots/test/overview.json", sha256: "1".repeat(64) },
      equipment: { path: "snapshots/test/equipment.json", sha256: "2".repeat(64) },
      incidents: { path: "snapshots/test/incidents.json", sha256: "3".repeat(64) },
      event_replay: { path: "snapshots/test/event-replay.json", sha256: "4".repeat(64) },
      quality: { path: "snapshots/test/quality.json", sha256: "5".repeat(64) },
    },
    generated_at: "2026-09-05T00:00:00Z",
    quality_status: "PASS",
    record_counts: { telemetry: 10, equipment: 1, incidents: 1, event_replay: 1, quality: 1 },
    schema_version: 1,
    snapshot_id: "test-snapshot",
    source_period_end: "2026-09-04T23:00:00Z",
    source_period_start: "2026-09-04T00:00:00Z",
    ...overrides,
  };
}

const equipment = [{
  alarm_count: 0, availability: 0.9, available: true, current_state: "ACTIVE",
  downtime_minutes: 10, equipment_id: "QC-001", mtbf_hours: 24, mttr_minutes: 30,
  terminal_id: "TM-001", utilization: 0.7,
}];

const incidents = [{
  equipment_id: "QC-001", incident_id: "inc-000001", opened_at: "2026-09-04T03:00:00Z",
  resolved_at: "2026-09-04T03:30:00Z", root_cause: "Hydraulic leak", severity: "MAJOR" as const,
  status: "RESOLVED" as const, terminal_id: "TM-001",
}];

const replay = [{
  available: true, equipment_id: "QC-001", event_id: "evt-000001",
  event_timestamp: "2026-09-04T03:00:00Z", state: "ACTIVE", terminal_id: "TM-001",
}];

function response(payload: Fixture, ok = true): Response {
  if (payload instanceof Error) throw payload;
  return new Response(JSON.stringify(payload), { status: ok ? 200 : 503 });
}

function createFetcher(fixtures: Record<string, Fixture>): SnapshotFetch {
  return async (input) => {
    const suffix = String(input).replace(/^.*\/data\//, "");
    const fixture = fixtures[suffix];
    if (fixture === undefined) throw new Error(`Missing fixture for ${suffix}`);
    return response(fixture);
  };
}

function fullFixtures(nextManifest: unknown = manifest(), nextOverview: unknown = overview) {
  return {
    "manifest.json": nextManifest,
    "snapshots/test/overview.json": nextOverview,
    "snapshots/test/equipment.json": equipment,
    "snapshots/test/incidents.json": incidents,
    "snapshots/test/event-replay.json": replay,
    "snapshots/test/quality.json": quality,
  };
}

function loadThroughApp(fetcher: SnapshotFetch, failures: SnapshotLoadError[] = []) {
  return () => loadSnapshot(fetcher, "/").catch((error: unknown) => {
    if (error instanceof SnapshotLoadError) failures.push(error);
    throw error;
  });
}

afterEach(() => {
  cleanup();
  window.history.replaceState({}, "", "/");
  snapshotCache.clear();
});

describe("frontend failure-state fixtures", () => {
  it("reports an unavailable manifest without Overview KPIs", async () => {
    const failures: SnapshotLoadError[] = [];
    const fetcher = createFetcher({ "manifest.json": new Error("network down") });
    render(<App loadData={loadThroughApp(fetcher, failures)} />);

    expect(await screen.findByRole("heading", { name: "Operational snapshot unavailable" })).toBeInTheDocument();
    expect(failures[0]?.kind).toBe("unavailable");
    expect(screen.queryByRole("region", { name: "Overview KPIs" })).not.toBeInTheDocument();
  });

  it("reports a malformed manifest", async () => {
    const failures: SnapshotLoadError[] = [];
    render(<App loadData={loadThroughApp(createFetcher({ "manifest.json": {} }), failures)} />);

    expect(await screen.findByRole("heading", { name: "Published snapshot malformed" })).toBeInTheDocument();
    expect(failures[0]?.kind).toBe("malformed");
  });

  it("reports an empty overview", async () => {
    const failures: SnapshotLoadError[] = [];
    const emptyOverview = { ...overview, availability: { available_intervals: 0, scheduled_intervals: 0, value: null } };
    render(<App loadData={loadThroughApp(createFetcher(fullFixtures(manifest(), emptyOverview)), failures)} />);

    expect(await screen.findByRole("heading", { name: "Published snapshot empty" })).toBeInTheDocument();
    expect(failures[0]?.kind).toBe("empty");
  });

  it("keeps Overview usable when the optional equipment entry is missing", async () => {
    const fixtures = fullFixtures();
    const nextManifest = manifest({ datasets: { ...manifest().datasets, equipment: undefined } });
    render(<App loadData={loadThroughApp(createFetcher({ ...fixtures, "manifest.json": nextManifest }))} />);

    expect(await screen.findByRole("region", { name: "Overview KPIs" })).toBeInTheDocument();
    const snapshot = await loadSnapshot(createFetcher({ ...fixtures, "manifest.json": nextManifest }), "/");
    expect(snapshot.equipment).toEqual({ status: "absent" });
  });

  it("marks an optional incidents payload with an unexpected field malformed", async () => {
    const fixtures = fullFixtures();
    const malformedIncidents = [{ ...incidents[0], unexpected: true }];
    const fetcher = createFetcher({ ...fixtures, "snapshots/test/incidents.json": malformedIncidents });
    render(<App loadData={loadThroughApp(fetcher)} />);

    expect(await screen.findByRole("region", { name: "Overview KPIs" })).toBeInTheDocument();
    expect((await loadSnapshot(fetcher, "/")).incidents).toEqual({ status: "malformed" });
  });

  it("omits a malformed optional replay event while keeping Overview usable", async () => {
    const malformedReplay = [{ ...replay[0], unexpected: true }];
    const fetcher = createFetcher({ ...fullFixtures(), "snapshots/test/event-replay.json": malformedReplay });
    render(<App loadData={loadThroughApp(fetcher)} />);

    expect(await screen.findByRole("region", { name: "Overview KPIs" })).toBeInTheDocument();
    expect((await loadSnapshot(fetcher, "/")).event_replay).toBeUndefined();
  });

  it("shows stale data health for a manifest older than the stale threshold", async () => {
    window.history.replaceState({}, "", "/#data-health");
    const staleManifest = manifest({ generated_at: "2026-09-03T00:00:00Z" });
    render(<App loadData={loadThroughApp(createFetcher(fullFixtures(staleManifest)))} />);

    expect(await screen.findByText("Data is healthy but stale.")).toBeInTheDocument();
  });

  it("shows the last valid cached snapshot after the next load fails", async () => {
    const cached: SnapshotV1 = await loadSnapshot(createFetcher(fullFixtures()), "/");
    snapshotCache.set(cached);
    const failures: SnapshotLoadError[] = [];
    render(<App loadData={loadThroughApp(createFetcher({ "manifest.json": new Error("network down") }), failures)} />);

    expect(await screen.findByRole("heading", { name: "Showing last valid snapshot" })).toBeInTheDocument();
    expect(screen.getByText("120 moves")).toBeInTheDocument();
    expect(failures[0]?.kind).toBe("unavailable");
  });

  it("renders a valid replacement after a failure instead of the cached KPI", async () => {
    const cached = await loadSnapshot(createFetcher(fullFixtures()), "/");
    snapshotCache.set(cached);
    const failingLoad = loadThroughApp(createFetcher({ "manifest.json": new Error("network down") }));
    const { rerender } = render(<App loadData={failingLoad} />);
    expect(await screen.findByRole("heading", { name: "Showing last valid snapshot" })).toBeInTheDocument();

    const replacement = { ...overview, throughput: 987 };
    rerender(<App loadData={loadThroughApp(createFetcher(fullFixtures(manifest({ snapshot_id: "replacement" }), replacement)))} />);
    expect(await screen.findByText("987 moves")).toBeInTheDocument();
    expect(screen.queryByText("120 moves")).not.toBeInTheDocument();
  });
});
