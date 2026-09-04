import type { HealthViewModel } from "./healthPresentation";

interface HealthKpiRailProps {
  model: HealthViewModel;
}

function displayCount(value: number | null): string {
  return value === null ? "Unavailable" : String(value);
}

export function HealthKpiRail({ model }: HealthKpiRailProps) {
  const kpis = [
    ["Snapshot age", `${Math.floor(model.snapshotAgeMs / (60 * 60 * 1000))} hours`],
    ["Bronze records", displayCount(model.counts.bronze)],
    ["Silver records", displayCount(model.counts.silver)],
    ["Quarantined records", displayCount(model.counts.quarantine)],
    ["Rejected records", displayCount(model.counts.rejected)],
  ];

  return (
    <section className="health-kpi-rail" aria-label="Data Health KPIs">
      {kpis.map(([label, value]) => (
        <div className="health-kpi" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}
