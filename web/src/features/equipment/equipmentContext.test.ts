import { describe, expect, it } from "vitest";

import type { IncidentRecordV1, ReplayEventV1 } from "../../data/schema";
import {
  deriveEquipmentActivity,
  deriveEquipmentIncidents,
} from "./equipmentContext";

const replayEvents: ReplayEventV1[] = [
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-first-at-tie",
    event_timestamp: "2026-09-02T01:00:00Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-duplicate-at-tie",
    event_timestamp: "2026-09-02T01:00:00Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
  {
    available: false,
    equipment_id: "QC-001",
    event_id: "evt-maintenance",
    event_timestamp: "2026-09-02T02:00:00Z",
    state: "MAINTENANCE",
    terminal_id: "TM-001",
  },
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-active-again",
    event_timestamp: "2026-09-02T03:00:00Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
  {
    available: true,
    equipment_id: "QC-002",
    event_id: "evt-other-equipment",
    event_timestamp: "2026-09-02T00:30:00Z",
    state: "ACTIVE",
    terminal_id: "TM-002",
  },
];

const incidents: IncidentRecordV1[] = [
  {
    equipment_id: "QC-001",
    incident_id: "inc-000001",
    opened_at: "2026-09-02T01:00:00Z",
    resolved_at: "2026-09-02T01:30:00Z",
    root_cause: "Hydraulic leak",
    severity: "MAJOR",
    status: "RESOLVED",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-001",
    incident_id: "inc-000002",
    opened_at: "2026-09-02T02:00:00Z",
    resolved_at: null,
    root_cause: "Motor overload",
    severity: "CRITICAL",
    status: "OPEN",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-002",
    incident_id: "inc-000003",
    opened_at: "2026-09-02T03:00:00Z",
    resolved_at: null,
    root_cause: "Power loss",
    severity: "MINOR",
    status: "OPEN",
    terminal_id: "TM-002",
  },
];

describe("deriveEquipmentActivity", () => {
  it("orders matching events, keeps stable ties, and collapses adjacent duplicates", () => {
    const originalEvents = replayEvents.map((event) => ({ ...event }));

    const result = deriveEquipmentActivity(replayEvents, "QC-001");

    expect(result.status).toBe("ready");
    expect(result.events.map((event) => event.event_id)).toEqual([
      "evt-first-at-tie",
      "evt-maintenance",
      "evt-active-again",
    ]);
    expect(replayEvents).toEqual(originalEvents);
  });

  it("distinguishes absent, empty, and non-matching replay data", () => {
    expect(deriveEquipmentActivity(undefined, "QC-001")).toEqual({
      status: "absent",
      events: [],
    });
    expect(deriveEquipmentActivity([], "QC-001")).toEqual({
      status: "empty",
      events: [],
    });
    expect(deriveEquipmentActivity([replayEvents[4]], "QC-001")).toEqual({
      status: "no-match",
      events: [],
    });
  });
});

describe("deriveEquipmentIncidents", () => {
  it("filters to the selected equipment and sorts newest incidents first", () => {
    const originalIncidents = incidents.map((incident) => ({ ...incident }));

    const result = deriveEquipmentIncidents({ status: "ready", records: incidents }, "QC-001");

    expect(result.status).toBe("ready");
    expect(result.records.map((incident) => incident.incident_id)).toEqual([
      "inc-000002",
      "inc-000001",
    ]);
    expect(incidents).toEqual(originalIncidents);
  });

  it("uses incident ids as a deterministic tie breaker", () => {
    const tiedIncidents = incidents.map((incident) => ({
      ...incident,
      opened_at: "2026-09-02T01:00:00Z",
    }));

    const result = deriveEquipmentIncidents({ status: "ready", records: tiedIncidents }, "QC-001");

    expect(result.records.map((incident) => incident.incident_id)).toEqual([
      "inc-000001",
      "inc-000002",
    ]);
  });

  it("preserves source dataset states and distinguishes no matches", () => {
    expect(deriveEquipmentIncidents(undefined, "QC-001")).toEqual({
      status: "absent",
      records: [],
    });
    expect(deriveEquipmentIncidents({ status: "empty" }, "QC-001")).toEqual({
      status: "empty",
      records: [],
    });
    expect(deriveEquipmentIncidents({ status: "unavailable" }, "QC-001")).toEqual({
      status: "unavailable",
      records: [],
    });
    expect(deriveEquipmentIncidents({ status: "malformed" }, "QC-001")).toEqual({
      status: "malformed",
      records: [],
    });
    expect(deriveEquipmentIncidents({ status: "ready", records: [] }, "QC-001")).toEqual({
      status: "empty",
      records: [],
    });
    expect(deriveEquipmentIncidents({ status: "ready", records: incidents }, "QC-999")).toEqual({
      status: "no-match",
      records: [],
    });
  });
});
