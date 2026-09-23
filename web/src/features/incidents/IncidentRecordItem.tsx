import type { IncidentRecordV1 } from "../../data/schema";
import { formatIncidentOpenedAt } from "./incidentData";

interface IncidentRecordItemProps {
  readonly record: IncidentRecordV1;
  readonly linkLabel: string;
  readonly statusLabel: string;
}

export function IncidentRecordItem({ record, linkLabel, statusLabel }: IncidentRecordItemProps) {
  return (
    <li className="equipment-incident-item">
      <div className="equipment-incident-heading">
        <a
          className="equipment-incident-link"
          href={`?incident=${encodeURIComponent(record.incident_id)}#incidents`}
        >
          {linkLabel}
        </a>
        <span className={`severity-pill severity-${record.severity.toLowerCase()}`}>
          {record.severity}
        </span>
      </div>
      <strong>{record.root_cause}</strong>
      <span>{statusLabel}</span>
      <time dateTime={record.opened_at}>{formatIncidentOpenedAt(record.opened_at)}</time>
    </li>
  );
}
