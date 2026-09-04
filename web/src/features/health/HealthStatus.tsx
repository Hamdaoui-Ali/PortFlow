import { AlertTriangle, CheckCircle2, CircleX } from "lucide-react";

import type { HealthViewModel } from "./healthPresentation";

export function HealthStatus({ model }: { model: HealthViewModel }) {
  const Icon = model.status === "healthy" ? CheckCircle2 : model.status === "stale" ? AlertTriangle : CircleX;
  const label = model.status[0].toUpperCase() + model.status.slice(1);

  return (
    <section className={`health-status health-status-${model.status}`} aria-labelledby="health-status-title">
      <div className="health-status-heading">
        <Icon size={22} aria-hidden="true" />
        <h2 id="health-status-title">{label}</h2>
      </div>
      <p>{model.message}</p>
    </section>
  );
}
