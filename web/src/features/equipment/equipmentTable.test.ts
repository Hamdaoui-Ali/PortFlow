import { describe, expect, it } from "vitest";
import type { EquipmentRecordV1 } from "../../data/schema";
import { filterEquipment, sortEquipment } from "./equipmentTableData";

const records: EquipmentRecordV1[] = [
  {
    alarm_count: 2,
    availability: 0.94,
    available: true,
    current_state: "ACTIVE",
    downtime_minutes: 12,
    equipment_id: "QC-001",
    mtbf_hours: 120,
    mttr_minutes: 30,
    terminal_id: "TM-001",
    utilization: 0.8,
  },
  {
    alarm_count: 1,
    availability: 0.7,
    available: false,
    current_state: "MAINTENANCE",
    downtime_minutes: 45,
    equipment_id: "QC-002",
    mtbf_hours: 90,
    mttr_minutes: 20,
    terminal_id: "TM-001",
    utilization: 0.6,
  },
  {
    alarm_count: 1,
    availability: 0.7,
    available: true,
    current_state: "ACTIVE",
    downtime_minutes: 5,
    equipment_id: "QC-003",
    mtbf_hours: 90,
    mttr_minutes: 20,
    terminal_id: "TM-002",
    utilization: 0.9,
  },
];

describe("filterEquipment", () => {
  it("matches equipment IDs case-insensitively and applies terminal filtering", () => {
    expect(filterEquipment(records, "qc-00", "TM-001")).toEqual([records[0], records[1]]);
  });

  it("treats blank search and all terminals as no filters", () => {
    expect(filterEquipment(records, "  ", "all")).toEqual(records);
  });
});

describe("sortEquipment", () => {
  it("sorts numeric columns in ascending and descending order", () => {
    expect(sortEquipment(records, "availability", "asc").map((row) => row.equipment_id))
      .toEqual(["QC-002", "QC-003", "QC-001"]);
    expect(sortEquipment(records, "availability", "desc").map((row) => row.equipment_id))
      .toEqual(["QC-001", "QC-002", "QC-003"]);
  });

  it("preserves input order for stable ties", () => {
    expect(sortEquipment(records, "mtbf_hours", "asc").map((row) => row.equipment_id))
      .toEqual(["QC-002", "QC-003", "QC-001"]);
  });

  it("does not mutate the source array", () => {
    const original = [...records];
    sortEquipment(records, "downtime_minutes", "desc");
    expect(records).toEqual(original);
  });
});
