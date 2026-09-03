import { Info } from "lucide-react";

import { KPI_DEFINITIONS, type KpiId } from "../content/kpis";

interface KpiDefinitionProps {
  kpiId: KpiId;
}

export function KpiDefinition({ kpiId }: KpiDefinitionProps) {
  const definition = KPI_DEFINITIONS[kpiId];

  return (
    <details className="kpi-definition" aria-label={`About ${definition.label}`}>
      <summary aria-label={`About ${definition.label}`}>
        <Info size={14} strokeWidth={1.8} aria-hidden="true" />
        <span>About</span>
      </summary>
      <div className="kpi-definition-content">
        <p><strong>Formula</strong> {definition.formula}</p>
        <p><strong>Grain</strong> {definition.grain}</p>
        <p><strong>Time boundary</strong> {definition.timeBoundary}</p>
        <p><strong>Exclusions</strong> {definition.exclusions}</p>
        <p><strong>Zero denominator</strong> {definition.zeroDenominator}</p>
      </div>
    </details>
  );
}
