import { describe, expect, it } from "vitest";

import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { deriveOverviewEquipmentPulse } from "./overviewEquipmentPulse";

const baseRecord: EquipmentRecordV1 = {
  alarm_count: 0,
  availability: 0.9444444444444444,
  available: true,
  current_state: "ACTIVE",
  downtime_minutes: 20,
  equipment_id: "QC-001",
  mtbf_hours: 24,
  mttr_minutes: 30,
  terminal_id: "TM-001",
  utilization: 0.7426470588235294,
};

function record(overrides: Partial<EquipmentRecordV1>): EquipmentRecordV1 {
  return { ...baseRecord, ...overrides };
}

describe("deriveOverviewEquipmentPulse", () => {
  it("keeps an omitted equipment dataset absent", () => {
    expect(deriveOverviewEquipmentPulse(undefined)).toEqual({ status: "absent" });
  });

  it.each(["empty", "unavailable", "malformed"] as const)(
    "preserves the %s dataset state",
    (status) => {
      expect(deriveOverviewEquipmentPulse({ status })).toEqual({ status });
    },
  );

  it("reports a ready dataset without records as empty", () => {
    expect(deriveOverviewEquipmentPulse({ status: "ready", records: [] })).toEqual({
      status: "empty",
    });
  });

  it("ranks unavailable and lower-availability records first", () => {
    const records = [
      record({ equipment_id: "QC-003", availability: null, downtime_minutes: 900 }),
      record({ equipment_id: "QC-004", available: false, availability: 0.9, downtime_minutes: 10 }),
      record({ equipment_id: "QC-002", availability: 0.7, downtime_minutes: 45 }),
      record({ equipment_id: "QC-001", availability: 0.7, downtime_minutes: 90 }),
      record({ equipment_id: "QC-000", availability: 0.7, downtime_minutes: 90 }),
    ];

    const result = deriveOverviewEquipmentPulse({ status: "ready", records });

    expect(result.status).toBe("ready");
    if (result.status !== "ready") return;
    expect(result.records.map(({ equipment_id }) => equipment_id)).toEqual([
      "QC-004",
      "QC-000",
      "QC-001",
    ]);
  });

  it("puts null numeric values after comparable values", () => {
    const records = [
      record({ equipment_id: "QC-NULL-AVAIL", availability: null, downtime_minutes: 900 }),
      record({ equipment_id: "QC-NULL-DOWNTIME", availability: 0.5, downtime_minutes: null }),
      record({ equipment_id: "QC-NUMERIC", availability: 0.5, downtime_minutes: 10 }),
    ];

    const result = deriveOverviewEquipmentPulse({ status: "ready", records });

    expect(result.status).toBe("ready");
    if (result.status !== "ready") return;
    expect(result.records.map(({ equipment_id }) => equipment_id)).toEqual([
      "QC-NUMERIC",
      "QC-NULL-DOWNTIME",
      "QC-NULL-AVAIL",
    ]);
  });

  it("does not mutate the source array or its records", () => {
    const records = [
      record({ equipment_id: "QC-002", availability: 0.7 }),
      record({ equipment_id: "QC-001", availability: 0.6 }),
    ];
    const dataset: EquipmentDatasetState = { status: "ready", records };
    const before = structuredClone(dataset);

    const result = deriveOverviewEquipmentPulse(dataset);

    expect(dataset).toEqual(before);
    expect(dataset.records).toBe(records);
    expect(dataset.records[0]).toBe(records[0]);
    expect(result.status).toBe("ready");
    if (result.status !== "ready") return;
    expect(result.records[0]).toBe(records[1]);
  });
});
