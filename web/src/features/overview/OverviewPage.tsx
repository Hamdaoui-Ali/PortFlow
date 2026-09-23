import type { ReactNode } from "react";

import type { SnapshotV1 } from "../../data/schema";
import { AvailabilityCard } from "./AvailabilityCard";
import { AvailabilityTrend } from "./AvailabilityTrend";
import { OverviewEquipmentPulse } from "./OverviewEquipmentPulse";
import { OverviewKpiRail } from "./OverviewKpiRail";
import type { AppFilters } from "../../app/AppShell";

interface OverviewPageProps {
  readonly snapshot: SnapshotV1;
  readonly equipmentDataset: SnapshotV1["equipment"];
  readonly filters: AppFilters;
  readonly staleNotice: ReactNode;
}

export function OverviewPage({ snapshot, equipmentDataset, filters, staleNotice }: OverviewPageProps) {
  if (!matchesFilters(snapshot, filters)) {
    return <>
      {staleNotice}
      <div className="data-state data-state-warning" role="status">
        <h2>Snapshot unavailable for selected filters</h2>
        <p>This published snapshot covers Casablanca Terminal and the last 24 hours only.</p>
      </div>
    </>;
  }

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
    </>
  );
}

function matchesFilters(snapshot: SnapshotV1, filters: AppFilters): boolean {
  const terminalMatches = filters.terminal === "all" || filters.terminal === snapshot.overview.terminal_id;
  return terminalMatches && filters.range === "24h";
}
