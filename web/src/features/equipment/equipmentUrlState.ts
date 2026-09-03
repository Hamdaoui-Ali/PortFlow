import type { EquipmentSortColumn, SortDirection } from "./equipmentTableData";

export interface EquipmentUrlState {
  query: string;
  sort: EquipmentSortColumn;
  direction: SortDirection;
  equipmentId: string | null;
}

export const defaultEquipmentUrlState: EquipmentUrlState = {
  query: "",
  sort: "equipment_id",
  direction: "asc",
  equipmentId: null,
};

const sortColumns = new Set<EquipmentSortColumn>([
  "alarm_count",
  "availability",
  "current_state",
  "downtime_minutes",
  "equipment_id",
  "mtbf_hours",
  "mttr_minutes",
  "terminal_id",
  "utilization",
]);

export function readEquipmentUrlState(search: string): EquipmentUrlState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const sort = params.get("sort");
  const direction = params.get("direction");
  const query = params.get("search")?.trim() ?? "";
  const equipmentId = params.get("equipment")?.trim() || null;

  return {
    query,
    sort: sort && sortColumns.has(sort as EquipmentSortColumn)
      ? sort as EquipmentSortColumn
      : defaultEquipmentUrlState.sort,
    direction: direction === "desc" ? "desc" : defaultEquipmentUrlState.direction,
    equipmentId,
  };
}

export function writeEquipmentUrlState(state: EquipmentUrlState): string {
  const params = new URLSearchParams();
  const query = state.query.trim();
  const equipmentId = state.equipmentId?.trim();

  if (query) params.set("search", query);
  if (state.sort !== defaultEquipmentUrlState.sort) params.set("sort", state.sort);
  if (state.direction !== defaultEquipmentUrlState.direction) params.set("direction", state.direction);
  if (equipmentId) params.set("equipment", equipmentId);

  return params.toString();
}
