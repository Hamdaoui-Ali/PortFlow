import type { IncidentDatasetState, IncidentRecordV1 } from "../../data/schema";
import { IncidentRecordItem } from "../incidents/IncidentRecordItem";
import {
  deriveOverviewIncidentPulse,
} from "./overviewIncidentPulseData";
import { OverviewPulseSection } from "./OverviewPulseSection";

interface OverviewIncidentPulseProps {
  readonly dataset?: IncidentDatasetState;
}

export function OverviewIncidentPulse({ dataset }: OverviewIncidentPulseProps) {
  return (
    <OverviewPulseSection
      pulse={deriveOverviewIncidentPulse(dataset)}
      eyebrow="Reliability context"
      title="Incident pulse"
      titleId="overview-incident-pulse-title"
      description="Open and highest-severity incidents appear first in this snapshot."
      renderRecord={renderIncidentRecord}
    />
  );
}

function renderIncidentRecord(record: IncidentRecordV1) {
  return (
    <IncidentRecordItem
      key={record.incident_id}
      record={record}
      linkLabel={`Open incident ${record.incident_id}`}
      statusLabel={`${record.terminal_id} · ${record.equipment_id} · ${record.status}`}
    />
  );
}
