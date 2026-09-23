import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { formatMinutes, formatPercentage } from "../equipment/equipmentMetrics";
import { OverviewPulseSection } from "./OverviewPulseSection";
import {
  deriveOverviewEquipmentPulse,
} from "./overviewEquipmentPulseData";

interface OverviewEquipmentPulseProps {
  readonly dataset?: EquipmentDatasetState;
}

export function OverviewEquipmentPulse({ dataset }: OverviewEquipmentPulseProps) {
  return (
    <OverviewPulseSection
      pulse={deriveOverviewEquipmentPulse(dataset)}
      eyebrow="Fleet context"
      title="Equipment pulse"
      titleId="overview-equipment-pulse-title"
      description="Unavailable or lower-availability records appear first in this snapshot."
      listClassName="equipment-activity-list"
      resourceName="Equipment"
      renderRecord={renderEquipmentRecord}
    />
  );
}

function renderEquipmentRecord(record: EquipmentRecordV1) {
  return (
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
          <span>{record.available ? "Available" : "Unavailable"}</span>
        </span>
      </div>
      <div>
        <div><span className="equipment-activity-state">Availability</span> <strong>{formatPercentage(record.availability)}</strong></div>
        <div><span className="equipment-activity-state">Downtime</span> <strong>{formatMinutes(record.downtime_minutes)}</strong></div>
      </div>
    </li>
  );
}
