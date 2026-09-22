import { useEffect, useState } from "react";

import type { SnapshotFetch } from "../data/loadSnapshot";
import { snapshotCache } from "../data/cache";
import { SnapshotLoadError, type SnapshotFailureKind } from "../data/errors";
import type { SnapshotV1 } from "../data/schema";
import { deriveHealthViewModel } from "../features/health/healthPresentation";
import { DataHealthPage } from "../features/health/DataHealthPage";
import { EquipmentPage } from "../features/equipment/EquipmentPage";
import { IncidentPage } from "../features/incidents/IncidentPage";
import { LiveDemoPage } from "../features/replay/LiveDemoPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { AppShell, useAppFilters, type AppFilters, type SnapshotHeaderStatus } from "./AppShell";

interface AppProps {
  loadData?: (fetcher?: SnapshotFetch, baseUrl?: string) => Promise<SnapshotV1>;
}

type SnapshotState =
  | { status: "loading" }
  | { status: "ready"; snapshot: SnapshotV1 }
  | { status: "error"; kind: SnapshotFailureKind }
  | { status: "stale"; kind: SnapshotFailureKind; snapshot: SnapshotV1 };

type AppRoute = "data-health" | "equipment" | "incidents" | "live-demo" | "overview";

const MAX_TIMEOUT_DELAY_MS = 2_147_000_000;

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
  const [freshnessNow, setFreshnessNow] = useState(() => new Date());

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

  useEffect(() => {
    if (snapshotState.status !== "ready") return;

    const evaluatedAt = new Date();
    setFreshnessNow(evaluatedAt);
    const health = deriveHealthViewModel(
      snapshotState.snapshot.manifest,
      snapshotState.snapshot.quality ?? { status: "absent" },
      evaluatedAt,
    );
    if (health.status !== "healthy") return;

    const staleAt = Date.parse(health.generatedAt) + health.staleAfterMs + 1;
    let timeout: number | undefined;
    const refreshAtStaleBoundary = () => {
      const remainingMs = staleAt - Date.now();
      if (remainingMs <= 0) {
        setFreshnessNow(new Date());
        return;
      }
      timeout = window.setTimeout(
        refreshAtStaleBoundary,
        Math.min(remainingMs, MAX_TIMEOUT_DELAY_MS),
      );
    };

    refreshAtStaleBoundary();
    return () => {
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [snapshotState]);

  return (
    <AppShell
      onNavigate={(hash) => setRoute(readRoute(hash))}
      snapshotStatus={deriveSnapshotHeaderStatus(snapshotState, freshnessNow)}
    >
      <AppContent route={route} snapshotState={snapshotState} />
    </AppShell>
  );
}

function deriveSnapshotHeaderStatus(snapshotState: SnapshotState, now: Date): SnapshotHeaderStatus {
  if (snapshotState.status === "loading") {
    return {
      kind: "loading",
      label: "Loading snapshot",
      message: "Fetching published operational data.",
    };
  }

  if (snapshotState.status === "error") {
    return {
      kind: "unavailable",
      label: "Snapshot unavailable",
      message: failureDescription(snapshotState.kind),
    };
  }

  const { snapshot } = snapshotState;
  if (snapshotState.status === "stale") {
    return {
      kind: "stale",
      label: "Showing last valid snapshot",
      message: "Using saved data after the latest refresh failed.",
      generatedAt: snapshot.manifest.generated_at,
    };
  }

  const health = deriveHealthViewModel(
    snapshot.manifest,
    snapshot.quality ?? { status: "absent" },
    now,
  );
  const label = {
    healthy: "Current snapshot",
    stale: "Stale snapshot",
    invalid: "Snapshot needs attention",
  }[health.status];

  return {
    kind: health.status,
    label,
    message: health.message,
    generatedAt: health.generatedAt,
  };
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
    <div className="data-state data-state-warning stale-notice" role="note" aria-label="Refresh details">
      <h2>Refresh issue</h2>
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

function readRoute(hash = window.location.hash): AppRoute {
  if (hash === "#equipment") return "equipment";
  if (hash === "#incidents") return "incidents";
  if (hash === "#live-demo") return "live-demo";
  if (hash === "#data-health") return "data-health";
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
