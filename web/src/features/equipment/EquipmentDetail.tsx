import type { EquipmentRecordV1 } from "../../data/schema";

interface EquipmentDetailProps {
  record: EquipmentRecordV1;
  onBack: () => void;
}

function formatPercentage(value: number | null): string {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function formatMetric(value: number | null, unit: "min" | "hr"): string {
  if (value === null) return "Unavailable";
  return `${Number.isInteger(value) ? value : value.toFixed(1)} ${unit}`;
}

export function EquipmentDetail({ record, onBack }: EquipmentDetailProps) {
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
    </section>
  );
}
