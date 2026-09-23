import type {
  EquipmentActivityStatus,
  EquipmentActivityView,
  EquipmentIncidentStatus,
  EquipmentIncidentView,
} from "./equipmentContext";
import { formatIncidentOpenedAt } from "../incidents/incidentData";
import { IncidentRecordItem } from "../incidents/IncidentRecordItem";

interface EquipmentContextProps {
  activity: EquipmentActivityView;
  incidents: EquipmentIncidentView;
}

export function EquipmentContextPanel({ activity, incidents }: EquipmentContextProps) {
  return (
    <div className="equipment-context">
      <section className="equipment-context-section" aria-labelledby="equipment-activity-title">
        <div className="equipment-context-header">
          <p className="section-kicker">Recent telemetry</p>
          <h3 id="equipment-activity-title">Equipment activity</h3>
          <p>State transitions from the published replay snapshot.</p>
        </div>
        {activity.status === "ready" ? (
          <ol className="equipment-activity-list" aria-labelledby="equipment-activity-title">
            {activity.events.map((event) => (
              <li className="equipment-activity-item" key={event.event_id}>
                <time dateTime={event.event_timestamp}>
                  {formatIncidentOpenedAt(event.event_timestamp)}
                </time>
                <div>
                  <strong>{event.state}</strong>
                  <span className="equipment-activity-state">
                    {event.available ? "Available" : "Unavailable"}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <ContextMessage message={activityMessage(activity.status)} />
        )}
      </section>

      <section className="equipment-context-section" aria-labelledby="equipment-incidents-title">
        <div className="equipment-context-header">
          <p className="section-kicker">Operational history</p>
          <h3 id="equipment-incidents-title">Related incidents</h3>
          <p>Incidents recorded for this equipment in the published snapshot.</p>
        </div>
        {incidents.status === "ready" ? (
          <ul className="equipment-incident-list" aria-labelledby="equipment-incidents-title">
            {incidents.records.map((incident) => (
              <IncidentRecordItem
                key={incident.incident_id}
                record={incident}
                linkLabel={incident.incident_id}
                statusLabel={incident.status === "OPEN" ? "Open" : "Resolved"}
              />
            ))}
          </ul>
        ) : (
          <ContextMessage message={incidentMessage(incidents.status)} />
        )}
      </section>
    </div>
  );
}

function ContextMessage({ message }: { message: string }) {
  return <p className="equipment-context-message" role="status">{message}</p>;
}

function activityMessage(status: Exclude<EquipmentActivityStatus, "ready">): string {
  if (status === "absent") return "Replay activity is not included in this snapshot.";
  if (status === "empty") return "No replay activity is available in this snapshot.";
  return "No replay events match this equipment.";
}

function incidentMessage(status: Exclude<EquipmentIncidentStatus, "ready">): string {
  if (status === "absent") return "Incident history is not included in this snapshot.";
  if (status === "empty") return "No incidents are present in this snapshot.";
  if (status === "no-match") return "No incidents match this equipment.";
  if (status === "unavailable") return "Incident history is unavailable for this snapshot.";
  return "Incident history could not be read from this snapshot.";
}
