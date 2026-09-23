import type {
  EquipmentRecordV1,
  IncidentDatasetState,
  ReplayEventV1,
} from "../../data/schema";
import { formatMetric, formatPercentage } from "./equipmentMetrics";
import { EquipmentContextPanel } from "./EquipmentContextPanel";
import {
  deriveEquipmentActivity,
  deriveEquipmentIncidents,
} from "./equipmentContext";

interface EquipmentDetailProps {
  record: EquipmentRecordV1;
  onBack: () => void;
  replayEvents?: ReplayEventV1[];
  incidentDataset?: IncidentDatasetState;
}

export function EquipmentDetail({
  record,
  onBack,
  replayEvents,
  incidentDataset,
}: EquipmentDetailProps) {
  const details = [
    ["Terminal", record.terminal_id],
    ["State", record.current_state],
    ["Availability", formatPercentage(record.availability)],
    ["Utilization", formatPercentage(record.utilization)],
    ["Downtime", formatMetric(record.downtime_minutes, "min")],
    ["Alarms", String(record.alarm_count)],
    ["MTTR", formatMetric(record.mttr_minutes, "min")],
    ["MTBF", formatMetric(record.mtbf_hours, "hr")],
  ] as const;
  const activity = deriveEquipmentActivity(replayEvents, record.equipment_id);
  const incidents = deriveEquipmentIncidents(incidentDataset, record.equipment_id);

  return (
    <section className="equipment-detail" aria-labelledby="equipment-detail-title">
      <button className="equipment-detail-back" type="button" onClick={onBack}>
        Back to equipment fleet
      </button>
      <p className="section-kicker">Equipment detail</p>
      <h2 id="equipment-detail-title">{record.equipment_id}</h2>
      <dl className="equipment-detail-list">
        {details.map(([label, value]) => (
          <div className="equipment-detail-item" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <EquipmentContextPanel activity={activity} incidents={incidents} />
    </section>
  );
}
