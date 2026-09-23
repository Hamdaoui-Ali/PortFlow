import type { ReactNode } from "react";

import type { SnapshotV1 } from "../../data/schema";
import { AvailabilityCard } from "./AvailabilityCard";
import { AvailabilityTrend } from "./AvailabilityTrend";
import { OverviewEquipmentPulse } from "./OverviewEquipmentPulse";
import { OverviewIncidentPulse } from "./OverviewIncidentPulse";
import { OverviewKpiRail } from "./OverviewKpiRail";

interface OverviewPageProps {
  readonly snapshot: SnapshotV1;
  readonly equipmentDataset: SnapshotV1["equipment"];
  readonly incidentDataset: SnapshotV1["incidents"];
  readonly staleNotice: ReactNode;
}

export function OverviewPage({
  snapshot,
  equipmentDataset,
  incidentDataset,
  staleNotice,
}: OverviewPageProps) {
  return (
    <>
      {staleNotice}
      <OverviewKpiRail overview={snapshot.overview} />
      <section className="overview-analysis" aria-labelledby="availability-trend-title">
        <div>
          <p className="section-kicker">Equipment health</p>
          <h2 id="availability-trend-title">Hourly equipment availability</h2>
          <p className="analysis-summary">
            Bars show equipment availability for each hour. The throughput value above is the total for the selected period; hourly throughput data is not available.
          </p>
        </div>
        {snapshot.event_replay?.length ? (
          <AvailabilityTrend events={snapshot.event_replay} />
        ) : (
          <div className="analysis-empty" role="status">
            <span className="analysis-empty-line" aria-hidden="true" />
            <strong>Hourly availability data unavailable</strong>
            <span>Use the throughput total above while the next snapshot is generated.</span>
          </div>
        )}
      </section>
      <AvailabilityCard
        value={snapshot.overview.availability.value}
        generatedAt={snapshot.manifest.generated_at}
      />
      <OverviewEquipmentPulse dataset={equipmentDataset} />
      <OverviewIncidentPulse dataset={incidentDataset} />
    </>
  );
}
