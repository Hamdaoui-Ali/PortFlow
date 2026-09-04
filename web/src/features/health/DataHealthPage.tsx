import type { ReactNode } from "react";

import type { ManifestV1, QualityDatasetState } from "../../data/schema";
import { HealthEvidence } from "./HealthEvidence";
import { HealthKpiRail } from "./HealthKpiRail";
import { HealthStatus } from "./HealthStatus";
import { deriveHealthViewModel } from "./healthPresentation";

interface DataHealthPageProps {
  manifest: ManifestV1;
  quality?: QualityDatasetState;
  staleNotice?: ReactNode;
}

export function DataHealthPage({ manifest, quality = { status: "absent" }, staleNotice }: DataHealthPageProps) {
  const model = deriveHealthViewModel(manifest, quality, new Date());

  return (
    <section className="data-health-page" aria-labelledby="data-health-title">
      {staleNotice}
      <header className="data-health-header">
        <p className="section-kicker">Snapshot trust</p>
        <h2 id="data-health-title">Data Health</h2>
        <p>Check whether the published operational snapshot is usable, current, and internally reconciled.</p>
        <p className="health-generated">Generated <time dateTime={model.generatedAt}>{model.generatedAt}</time> · Snapshot {manifest.snapshot_id}</p>
      </header>
      <HealthStatus model={model} />
      <HealthKpiRail model={model} />
      <HealthEvidence model={model} />
    </section>
  );
}
