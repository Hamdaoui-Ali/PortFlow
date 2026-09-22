import { describe, expect, it } from "vitest";

import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { deriveIncidentEquipmentContext } from "./incidentContext";

const equipmentRecord: EquipmentRecordV1 = {
  alarm_count: 3,
  availability: 0.9444444444444444,
  available: true,
  current_state: "ACTIVE",
  downtime_minutes: 80,
  equipment_id: "QC-001",
  mtbf_hours: 24,
  mttr_minutes: 30,
  terminal_id: "TM-001",
  utilization: 0.7426470588235294,
};

const readyDataset: EquipmentDatasetState = {
  status: "ready",
  records: [equipmentRecord],
};

describe("deriveIncidentEquipmentContext", () => {
  it("keeps an omitted equipment dataset absent", () => {
    expect(deriveIncidentEquipmentContext(undefined, "QC-001")).toEqual({ status: "absent" });
  });

  it.each(["empty", "unavailable", "malformed"] as const)(
    "preserves the %s dataset state",
    (status) => {
      expect(deriveIncidentEquipmentContext({ status }, "QC-001")).toEqual({ status });
    },
  );

  it("reports a ready dataset without the affected equipment", () => {
    expect(deriveIncidentEquipmentContext(readyDataset, "QC-999")).toEqual({ status: "no-match" });
  });

  it("returns the matching equipment record", () => {
    expect(deriveIncidentEquipmentContext(readyDataset, "QC-001")).toEqual({
      status: "ready",
      record: equipmentRecord,
    });
  });

  it("does not mutate the dataset or record", () => {
    const records = [equipmentRecord];
    const dataset: EquipmentDatasetState = { status: "ready", records };
    const before = structuredClone(dataset);

    deriveIncidentEquipmentContext(dataset, "QC-001");

    expect(dataset).toEqual(before);
    expect(dataset.records).toBe(records);
    expect(dataset.records[0]).toBe(equipmentRecord);
  });
});
