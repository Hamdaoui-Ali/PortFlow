import { useEffect, useRef } from "react";
import type { IncidentRecordV1 } from "../../data/schema";
import { incidentDurationMinutes } from "./incidentData";
import { formatDuration } from "./IncidentTable";

export function IncidentDetail({ record, onBack }: { record: IncidentRecordV1; onBack: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const duration = incidentDurationMinutes(record);
  useEffect(() => headingRef.current?.focus(), [record.incident_id]);
  return (
    <article className="incident-detail" aria-labelledby="incident-detail-title">
      <button type="button" className="back-link" onClick={onBack}>← Back to incident list</button>
      <header className="detail-header">
        <div>
          <p className="section-kicker">Incident lifecycle</p>
          <h2 id="incident-detail-title" ref={headingRef} tabIndex={-1}>Incident {record.incident_id}</h2>
          <p>{record.equipment_id} at {record.terminal_id}</p>
        </div>
        <span className={`severity-pill severity-${record.severity.toLowerCase()}`}>{record.severity}</span>
      </header>
      <dl className="detail-grid">
        <div><dt>Status</dt><dd>{record.status}</dd></div>
        <div><dt>Root cause</dt><dd>{record.root_cause}</dd></div>
        <div><dt>Opened</dt><dd>{formatTimestamp(record.opened_at)}</dd></div>
        <div><dt>Resolved</dt><dd>{record.resolved_at ? formatTimestamp(record.resolved_at) : "Not resolved"}</dd></div>
        <div><dt>Recovery duration</dt><dd>{duration === null ? "In progress" : formatDuration(duration)}</dd></div>
      </dl>
    </article>
  );
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value));
}
