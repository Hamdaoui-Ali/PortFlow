import {
  Activity,
  AlertCircle,
  Clock3,
  Container,
  Gauge,
} from "lucide-react";

import type { OverviewV1 } from "../../data/schema";
import { KpiDefinition } from "../../components/KpiDefinition";
import type { KpiId } from "../../content/kpis";
import { formatMinutes, formatPercentage } from "../equipment/equipmentMetrics";

interface OverviewKpiRailProps {
  readonly overview: OverviewV1;
}

interface KpiAction {
  readonly href: string;
  readonly label: string;
}

interface Kpi {
  readonly id: KpiId;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
  readonly icon: typeof Activity;
  readonly tone: "teal" | "cobalt" | "amber";
  readonly action?: KpiAction;
}

function formatNumber(value: number | null | undefined, suffix = ""): string {
  return value === null || value === undefined ? "Unavailable" : `${value}${suffix}`;
}

export function OverviewKpiRail({ overview }: OverviewKpiRailProps) {
  const kpis: Kpi[] = [
    {
      id: "throughput",
      label: "Throughput",
      value: formatNumber(overview.throughput, " moves"),
      detail: "Completed movements",
      icon: Container,
      tone: "cobalt",
    },
    {
      id: "availability",
      label: "Equipment availability",
      value: formatPercentage(overview.availability.value),
      detail: "Available ÷ scheduled intervals",
      icon: Gauge,
      tone: "teal",
      action: { href: "#equipment", label: "Open equipment fleet" },
    },
    {
      id: "average-dwell",
      label: "Average dwell time",
      value: formatMinutes(overview.average_dwell_minutes),
      detail: "Mean completed stay",
      icon: Clock3,
      tone: "cobalt",
    },
    {
      id: "mttr",
      label: "MTTR",
      value: formatMinutes(overview.mttr_minutes),
      detail: "Mean repair duration",
      icon: Activity,
      tone: "amber",
    },
    {
      id: "active-incidents",
      label: "Active incidents",
      value: formatNumber(overview.active_incidents),
      detail: "Open at period end",
      icon: AlertCircle,
      tone: "amber",
      action: { href: "#incidents", label: "Open incident register" },
    },
  ];

  return (
    <section className="kpi-rail" aria-label="Overview KPIs">
      {kpis.map(({ id, label, value, detail, icon: Icon, tone, action }) => (
        <div className={`kpi-item kpi-item-${tone}`} key={label}>
          <div className="kpi-label"><Icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span><KpiDefinition kpiId={id} /></div>
          <p className="kpi-value">{value}</p>
          <p className="kpi-detail">{detail}</p>
          {action ? <a className="kpi-action" href={action.href}>{action.label}</a> : null}
        </div>
      ))}
    </section>
  );
}
