import { describe, expect, it } from "vitest";

import type { SnapshotV1 } from "../data/schema";
import { deriveSnapshotFilterScope, formatSnapshotPeriod } from "./filterScope";

const snapshot: SnapshotV1 = {
  manifest: {
    datasets: {
      overview: {
        path: "snapshots/demo-v1/overview.json",
        sha256: "13046979b100d92a07ea391dbbe003a3e58333da33916db1bb62666a88c7320d",
      },
    },
    generated_at: "2026-09-02T23:55:02Z",
    quality_status: "PASS",
    record_counts: { telemetry: 1 },
    schema_version: 1,
    snapshot_id: "demo-v1",
    source_period_end: "2026-09-02T23:55:00Z",
    source_period_start: "2026-09-02T00:00:00Z",
  },
  overview: {
    availability: {
      available_intervals: 1,
      scheduled_intervals: 1,
      value: 1,
    },
    schema_version: 1,
    terminal_id: "TM-001",
  },
};

describe("snapshot filter scope", () => {
  it("derives the known terminal and UTC source period", () => {
    expect(deriveSnapshotFilterScope(snapshot)).toEqual({
      terminalLabel: "Casablanca Terminal",
      periodLabel: "02 Sept 2026, 00:00–23:55 UTC",
    });
  });

  it("falls back to the validated terminal ID", () => {
    expect(deriveSnapshotFilterScope({
      ...snapshot,
      overview: { ...snapshot.overview, terminal_id: "TM-999" },
    }).terminalLabel).toBe("TM-999");
  });

  it("formats cross-day periods deterministically in UTC", () => {
    expect(formatSnapshotPeriod("2026-09-01T23:30:00Z", "2026-09-02T01:15:00Z"))
      .toBe("01 Sept 2026, 23:30 – 02 Sept 2026, 01:15 UTC");
  });
});
