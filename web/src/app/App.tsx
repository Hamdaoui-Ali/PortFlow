import { useEffect, useState } from "react";

import { loadSnapshot, type SnapshotFetch } from "../data/loadSnapshot";
import type { SnapshotV1 } from "../data/schema";
import { AvailabilityCard } from "../features/overview/AvailabilityCard";
import { AppShell } from "./AppShell";

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
        {snapshotState.status === "loading" ? (
          <p className="data-state" role="status">Loading operational snapshot</p>
        ) : null}
        {snapshotState.status === "error" ? (
          <div className="data-state data-state-error" role="alert">
            <h2>Operational snapshot unavailable</h2>
            <p>PortFlow could not validate the published data.</p>
          </div>
        ) : null}
        {snapshotState.status === "ready" ? (
          <AvailabilityCard
            value={snapshotState.snapshot.overview.availability.value}
            generatedAt={snapshotState.snapshot.manifest.generated_at}
          />
        ) : null}
    </AppShell>
  );
}
