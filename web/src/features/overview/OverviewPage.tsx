import type { ReactNode } from "react";

import type { SnapshotV1 } from "../../data/schema";
import { AvailabilityCard } from "./AvailabilityCard";
import { AvailabilityTrend } from "./AvailabilityTrend";
import { OverviewKpiRail } from "./OverviewKpiRail";
import type { AppFilters } from "../../app/AppShell";

interface OverviewPageProps {
  snapshot: SnapshotV1;
  filters: AppFilters;
  staleNotice: ReactNode;
}

export function OverviewPage({ snapshot, filters, staleNotice }: OverviewPageProps) {
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
      <section className="overview-analysis" aria-label="Terminal throughput trend">
        <div>
          <p className="section-kicker">Activity signal</p>
          <h2>Terminal throughput (moves)</h2>
          <p className="analysis-summary">The current public snapshot contains a period total, not a time-series breakdown.</p>
        </div>
        {snapshot.event_replay?.length ? (
          <AvailabilityTrend events={snapshot.event_replay} />
        ) : (
          <div className="analysis-empty" role="status">
            <span className="analysis-empty-line" aria-hidden="true" />
            <strong>Trend data unavailable</strong>
            <span>Use the period total above while the next snapshot is generated.</span>
          </div>
        )}
      </section>
      <AvailabilityCard
        value={snapshot.overview.availability.value}
        generatedAt={snapshot.manifest.generated_at}
      />
    </>
  );
}

function matchesFilters(snapshot: SnapshotV1, filters: AppFilters): boolean {
  const terminalMatches = filters.terminal === "all" || filters.terminal === snapshot.overview.terminal_id;
  return terminalMatches && filters.range === "24h";
}
