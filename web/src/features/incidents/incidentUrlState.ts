import type { IncidentSeverity, IncidentSortColumn, SortDirection } from "./incidentData";

export interface IncidentUrlState {
  query: string;
  severity: IncidentSeverity;
  sort: IncidentSortColumn;
  direction: SortDirection;
  incidentId: string | null;
}

export const defaultIncidentUrlState: IncidentUrlState = {
  query: "",
  severity: "all",
  sort: "opened_at",
  direction: "desc",
  incidentId: null,
};

const sortColumns = new Set<IncidentSortColumn>([
  "incident_id", "opened_at", "severity", "status", "duration_minutes",
]);
const severities = new Set<IncidentSeverity>(["all", "MINOR", "MAJOR", "CRITICAL"]);

export function readIncidentUrlState(search: string): IncidentUrlState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const sort = params.get("sort");
  const severity = params.get("severity");
  return {
    query: params.get("search")?.trim() ?? "",
    severity: severity && severities.has(severity as IncidentSeverity) ? severity as IncidentSeverity : "all",
    sort: sort && sortColumns.has(sort as IncidentSortColumn) ? sort as IncidentSortColumn : "opened_at",
    direction: params.get("direction") === "asc" ? "asc" : "desc",
    incidentId: params.get("incident")?.trim() || null,
  };
}

export function writeIncidentUrlState(state: IncidentUrlState): string {
  const params = new URLSearchParams();
  if (state.query.trim()) params.set("search", state.query.trim());
  if (state.severity !== "all") params.set("severity", state.severity);
  if (state.sort !== "opened_at") params.set("sort", state.sort);
  if (state.direction !== "desc") params.set("direction", state.direction);
  if (state.incidentId?.trim()) params.set("incident", state.incidentId.trim());
  return params.toString();
}
