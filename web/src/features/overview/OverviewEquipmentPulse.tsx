import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import {
  deriveOverviewEquipmentPulse,
  type OverviewEquipmentPulse as OverviewEquipmentPulseView,
} from "./overviewEquipmentPulseData";

interface OverviewEquipmentPulseProps {
  dataset?: EquipmentDatasetState;
}

export function OverviewEquipmentPulse({ dataset }: OverviewEquipmentPulseProps) {
  const pulse = deriveOverviewEquipmentPulse(dataset);

  return (
    <section className="overview-equipment-pulse" aria-labelledby="overview-equipment-pulse-title">
      <div className="overview-equipment-pulse-header">
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

function ReadyPulse({ records }: { records: EquipmentRecordV1[] }) {
  return (
    <ul className="overview-equipment-pulse-list" aria-label="Equipment pulse records">
      {records.map((record) => (
        <li className="overview-equipment-pulse-item" key={record.equipment_id}>
          <div className="overview-equipment-pulse-identity">
            <a href={`?equipment=${encodeURIComponent(record.equipment_id)}#equipment`}>
              Open equipment {record.equipment_id}
            </a>
            <span>
              <span>{record.terminal_id}</span> <span aria-hidden="true">·</span> <span>{record.current_state}</span>
              <span className="overview-equipment-pulse-availability-state">
                {record.available ? "Available" : "Unavailable"}
              </span>
            </span>
          </div>
          <dl className="overview-equipment-pulse-metrics">
            <div>
              <dt>Availability</dt>
              <dd>{formatPercentage(record.availability)}</dd>
            </div>
            <div>
              <dt>Downtime</dt>
              <dd>{formatMinutes(record.downtime_minutes)}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function PulseMessage({ status }: { status: Exclude<OverviewEquipmentPulseView["status"], "ready"> }) {
  return <p className="overview-equipment-pulse-message" role="status">{messageForStatus(status)}</p>;
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

function formatPercentage(value: number | null): string {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function formatMinutes(value: number | null): string {
  return value === null ? "Unavailable" : `${Number.isInteger(value) ? value : value.toFixed(1)} min`;
}
