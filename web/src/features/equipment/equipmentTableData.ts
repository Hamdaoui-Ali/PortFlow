import type { EquipmentRecordV1 } from "../../data/schema";

export type EquipmentSortColumn =
  | "alarm_count"
  | "availability"
  | "current_state"
  | "downtime_minutes"
  | "equipment_id"
  | "mtbf_hours"
  | "mttr_minutes"
  | "terminal_id"
  | "utilization";

export type SortDirection = "asc" | "desc";

const numericColumns = new Set<EquipmentSortColumn>([
  "alarm_count",
  "availability",
  "downtime_minutes",
  "mtbf_hours",
  "mttr_minutes",
  "utilization",
]);

export function filterEquipment(
  records: EquipmentRecordV1[],
  query: string,
  terminal: string,
): EquipmentRecordV1[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const normalizedTerminal = terminal.trim();

  return records.filter((record) => {
    const matchesQuery = !normalizedQuery
      || record.equipment_id.toLocaleLowerCase().includes(normalizedQuery);
    const matchesTerminal = !normalizedTerminal || normalizedTerminal === "all"
      || record.terminal_id === normalizedTerminal;
    return matchesQuery && matchesTerminal;
  });
}

export function sortEquipment(
  records: EquipmentRecordV1[],
  column: EquipmentSortColumn,
  direction: SortDirection,
): EquipmentRecordV1[] {
  return records
    .map((record, index) => ({ record, index }))
    .sort((left, right) => {
      const leftValue = left.record[column];
      const rightValue = right.record[column];

      if (leftValue === rightValue) return left.index - right.index;
      if (leftValue === null) return 1;
      if (rightValue === null) return -1;

      const comparison = numericColumns.has(column)
        ? Number(leftValue) - Number(rightValue)
        : String(leftValue).localeCompare(String(rightValue));
      return direction === "asc" ? comparison : -comparison;
    })
    .map(({ record }) => record);
}
