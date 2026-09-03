import { describe, expect, it } from "vitest";

import { groupHourlyAvailability, type ReplayEvent } from "./hourlyAvailability";

const events: ReplayEvent[] = [
  { available: true, equipment_id: "QC-001", event_id: "evt-1", event_timestamp: "2026-09-02T00:00:00Z", state: "ACTIVE", terminal_id: "TM-001" },
  { available: true, equipment_id: "QC-001", event_id: "evt-2", event_timestamp: "2026-09-02T00:05:00Z", state: "ACTIVE", terminal_id: "TM-001" },
  { available: false, equipment_id: "QC-001", event_id: "evt-3", event_timestamp: "2026-09-02T00:10:00Z", state: "UNAVAILABLE", terminal_id: "TM-001" },
  { available: false, equipment_id: "QC-001", event_id: "evt-4", event_timestamp: "2026-09-02T01:00:00Z", state: "MAINTENANCE", terminal_id: "TM-001" },
];

describe("groupHourlyAvailability", () => {
  it("groups events in chronological order and calculates hourly availability", () => {
    expect(groupHourlyAvailability(events)).toEqual([
      { available: 2, label: "00:00", total: 3, value: 2 / 3 },
      { available: 0, label: "01:00", total: 1, value: 0 },
    ]);
  });

  it("returns no points for an empty replay", () => {
    expect(groupHourlyAvailability([])).toEqual([]);
  });
});
