import type {
  IncidentDatasetState,
  IncidentRecordV1,
  ReplayEventV1,
} from "../../data/schema";

export type EquipmentActivityStatus = "absent" | "empty" | "no-match" | "ready";

export interface EquipmentActivityView {
  status: EquipmentActivityStatus;
  events: ReplayEventV1[];
}

export type EquipmentIncidentStatus =
  | "absent"
  | "empty"
  | "unavailable"
  | "malformed"
  | "no-match"
  | "ready";

export interface EquipmentIncidentView {
  status: EquipmentIncidentStatus;
  records: IncidentRecordV1[];
}

interface IndexedReplayEvent {
  event: ReplayEventV1;
  index: number;
}

export function deriveEquipmentActivity(
  events: ReplayEventV1[] | undefined,
  equipmentId: string,
): EquipmentActivityView {
  if (events === undefined) return { status: "absent", events: [] };
  if (events.length === 0) return { status: "empty", events: [] };

  const matching = events.reduce<IndexedReplayEvent[]>((result, event, index) => {
    if (event.equipment_id === equipmentId) result.push({ event, index });
    return result;
  }, []);

  if (matching.length === 0) return { status: "no-match", events: [] };

  const ordered = [...matching].sort((left, right) => {
    const timestampOrder = Date.parse(left.event.event_timestamp) - Date.parse(right.event.event_timestamp);
    return timestampOrder || left.index - right.index;
  });

  const eventsByState: ReplayEventV1[] = [];
  for (const { event } of ordered) {
    const previous = eventsByState.at(-1);
    if (previous?.state === event.state && previous.available === event.available) continue;
    eventsByState.push(event);
  }

  return { status: "ready", events: eventsByState };
}

export function deriveEquipmentIncidents(
  dataset: IncidentDatasetState | undefined,
  equipmentId: string,
): EquipmentIncidentView {
  if (dataset === undefined) return { status: "absent", records: [] };
  if (dataset.status !== "ready") return { status: dataset.status, records: [] };
  if (dataset.records.length === 0) return { status: "empty", records: [] };

  const matching = dataset.records.filter((record) => record.equipment_id === equipmentId);
  if (matching.length === 0) return { status: "no-match", records: [] };

  const records = [...matching].sort((left, right) => {
    const openedAtOrder = Date.parse(right.opened_at) - Date.parse(left.opened_at);
    return openedAtOrder || left.incident_id.localeCompare(right.incident_id);
  });

  return { status: "ready", records };
}
