import type { EquipmentDatasetState } from "../../data/schema";
import { formatMinutes, formatPercentage } from "../equipment/equipmentMetrics";
import { deriveIncidentEquipmentContext, type IncidentEquipmentContext } from "./incidentContext";

interface IncidentContextPanelProps {
  dataset?: EquipmentDatasetState;
  equipmentId: string;
}

export function IncidentContextPanel({ dataset, equipmentId }: IncidentContextPanelProps) {
  const context = deriveIncidentEquipmentContext(dataset, equipmentId);

  return (
    <section className="incident-context-panel" aria-labelledby="incident-context-title">
      <p className="section-kicker">Affected equipment</p>
      <h3 id="incident-context-title">Equipment context</h3>
      {context.status === "ready" ? <ReadyContext context={context} /> : <ContextMessage status={context.status} />}
    </section>
  );
}

function ReadyContext({ context }: { context: Extract<IncidentEquipmentContext, { status: "ready" }> }) {
  const { record } = context;
  return (
    <dl className="incident-context-list">
      <div className="incident-context-item">
        <dt>Equipment</dt>
        <dd>
          <a href={`?equipment=${encodeURIComponent(record.equipment_id)}#equipment`}>
            Open equipment {record.equipment_id}
          </a>
        </dd>
      </div>
      <div className="incident-context-item">
        <dt>Terminal</dt>
        <dd>{record.terminal_id}</dd>
      </div>
      <div className="incident-context-item">
        <dt>State</dt>
        <dd>{record.current_state}</dd>
      </div>
      <div className="incident-context-item">
        <dt>Availability</dt>
        <dd>{formatPercentage(record.availability)}</dd>
      </div>
      <div className="incident-context-item">
        <dt>Utilization</dt>
        <dd>{formatPercentage(record.utilization)}</dd>
      </div>
      <div className="incident-context-item">
        <dt>Downtime</dt>
        <dd>{formatMinutes(record.downtime_minutes)}</dd>
      </div>
    </dl>
  );
}

function ContextMessage({ status }: { status: Exclude<IncidentEquipmentContext["status"], "ready"> }) {
  return <p className="incident-context-message" role="status">{messageForStatus(status)}</p>;
}

function messageForStatus(status: Exclude<IncidentEquipmentContext["status"], "ready">): string {
  switch (status) {
    case "absent":
      return "Equipment context is not included in this snapshot.";
    case "empty":
      return "No equipment records are present in this snapshot.";
    case "unavailable":
      return "Equipment context is unavailable for this snapshot.";
    case "malformed":
      return "Equipment context could not be read from this snapshot.";
    case "no-match":
      return "No equipment record matches this incident.";
  }
}
