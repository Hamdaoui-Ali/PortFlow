import type { IncidentDatasetState, IncidentRecordV1 } from "../../data/schema";
import { formatIncidentOpenedAt } from "../incidents/incidentData";
import {
  deriveOverviewIncidentPulse,
  type OverviewIncidentPulse as OverviewIncidentPulseView,
} from "./overviewIncidentPulseData";

interface OverviewIncidentPulseProps {
  readonly dataset?: IncidentDatasetState;
}

interface ReadyIncidentPulseProps {
  readonly records: readonly IncidentRecordV1[];
}

interface IncidentPulseMessageProps {
  readonly status: Exclude<OverviewIncidentPulseView["status"], "ready">;
}

export function OverviewIncidentPulse({ dataset }: OverviewIncidentPulseProps) {
  const pulse = deriveOverviewIncidentPulse(dataset);

  return (
    <section className="incident-pulse" aria-labelledby="overview-incident-pulse-title">
      <div className="incident-pulse-header">
        <p className="section-kicker">Reliability context</p>
        <h2 id="overview-incident-pulse-title">Incident pulse</h2>
        <p>Open and highest-severity incidents appear first in this snapshot.</p>
      </div>
      {pulse.status === "ready"
        ? <ReadyIncidentPulse records={pulse.records} />
        : <IncidentPulseMessage status={pulse.status} />}
    </section>
  );
}

function ReadyIncidentPulse({ records }: ReadyIncidentPulseProps) {
  return (
    <ul className="incident-pulse-list" aria-label="Incident pulse records">
      {records.map((record) => (
        <li className="incident-pulse-item" key={record.incident_id}>
          <div className="incident-pulse-heading">
            <a
              className="incident-pulse-link"
              href={incidentHref(record.incident_id)}
            >
              Open incident {record.incident_id}
            </a>
            <span className={`severity-pill severity-${record.severity.toLowerCase()}`}>
              {record.severity}
            </span>
          </div>
          <strong>{record.root_cause}</strong>
          <span className="incident-pulse-meta">
            {record.terminal_id} · {record.equipment_id} · {record.status}
          </span>
          <time dateTime={record.opened_at}>{formatIncidentOpenedAt(record.opened_at)}</time>
        </li>
      ))}
    </ul>
  );
}

function IncidentPulseMessage({ status }: IncidentPulseMessageProps) {
  return <output className="incident-pulse-message">{messageForStatus(status)}</output>;
}

function messageForStatus(status: Exclude<OverviewIncidentPulseView["status"], "ready">): string {
  switch (status) {
    case "absent":
      return "Incident pulse is not included in this snapshot.";
    case "empty":
      return "No incidents are present in this snapshot.";
    case "unavailable":
      return "Incident pulse is unavailable for this snapshot.";
    case "malformed":
      return "Incident pulse could not be read from this snapshot.";
  }
}

function incidentHref(incidentId: string): string {
  return `?incident=${encodeURIComponent(incidentId)}#incidents`;
}
