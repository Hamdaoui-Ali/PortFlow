import { useEffect, useState } from "react";

import { loadSnapshot, type SnapshotFetch } from "../data/loadSnapshot";
import type { SnapshotV1 } from "../data/schema";
import { AvailabilityCard } from "../features/overview/AvailabilityCard";
import { OverviewKpiRail } from "../features/overview/OverviewKpiRail";
import { AvailabilityTrend } from "../features/overview/AvailabilityTrend";
import { AppShell, useAppFilters, type AppFilters } from "./AppShell";

interface AppProps {
  loadData?: (fetcher?: SnapshotFetch, baseUrl?: string) => Promise<SnapshotV1>;
}

type SnapshotState =
  | { status: "loading" }
  | { status: "ready"; snapshot: SnapshotV1 }
  | { status: "error" };

export function App({ loadData = loadSnapshot }: AppProps) {
  const [snapshotState, setSnapshotState] = useState<SnapshotState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    void loadData()
      .then((snapshot) => {
        if (active) setSnapshotState({ status: "ready", snapshot });
      })
      .catch(() => {
        if (active) setSnapshotState({ status: "error" });
      });
    return () => {
      active = false;
    };
  }, [loadData]);

  return (
    <AppShell>
      <OverviewContent snapshotState={snapshotState} />
    </AppShell>
  );
}

function OverviewContent({ snapshotState }: { snapshotState: SnapshotState }) {
  const filters = useAppFilters();

  if (snapshotState.status === "loading") {
    return <p className="data-state" role="status">Loading operational snapshot</p>;
  }
  if (snapshotState.status === "error") {
    return (
      <div className="data-state data-state-error" role="alert">
        <h2>Operational snapshot unavailable</h2>
        <p>PortFlow could not validate the published data.</p>
      </div>
    );
  }

  const { snapshot } = snapshotState;
  if (!matchesFilters(snapshot, filters)) {
    return (
      <div className="data-state data-state-warning" role="status">
        <h2>Snapshot unavailable for selected filters</h2>
        <p>This published snapshot covers Casablanca Terminal and the last 24 hours only.</p>
      </div>
    );
  }

  return (
    <>
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
