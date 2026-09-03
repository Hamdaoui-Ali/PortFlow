import type { ReplayViewModel } from "./replayPresentation";

export function ReplayKpiStrip({ model }: { model: ReplayViewModel }) {
  return (
    <section className="replay-kpi-strip" aria-label="Replay KPIs">
      <article className="replay-kpi-card"><span>Current state</span><strong>{model.currentStateLabel}</strong></article>
      <article className="replay-kpi-card"><span>Current availability</span><strong>{model.availabilityLabel}</strong></article>
      <article className="replay-kpi-card"><span>Replay progress</span><strong>{model.progressLabel}</strong></article>
      <article className="replay-kpi-card"><span>Snapshot availability</span><strong>{model.sourceAvailabilityLabel}</strong></article>
    </section>
  );
}
