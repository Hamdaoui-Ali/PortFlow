import { lazy, Suspense, useEffect, useState } from "react";

import type { SnapshotFetch } from "../data/loadSnapshot";
import { snapshotCache } from "../data/cache";
import { SnapshotLoadError, type SnapshotFailureKind } from "../data/errors";
import type { SnapshotV1 } from "../data/schema";
import { AppShell, useAppFilters, type AppFilters } from "./AppShell";

const EquipmentPage = lazy(() =>
  import("../features/equipment/EquipmentPage").then(({ EquipmentPage: page }) => ({ default: page })),
);
const IncidentPage = lazy(() =>
  import("../features/incidents/IncidentPage").then(({ IncidentPage: page }) => ({ default: page })),
);
const LiveDemoPage = lazy(() =>
  import("../features/replay/LiveDemoPage").then(({ LiveDemoPage: page }) => ({ default: page })),
);
const DataHealthPage = lazy(() =>
  import("../features/health/DataHealthPage").then(({ DataHealthPage: page }) => ({ default: page })),
);
const OverviewPage = lazy(() =>
  import("../features/overview/OverviewPage").then(({ OverviewPage: page }) => ({ default: page })),
);

interface AppProps {
  loadData?: (fetcher?: SnapshotFetch, baseUrl?: string) => Promise<SnapshotV1>;
}

type SnapshotState =
  | { status: "loading" }
  | { status: "ready"; snapshot: SnapshotV1 }
  | { status: "error"; kind: SnapshotFailureKind }
  | { status: "stale"; kind: SnapshotFailureKind; snapshot: SnapshotV1 };

type AppRoute = "data-health" | "equipment" | "incidents" | "live-demo" | "overview";

export async function loadDefaultSnapshot(
  fetcher?: SnapshotFetch,
  baseUrl?: string,
): Promise<SnapshotV1> {
  const { loadSnapshot } = await import("../data/loadSnapshot");
  return loadSnapshot(fetcher, baseUrl);
}

export function App({ loadData = loadDefaultSnapshot }: AppProps) {
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
      <Suspense fallback={<p className="data-state" role="status">Loading selected view</p>}>
        <AppContent route={route} snapshotState={snapshotState} />
      </Suspense>
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

  if (route === "data-health") {
    return (
      <DataHealthPage
        manifest={snapshot.manifest}
        quality={snapshot.quality}
        staleNotice={staleNotice}
      />
    );
  }

  return <OverviewPage snapshot={snapshot} filters={filters} staleNotice={staleNotice} />;
}

function readRoute(): AppRoute {
  if (window.location.hash === "#equipment") return "equipment";
  if (window.location.hash === "#incidents") return "incidents";
  if (window.location.hash === "#live-demo") return "live-demo";
  if (window.location.hash === "#data-health") return "data-health";
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
