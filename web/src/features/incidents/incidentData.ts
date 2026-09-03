import type { IncidentRecordV1 } from "../../data/schema";

export type IncidentSeverity = "all" | "MINOR" | "MAJOR" | "CRITICAL";
export type IncidentSortColumn = "incident_id" | "opened_at" | "severity" | "status" | "duration_minutes";
export type SortDirection = "asc" | "desc";

const severityRank: Record<Exclude<IncidentSeverity, "all">, number> = {
  MINOR: 1,
  MAJOR: 2,
  CRITICAL: 3,
};

export function incidentDurationMinutes(record: IncidentRecordV1): number | null {
  if (!record.resolved_at) return null;
  return (Date.parse(record.resolved_at) - Date.parse(record.opened_at)) / 60_000;
}

export function filterIncidents(
  records: IncidentRecordV1[],
  query: string,
  terminal: string,
  severity: IncidentSeverity,
): IncidentRecordV1[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return records.filter((record) => {
    const searchable = `${record.incident_id} ${record.equipment_id} ${record.root_cause}`.toLocaleLowerCase();
    const matchesQuery = !normalizedQuery || searchable.includes(normalizedQuery);
    const matchesTerminal = !terminal || terminal === "all" || record.terminal_id === terminal;
    const matchesSeverity = severity === "all" || record.severity === severity;
    return matchesQuery && matchesTerminal && matchesSeverity;
  });
}

export function sortIncidents(
  records: IncidentRecordV1[],
  column: IncidentSortColumn,
  direction: SortDirection,
): IncidentRecordV1[] {
  return records
    .map((record, index) => ({ record, index }))
    .sort((left, right) => {
      const leftValue = column === "duration_minutes"
        ? incidentDurationMinutes(left.record)
        : column === "severity" ? severityRank[left.record.severity] : left.record[column];
      const rightValue = column === "duration_minutes"
        ? incidentDurationMinutes(right.record)
        : column === "severity" ? severityRank[right.record.severity] : right.record[column];
      if (leftValue === rightValue) return left.index - right.index;
      if (leftValue === null) return 1;
      if (rightValue === null) return -1;
      const comparison = column === "opened_at"
        ? Date.parse(String(leftValue)) - Date.parse(String(rightValue))
        : typeof leftValue === "number" && typeof rightValue === "number"
          ? leftValue - rightValue
          : String(leftValue).localeCompare(String(rightValue));
      return direction === "asc" ? comparison : -comparison;
    })
    .map(({ record }) => record);
}

export function getIncidentMetrics(records: IncidentRecordV1[]) {
  const resolved = records.filter((record) => incidentDurationMinutes(record) !== null);
  const totalDuration = resolved.reduce((sum, record) => sum + (incidentDurationMinutes(record) ?? 0), 0);
  return {
    totalCount: records.length,
    openCount: records.filter((record) => record.status === "OPEN").length,
    averageResolutionMinutes: resolved.length ? totalDuration / resolved.length : null,
  };
}

export function getIncidentTrend(records: IncidentRecordV1[]) {
  const counts = new Map<string, number>();
  for (const record of records) {
    const date = new Date(record.opened_at).toISOString().slice(0, 10);
    counts.set(date, (counts.get(date) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, count]) => ({ date, count }));
}

export function getRootCauseCounts(records: IncidentRecordV1[]) {
  const counts = new Map<string, number>();
  for (const record of records) counts.set(record.root_cause, (counts.get(record.root_cause) ?? 0) + 1);
  return [...counts.entries()]
    .filter(([, count]) => count > 1)
    .sort(([leftCause, leftCount], [rightCause, rightCount]) => rightCount - leftCount || leftCause.localeCompare(rightCause))
    .map(([rootCause, count]) => ({ rootCause, count }));
}
