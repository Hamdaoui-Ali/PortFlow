import {
  Activity,
  AlertCircle,
  Clock3,
  Container,
  Gauge,
} from "lucide-react";

import { KpiDefinition } from "../../components/KpiDefinition";
import { KPI_DEFINITIONS, type KpiId } from "../../content/kpis";
import type { OverviewV1 } from "../../data/schema";
import { formatMinutes, formatPercentage } from "../equipment/equipmentMetrics";

interface OverviewKpiRailProps {
  readonly overview: OverviewV1;
}

type Kpi = readonly [
  id: KpiId,
  value: string,
  detail: string,
  icon: typeof Activity,
  tone: "teal" | "cobalt" | "amber",
  action?: "equipment" | "incidents",
];

function formatNumber(value: number | null | undefined, suffix = ""): string {
  return value === null || value === undefined ? "Unavailable" : `${value}${suffix}`;
}

export function OverviewKpiRail({ overview }: OverviewKpiRailProps) {
  const kpis: Kpi[] = [
    ["throughput", formatNumber(overview.throughput, " moves"), "Completed movements", Container, "cobalt"],
    [
      "availability",
      formatPercentage(overview.availability.value),
      "Available ÷ scheduled intervals",
      Gauge,
      "teal",
      "equipment",
    ],
    ["average-dwell", formatMinutes(overview.average_dwell_minutes), "Mean completed stay", Clock3, "cobalt"],
    ["mttr", formatMinutes(overview.mttr_minutes), "Mean repair duration", Activity, "amber"],
    [
      "active-incidents",
      formatNumber(overview.active_incidents),
      "Open at period end",
      AlertCircle,
      "amber",
      "incidents",
    ],
  ];

  return (
    <section className="kpi-rail" aria-label="Overview KPIs">
      {kpis.map(([id, value, detail, Icon, tone, action]) => (
        <div className={`kpi-item kpi-item-${tone}`} key={id}>
          <div className="kpi-label"><Icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{KPI_DEFINITIONS[id].label}</span><KpiDefinition kpiId={id} /></div>
          <p className="kpi-value">{value}</p>
          <p className="kpi-detail">{detail}</p>
          {action ? <a className="snapshot-freshness-link kpi-link" href={`#${action}`}>Open {action}</a> : null}
        </div>
      ))}
    </section>
  );
}
