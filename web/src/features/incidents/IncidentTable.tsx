import type { IncidentRecordV1 } from "../../data/schema";
import { incidentDurationMinutes, type IncidentSeverity, type IncidentSortColumn, type SortDirection } from "./incidentData";

interface IncidentTableProps {
  records: IncidentRecordV1[];
  query: string;
  severity: IncidentSeverity;
  sort: IncidentSortColumn;
  direction: SortDirection;
  onQueryChange: (query: string) => void;
  onSeverityChange: (severity: IncidentSeverity) => void;
  onSortChange: (column: IncidentSortColumn) => void;
  onSelect: (incidentId: string) => void;
}

const columns: Array<{ key: IncidentSortColumn; label: string }> = [
  { key: "incident_id", label: "Incident" },
  { key: "severity", label: "Severity" },
  { key: "status", label: "Status" },
  { key: "opened_at", label: "Opened" },
  { key: "duration_minutes", label: "Duration" },
];

export function IncidentTable({
  records,
  query,
  severity,
  sort,
  direction,
  onQueryChange,
  onSeverityChange,
  onSortChange,
  onSelect,
}: IncidentTableProps) {
  return (
    <section className="incident-table-panel" aria-labelledby="incident-table-title">
      <div className="table-toolbar">
        <div>
          <p className="section-kicker">Incident register</p>
          <h3 id="incident-table-title">Operational incidents</h3>
        </div>
        <div className="table-filters">
          <label className="filter-control">
            <span>Search incidents</span>
            <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="ID, equipment, or cause" />
          </label>
          <label className="filter-control">
            <span>Incident severity</span>
            <select value={severity} onChange={(event) => onSeverityChange(event.target.value as IncidentSeverity)}>
              <option value="all">All severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="MAJOR">Major</option>
              <option value="MINOR">Minor</option>
            </select>
          </label>
        </div>
      </div>
      <div className="table-scroll-region">
        <table className="data-table">
          <caption className="sr-only">Incident register with sortable columns</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} scope="col" aria-sort={sort === column.key ? direction === "asc" ? "ascending" : "descending" : "none"}>
                  <button type="button" className="table-sort-button" onClick={() => onSortChange(column.key)}>
                    {column.label}
                  </button>
                </th>
              ))}
              <th scope="col">Root cause</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => {
              const duration = incidentDurationMinutes(record);
              return (
                <tr key={record.incident_id}>
                  <th scope="row">
                    <a href={`?incident=${encodeURIComponent(record.incident_id)}#incidents`} onClick={(event) => { event.preventDefault(); onSelect(record.incident_id); }}>
                      {record.incident_id}
                    </a>
                    <span className="table-subtext">{record.equipment_id} · {record.terminal_id}</span>
                  </th>
                  <td><span className={`severity-pill severity-${record.severity.toLowerCase()}`}>{record.severity}</span></td>
                  <td>{record.status}</td>
                  <td>{formatDate(record.opened_at)}</td>
                  <td>{duration === null ? "Open" : formatDuration(duration)}</td>
                  <td>{record.root_cause}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(value));
}

export function formatDuration(minutes: number): string {
  return `${Math.round(minutes)} minute${Math.round(minutes) === 1 ? "" : "s"}`;
}
