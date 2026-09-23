import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";

export const OVERVIEW_EQUIPMENT_PULSE_LIMIT = 3;

export type OverviewEquipmentPulse =
  | { status: "absent" | "empty" | "unavailable" | "malformed" }
  | { status: "ready"; records: EquipmentRecordV1[] };

export function deriveOverviewEquipmentPulse(
  dataset: EquipmentDatasetState | undefined,
): OverviewEquipmentPulse {
  if (!dataset) return { status: "absent" };
  if (dataset.status !== "ready") return { status: dataset.status };
  if (dataset.records.length === 0) return { status: "empty" };

  const records = [...dataset.records]
    .sort(comparePulsePriority)
    .slice(0, OVERVIEW_EQUIPMENT_PULSE_LIMIT);
  return { status: "ready", records };
}

function comparePulsePriority(left: EquipmentRecordV1, right: EquipmentRecordV1): number {
  const availabilityState = Number(left.available) - Number(right.available);
  if (availabilityState !== 0) return availabilityState;

  const availability = compareNullable(left.availability, right.availability, (a, b) => a - b);
  if (availability !== 0) return availability;

  const downtime = compareNullable(left.downtime_minutes, right.downtime_minutes, (a, b) => b - a);
  if (downtime !== 0) return downtime;

  return compareText(left.equipment_id, right.equipment_id);
}

function compareNullable(
  left: number | null,
  right: number | null,
  compareNumbers: (left: number, right: number) => number,
): number {
  if (left === right) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return compareNumbers(left, right);
}

function compareText(left: string, right: string): number {
  if (left === right) return 0;
  return left < right ? -1 : 1;
}
