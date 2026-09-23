import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { formatMinutes, formatPercentage } from "../equipment/equipmentMetrics";
import {
  deriveOverviewEquipmentPulse,
  type OverviewEquipmentPulse as OverviewEquipmentPulseView,
} from "./overviewEquipmentPulseData";

interface OverviewEquipmentPulseProps {
  readonly dataset?: EquipmentDatasetState;
}

interface ReadyPulseProps {
  readonly records: readonly EquipmentRecordV1[];
}

interface PulseMessageProps {
  readonly status: Exclude<OverviewEquipmentPulseView["status"], "ready">;
}

export function OverviewEquipmentPulse({ dataset }: OverviewEquipmentPulseProps) {
  const pulse = deriveOverviewEquipmentPulse(dataset);

  return (
    <section className="equipment-context" aria-labelledby="overview-equipment-pulse-title">
      <div className="equipment-context-header">
        <p className="section-kicker">Fleet context</p>
        <h2 id="overview-equipment-pulse-title">Equipment pulse</h2>
        <p>
          Unavailable or lower-availability records appear first in this snapshot.
        </p>
      </div>
      {pulse.status === "ready"
        ? <ReadyPulse records={pulse.records} />
        : <PulseMessage status={pulse.status} />}
    </section>
  );
}

function ReadyPulse({ records }: ReadyPulseProps) {
  return (
    <ul className="equipment-activity-list" aria-label="Equipment pulse records">
      {records.map((record) => (
        <li className="equipment-activity-item" key={record.equipment_id}>
          <div>
            <strong>
              <a
                className="equipment-incident-link"
                href={`?equipment=${encodeURIComponent(record.equipment_id)}#equipment`}
              >
                Open equipment {record.equipment_id}
              </a>
            </strong>
            <span className="equipment-activity-state">
              <span>{record.terminal_id}</span> <span aria-hidden="true">·</span> <span>{record.current_state}</span>
              <span>
                {record.available ? "Available" : "Unavailable"}
              </span>
            </span>
          </div>
          <div>
            <div><span className="equipment-activity-state">Availability</span> <strong>{formatPercentage(record.availability)}</strong></div>
            <div><span className="equipment-activity-state">Downtime</span> <strong>{formatMinutes(record.downtime_minutes)}</strong></div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function PulseMessage({ status }: PulseMessageProps) {
  return <output className="equipment-context-message">{messageForStatus(status)}</output>;
}

function messageForStatus(status: Exclude<OverviewEquipmentPulseView["status"], "ready">): string {
  switch (status) {
    case "absent":
      return "Equipment pulse is not included in this snapshot.";
    case "empty":
      return "No equipment records are present in this snapshot.";
    case "unavailable":
      return "Equipment pulse is unavailable for this snapshot.";
    case "malformed":
      return "Equipment pulse could not be read from this snapshot.";
  }
}
