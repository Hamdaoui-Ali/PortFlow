import { describe, expect, it } from "vitest";

import type { IncidentRecordV1 } from "../../data/schema";
import {
  filterIncidents,
  getIncidentMetrics,
  getIncidentTrend,
  getRootCauseCounts,
  sortIncidents,
} from "./incidentData";

const records: IncidentRecordV1[] = [
  {
    equipment_id: "QC-001",
    incident_id: "inc-000001",
    opened_at: "2026-09-02T03:00:00Z",
    resolved_at: "2026-09-02T03:30:00Z",
    root_cause: "Hydraulic leak",
    severity: "MAJOR",
    status: "RESOLVED",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-002",
    incident_id: "inc-000002",
    opened_at: "2026-09-02T20:00:00Z",
    resolved_at: null,
    root_cause: "Motor overload",
    severity: "CRITICAL",
    status: "OPEN",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-003",
    incident_id: "inc-000003",
    opened_at: "2026-09-01T12:00:00Z",
    resolved_at: "2026-09-01T14:00:00Z",
    root_cause: "Hydraulic leak",
    severity: "MINOR",
    status: "RESOLVED",
    terminal_id: "TM-002",
  },
];

describe("incident data helpers", () => {
  it("filters by incident, equipment, terminal, and severity", () => {
    expect(filterIncidents(records, "QC-00", "TM-001", "CRITICAL").map((record) => record.incident_id))
      .toEqual(["inc-000002"]);
  });

  it("sorts newest incidents first and keeps null durations last", () => {
    expect(sortIncidents(records, "opened_at", "desc").map((record) => record.incident_id))
      .toEqual(["inc-000002", "inc-000001", "inc-000003"]);
    expect(sortIncidents(records, "duration_minutes", "asc").map((record) => record.incident_id))
      .toEqual(["inc-000001", "inc-000003", "inc-000002"]);
  });

  it("derives counts, open incidents, and average resolved duration", () => {
    expect(getIncidentMetrics(records)).toEqual({
      averageResolutionMinutes: 75,
      openCount: 1,
      totalCount: 3,
    });
  });

  it("groups incident trends by UTC day", () => {
    expect(getIncidentTrend(records)).toEqual([
      { count: 1, date: "2026-09-01" },
      { count: 2, date: "2026-09-02" },
    ]);
  });

  it("groups recurring root causes with deterministic counts", () => {
    expect(getRootCauseCounts(records)).toEqual([
      { count: 2, rootCause: "Hydraulic leak" },
      { count: 1, rootCause: "Motor overload" },
    ]);
  });
});
