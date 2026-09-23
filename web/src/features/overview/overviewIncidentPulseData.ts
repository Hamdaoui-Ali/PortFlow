import type { IncidentDatasetState, IncidentRecordV1 } from "../../data/schema";
import { incidentSeverityRank } from "../incidents/incidentData";

export const OVERVIEW_INCIDENT_PULSE_LIMIT = 3;

export type OverviewIncidentPulse =
  | { status: "absent" | "empty" | "unavailable" | "malformed" }
  | { status: "ready"; records: IncidentRecordV1[] };

export function deriveOverviewIncidentPulse(
  dataset: IncidentDatasetState | undefined,
): OverviewIncidentPulse {
  if (!dataset) return { status: "absent" };
  if (dataset.status !== "ready") return { status: dataset.status };
  if (dataset.records.length === 0) return { status: "empty" };

  return {
    status: "ready",
    records: [...dataset.records]
      .sort(comparePulsePriority)
      .slice(0, OVERVIEW_INCIDENT_PULSE_LIMIT),
  };
}

function comparePulsePriority(left: IncidentRecordV1, right: IncidentRecordV1): number {
  const openFirst = Number(right.status === "OPEN") - Number(left.status === "OPEN");
  if (openFirst !== 0) return openFirst;

  const severity = incidentSeverityRank[right.severity] - incidentSeverityRank[left.severity];
  if (severity !== 0) return severity;

  const openedAt = Date.parse(right.opened_at) - Date.parse(left.opened_at);
  if (openedAt !== 0) return openedAt;

  return left.incident_id.localeCompare(right.incident_id);
}
