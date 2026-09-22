import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";

export type IncidentEquipmentContext =
  | { status: "absent" | "empty" | "unavailable" | "malformed" | "no-match" }
  | { status: "ready"; record: EquipmentRecordV1 };

export function deriveIncidentEquipmentContext(
  dataset: EquipmentDatasetState | undefined,
  equipmentId: string,
): IncidentEquipmentContext {
  if (!dataset) return { status: "absent" };
  if (dataset.status !== "ready") return { status: dataset.status };

  const record = dataset.records.find((candidate) => candidate.equipment_id === equipmentId);
  return record ? { status: "ready", record } : { status: "no-match" };
}
