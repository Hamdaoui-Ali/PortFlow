import {
  Activity,
  AlertCircle,
  Clock3,
  Container,
  Gauge,
} from "lucide-react";

import type { OverviewV1 } from "../../data/schema";

interface OverviewKpiRailProps {
  overview: OverviewV1;
}

type Kpi = {
  label: string;
  value: string;
  detail: string;
  icon: typeof Activity;
  tone: "teal" | "cobalt" | "amber";
};

function formatNumber(value: number | null | undefined, suffix = ""): string {
  return value === null || value === undefined ? "Unavailable" : `${value}${suffix}`;
}

function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Unavailable";
  return `${Number.isInteger(value) ? value : value.toFixed(1)} min`;
}

export function OverviewKpiRail({ overview }: OverviewKpiRailProps) {
  const kpis: Kpi[] = [
    {
      label: "Throughput",
      value: formatNumber(overview.throughput, " moves"),
      detail: "Completed movements",
      icon: Container,
      tone: "cobalt",
    },
    {
      label: "Equipment availability",
      value: overview.availability.value === null ? "Unavailable" : `${(overview.availability.value * 100).toFixed(1)}%`,
      detail: "Available ÷ scheduled intervals",
      icon: Gauge,
      tone: "teal",
    },
    {
      label: "Average dwell time",
      value: formatMinutes(overview.average_dwell_minutes),
      detail: "Mean completed stay",
      icon: Clock3,
      tone: "cobalt",
    },
    {
      label: "MTTR",
      value: formatMinutes(overview.mttr_minutes),
      detail: "Mean repair duration",
      icon: Activity,
      tone: "amber",
    },
    {
      label: "Active incidents",
      value: formatNumber(overview.active_incidents),
      detail: "Open at period end",
      icon: AlertCircle,
      tone: "amber",
    },
  ];

  return (
    <section className="kpi-rail" aria-label="Overview KPIs">
      {kpis.map(({ label, value, detail, icon: Icon, tone }) => (
        <div className={`kpi-item kpi-item-${tone}`} key={label}>
          <div className="kpi-label"><Icon size={17} strokeWidth={1.8} aria-hidden="true" />{label}</div>
          <p className="kpi-value">{value}</p>
          <p className="kpi-detail">{detail}</p>
        </div>
      ))}
    </section>
  );
}
