import { describe, expect, it } from "vitest";

import type { IncidentDatasetState, IncidentRecordV1 } from "../../data/schema";
import { deriveOverviewIncidentPulse } from "./overviewIncidentPulseData";

const records: IncidentRecordV1[] = [
  {
    equipment_id: "QC-001",
    incident_id: "inc-000001",
    opened_at: "2026-09-02T03:00:00Z",
    resolved_at: null,
    root_cause: "Hydraulic leak",
    severity: "MAJOR",
    status: "OPEN",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-002",
    incident_id: "inc-000002",
    opened_at: "2026-09-02T04:00:00Z",
    resolved_at: null,
    root_cause: "Motor overload",
    severity: "CRITICAL",
    status: "OPEN",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-003",
    incident_id: "inc-000003",
    opened_at: "2026-09-02T23:00:00Z",
    resolved_at: "2026-09-03T00:00:00Z",
    root_cause: "Sensor drift",
    severity: "CRITICAL",
    status: "RESOLVED",
    terminal_id: "TM-002",
  },
];

describe("deriveOverviewIncidentPulse", () => {
  it("ranks open and severe incidents before older resolved records and limits the list", () => {
    const extraRecord = { ...records[2], incident_id: "inc-000006" };
    const view = deriveOverviewIncidentPulse({ status: "ready", records: [...records, extraRecord] });

    expect(view).toEqual({
      status: "ready",
      records: [records[1], records[0], records[2]],
    });
  });

  it("uses the opening instant and incident id as deterministic tie-breakers", () => {
    const offsetRecord = {
      ...records[1],
      incident_id: "inc-000004",
      opened_at: "2026-09-02T00:30:00-02:00",
    };
    const sameInstantDifferentId = {
      ...records[1],
      incident_id: "inc-000005",
      opened_at: "2026-09-02T02:30:00Z",
    };
    const view = deriveOverviewIncidentPulse({
      status: "ready",
      records: [offsetRecord, sameInstantDifferentId, records[1]],
    });

    expect(view.status).toBe("ready");
    if (view.status === "ready") {
      expect(view.records.map((record) => record.incident_id)).toEqual([
        "inc-000002",
        "inc-000004",
        "inc-000005",
      ]);
    }
  });

  it.each([
    [undefined, "absent"],
    [{ status: "empty" }, "empty"],
    [{ status: "unavailable" }, "unavailable"],
    [{ status: "malformed" }, "malformed"],
  ] as const)("preserves the %s dataset state", (dataset, status) => {
    expect(deriveOverviewIncidentPulse(dataset as IncidentDatasetState | undefined)).toEqual({ status });
  });

  it("treats a ready empty dataset as empty", () => {
    expect(deriveOverviewIncidentPulse({ status: "ready", records: [] })).toEqual({ status: "empty" });
  });
});
