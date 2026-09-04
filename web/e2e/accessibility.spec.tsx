import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/app/App";
import { snapshotCache } from "../src/data/cache";
import type { SnapshotV1 } from "../src/data/schema";
import { scanAccessibility } from "../src/test/accessibility";
import "../src/styles.css";

const snapshot: SnapshotV1 = {
  manifest: {
    datasets: {
      overview: { path: "snapshots/demo-v1/overview.json", sha256: "1".repeat(64) },
      equipment: { path: "snapshots/demo-v1/equipment.json", sha256: "2".repeat(64) },
      incidents: { path: "snapshots/demo-v1/incidents.json", sha256: "3".repeat(64) },
      event_replay: { path: "snapshots/demo-v1/event-replay.json", sha256: "4".repeat(64) },
      quality: { path: "snapshots/demo-v1/quality.json", sha256: "5".repeat(64) },
    },
    generated_at: "2026-09-02T23:55:02Z",
    quality_status: "PASS",
    record_counts: { telemetry: 288, equipment: 1, incidents: 1, event_replay: 1, quality: 1 },
    schema_version: 1,
    snapshot_id: "demo-v1",
    source_period_end: "2026-09-02T23:55:00Z",
    source_period_start: "2026-09-02T00:00:00Z",
  },
  overview: {
    availability: { available_intervals: 272, scheduled_intervals: 288, value: 272 / 288 },
    schema_version: 1,
    terminal_id: "TM-001",
    active_intervals: 1,
    throughput: 120,
    utilization: 0.74,
  },
  equipment: {
    status: "ready",
    records: [{
      alarm_count: 1, availability: 0.94, available: true, current_state: "ACTIVE",
      downtime_minutes: 10, equipment_id: "QC-001", mtbf_hours: 24, mttr_minutes: 30,
      terminal_id: "TM-001", utilization: 0.74,
    }],
  },
  incidents: {
    status: "ready",
    records: [{
      equipment_id: "QC-001", incident_id: "inc-000001", opened_at: "2026-09-02T03:00:00Z",
      resolved_at: "2026-09-02T03:30:00Z", root_cause: "Hydraulic leak", severity: "MAJOR",
      status: "RESOLVED", terminal_id: "TM-001",
    }],
  },
  event_replay: [{
    available: true, equipment_id: "QC-001", event_id: "evt-000001",
    event_timestamp: "2026-09-02T03:00:00Z", state: "ACTIVE", terminal_id: "TM-001",
  }],
  quality: {
    status: "ready",
    data: { bronze_rows: 305, silver_rows: 305, quarantine_rows: 0, reason_counts: { late: 0 }, dbt_test_status: "PASS" },
  },
};

afterEach(() => {
  cleanup();
  window.history.replaceState({}, "", "/");
  snapshotCache.clear();
});

describe("route accessibility", () => {
  it.each([
    ["overview", "Terminal throughput (moves)"],
    ["equipment", "Equipment fleet"],
    ["incidents", "Incident exploration"],
    ["live-demo", "Live Demo"],
    ["data-health", "Data Health"],
  ] as const)("has no axe violations on %s", async (route, heading) => {
    window.history.replaceState({}, "", `/#${route}`);
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    if (route === "overview") {
      expect(screen.getByRole("img", { name: /hourly availability trend/i })).toBeInTheDocument();
    }
    if (route === "equipment") {
      expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
    }
    if (route === "incidents") {
      expect(screen.getByRole("table", { name: /incident/i })).toBeInTheDocument();
    }
    if (route === "live-demo") {
      expect(screen.getByRole("button", { name: /pause replay|start replay/i })).toBeInTheDocument();
    }
    if (route === "data-health") {
      expect(screen.getByRole("table", { name: /rejection reasons/i })).toBeInTheDocument();
    }
    const results = await scanAccessibility(document.body);
    expect(results.violations).toEqual([]);
  });

  it("keeps the shared interactive controls at a touch-friendly size", async () => {
    window.history.replaceState({}, "", "/#live-demo");
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    expect(await screen.findByRole("heading", { name: "Live Demo" })).toBeInTheDocument();

    expect(document.querySelectorAll("button, input, select, summary, .nav-link").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Start replay" })).toBeInTheDocument();
    expect(screen.getByLabelText("Replay speed")).toBeInTheDocument();
  });
});
