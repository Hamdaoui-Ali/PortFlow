import { describe, expect, it } from "vitest";

import type { OverviewV1, ReplayEventV1 } from "../../data/schema";
import { createReplayState, replayReducer } from "./replayMachine";
import {
  deriveReplayViewModel,
  formatReplayEvent,
  formatReplayTimestamp,
} from "./replayPresentation";

const overview: OverviewV1 = {
  active_incidents: 1,
  active_intervals: 202,
  availability: { available_intervals: 272, scheduled_intervals: 288, value: 0.9444444444 },
  available_intervals: 272,
  average_dwell_minutes: 63.75,
  critical_alarms: 1,
  mtbf_hours: 24,
  mttr_minutes: 30,
  operating_hours: 24,
  qualifying_failure_count: 1,
  repair_minutes: 30,
  resolved_incident_count: 1,
  scheduled_intervals: 288,
  schema_version: 1,
  source_period_end: "2026-09-02T23:55:00Z",
  source_period_start: "2026-09-02T00:00:00Z",
  terminal_id: "TM-001",
  throughput: 4,
  utilization: 0.7426,
};

const events: ReplayEventV1[] = [
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-1",
    event_timestamp: "2026-09-02T00:00:00Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
  {
    available: false,
    equipment_id: "QC-001",
    event_id: "evt-2",
    event_timestamp: "2026-09-02T00:05:00Z",
    state: "WARNING",
    terminal_id: "TM-001",
  },
  {
    available: false,
    equipment_id: "QC-001",
    event_id: "evt-3",
    event_timestamp: "2026-09-02T00:10:00Z",
    state: "UNAVAILABLE",
    terminal_id: "TM-001",
  },
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-4",
    event_timestamp: "2026-09-02T00:15:00Z",
    state: "IDLE",
    terminal_id: "TM-001",
  },
];

describe("replayPresentation", () => {
  it("derives the current event and source KPI after starting replay", () => {
    const state = replayReducer(createReplayState(events), { type: "START" });
    const model = deriveReplayViewModel(state, overview);

    expect(model.currentEvent?.event_id).toBe("evt-1");
    expect(model.progressLabel).toBe("1 of 4 events");
    expect(model.availabilityLabel).toBe("Available");
    expect(model.currentStateLabel).toBe("ACTIVE");
    expect(model.sourceAvailabilityLabel).toBe("94.4%");
  });

  it("uses unavailable labels before and during unavailable equipment states", () => {
    const initial = deriveReplayViewModel(createReplayState(events), overview);
    let state = replayReducer(createReplayState(events), { type: "START" });
    state = replayReducer(state, { type: "TICK", deltaMs: 600_000 });
    const unavailable = deriveReplayViewModel(state, overview);

    expect(initial.currentEvent).toBeNull();
    expect(initial.availabilityLabel).toBe("Unavailable");
    expect(unavailable.currentEvent?.event_id).toBe("evt-3");
    expect(unavailable.availabilityLabel).toBe("Unavailable");
    expect(unavailable.currentStateLabel).toBe("UNAVAILABLE");
  });

  it("formats complete progress and event labels", () => {
    let state = replayReducer(createReplayState(events), { type: "START" });
    state = replayReducer(state, { type: "TICK", deltaMs: 900_000 });
    const model = deriveReplayViewModel(state, overview);

    expect(model.progressLabel).toBe("4 of 4 events");
    expect(model.latestEventLabel).toContain("evt-4");
    expect(model.latestEventLabel).toContain("QC-001");
    expect(model.latestEventLabel).toContain("TM-001");
    expect(model.latestEventLabel).toContain("IDLE");
  });

  it("formats replay timestamps in UTC", () => {
    expect(formatReplayTimestamp("2026-09-02T00:05:00Z")).toBe("Sep 2, 2026, 12:05 AM UTC");
  });

  it("formats all event identity fields", () => {
    expect(formatReplayEvent(events[1])).toBe("evt-2 · QC-001 · TM-001 · WARNING");
  });
});
