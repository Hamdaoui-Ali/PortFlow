import type { IncidentRecordV1 } from "../data/schema";

export const incidentRecords: IncidentRecordV1[] = [
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

export function makeIncidentRecord(overrides: Partial<IncidentRecordV1> = {}): IncidentRecordV1 {
  return { ...incidentRecords[1], ...overrides };
}
