import type { SnapshotFilterScope } from "./filterScope";

type FilterRecoveryResource = "overview" | "equipment" | "incidents";

const resourceLabels: Record<FilterRecoveryResource, string> = {
  overview: "Snapshot",
  equipment: "Equipment",
  incidents: "Incidents",
};

interface FilterRecoveryStateProps {
  readonly filterScope: SnapshotFilterScope;
  readonly onResetFilters: () => void;
  readonly resource: FilterRecoveryResource;
}

export function FilterRecoveryState({
  filterScope,
  onResetFilters,
  resource,
}: FilterRecoveryStateProps) {
  const isOverview = resource === "overview";
  const resourceLabel = resourceLabels[resource];
  const heading = isOverview
    ? "Snapshot unavailable for selected filters"
    : `${resourceLabel} unavailable for selected filters`;
  const description = isOverview
    ? "These filters do not match the published snapshot."
    : "The selected filters are outside the published snapshot scope.";

  return (
    <div className="data-state data-state-warning" role="status">
      <h2>{heading}</h2>
      <p>{description}</p>
      <p className="filter-scope-summary">
        Published scope: <strong>{filterScope.terminalLabel}</strong> · {filterScope.periodLabel}
      </p>
      <button type="button" className="filter-reset" onClick={onResetFilters}>
        Reset filters to published scope
      </button>
    </div>
  );
}
