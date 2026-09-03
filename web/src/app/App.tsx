import { useEffect, useState } from "react";

import { loadSnapshot, type SnapshotFetch } from "../data/loadSnapshot";
import { snapshotCache } from "../data/cache";
import { SnapshotLoadError, type SnapshotFailureKind } from "../data/errors";
import type { SnapshotV1 } from "../data/schema";
import { AvailabilityCard } from "../features/overview/AvailabilityCard";
import { OverviewKpiRail } from "../features/overview/OverviewKpiRail";
import { AvailabilityTrend } from "../features/overview/AvailabilityTrend";
import { EquipmentPage } from "../features/equipment/EquipmentPage";
import { IncidentPage } from "../features/incidents/IncidentPage";
import { LiveDemoPage } from "../features/replay/LiveDemoPage";
import { AppShell, useAppFilters, type AppFilters } from "./AppShell";

interface AppProps {
  loadData?: (fetcher?: SnapshotFetch, baseUrl?: string) => Promise<SnapshotV1>;
}

type SnapshotState =
  | { status: "loading" }
  | { status: "ready"; snapshot: SnapshotV1 }
  | { status: "error"; kind: SnapshotFailureKind }
  | { status: "stale"; kind: SnapshotFailureKind; snapshot: SnapshotV1 };

type AppRoute = "equipment" | "incidents" | "live-demo" | "overview";

export function App({ loadData = loadSnapshot }: AppProps) {
  const [snapshotState, setSnapshotState] = useState<SnapshotState>({ status: "loading" });
  const [route, setRoute] = useState<AppRoute>(readRoute);

  useEffect(() => {
    let active = true;
    void loadData()
      .then((snapshot) => {
        if (active) {
          snapshotCache.set(snapshot);
          setSnapshotState({ status: "ready", snapshot });
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        const kind = error instanceof SnapshotLoadError ? error.kind : "unavailable";
        const cached = snapshotCache.get();
        setSnapshotState(cached
          ? { status: "stale", kind, snapshot: cached.snapshot }
          : { status: "error", kind });
      });
    return () => {
      active = false;
    };
  }, [loadData]);

  useEffect(() => {
    const updateRoute = () => setRoute(readRoute());
    window.addEventListener("hashchange", updateRoute);
    return () => window.removeEventListener("hashchange", updateRoute);
  }, []);

  return (
    <AppShell>
      <AppContent route={route} snapshotState={snapshotState} />
    </AppShell>
  );
}

function AppContent({ route, snapshotState }: { route: AppRoute; snapshotState: SnapshotState }) {
  const filters = useAppFilters();

  if (snapshotState.status === "loading") {
    return <p className="data-state" role="status">Loading operational snapshot</p>;
  }
  if (snapshotState.status === "error") {
    return (
      <div className="data-state data-state-error" role="alert">
        <h2>{failureHeading(snapshotState.kind)}</h2>
        <p>{failureDescription(snapshotState.kind)}</p>
      </div>
    );
  }

  const { snapshot } = snapshotState;
  const staleNotice = snapshotState.status === "stale" ? (
    <div className="data-state data-state-warning stale-notice" role="status" aria-label="Showing last valid snapshot">
      <h2>Showing last valid snapshot</h2>
      <p>{failureDescription(snapshotState.kind)} New data will appear when the published snapshot recovers.</p>
    </div>
  ) : null;

  if (route === "equipment") {
    return (
      <>
        {staleNotice}
        <EquipmentPage
          dataset={snapshot.equipment ?? { status: "absent" }}
          filters={filters}
        />
      </>
    );
  }

  if (route === "incidents") {
    return (
      <>
        {staleNotice}
        <IncidentPage dataset={snapshot.incidents ?? { status: "absent" }} filters={filters} />
      </>
    );
  }

  if (route === "live-demo") {
    return (
      <>
        {staleNotice}
        <LiveDemoPage events={snapshot.event_replay} overview={snapshot.overview} />
      </>
    );
  }

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

function readRoute(): AppRoute {
  if (window.location.hash === "#equipment") return "equipment";
  if (window.location.hash === "#incidents") return "incidents";
  if (window.location.hash === "#live-demo") return "live-demo";
  return "overview";
}

function failureHeading(kind: SnapshotFailureKind): string {
  if (kind === "malformed") return "Published snapshot malformed";
  if (kind === "empty") return "Published snapshot empty";
  return "Operational snapshot unavailable";
}

function failureDescription(kind: SnapshotFailureKind): string {
  if (kind === "malformed") return "PortFlow could not validate the published data format.";
  if (kind === "empty") return "The published snapshot contains no scheduled operational intervals.";
  return "PortFlow could not reach the published data.";
}

function matchesFilters(snapshot: SnapshotV1, filters: AppFilters): boolean {
  const terminalMatches = filters.terminal === "all" || filters.terminal === snapshot.overview.terminal_id;
  return terminalMatches && filters.range === "24h";
}
