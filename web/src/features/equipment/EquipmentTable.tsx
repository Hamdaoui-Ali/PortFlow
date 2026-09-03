import type { EquipmentRecordV1 } from "../../data/schema";
import {
  filterEquipment,
  sortEquipment,
  type EquipmentSortColumn,
  type SortDirection,
} from "./equipmentTableData";

interface EquipmentTableProps {
  records: EquipmentRecordV1[];
  query: string;
  terminal: string;
  sort: EquipmentSortColumn;
  direction: SortDirection;
  onQueryChange: (query: string) => void;
  onSortChange: (column: EquipmentSortColumn) => void;
  onSelect: (equipmentId: string) => void;
}

interface Column {
  key: EquipmentSortColumn;
  label: string;
  format: (record: EquipmentRecordV1) => string;
  numeric?: boolean;
}

function formatPercentage(value: number | null): string {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function formatMinutes(value: number | null): string {
  return value === null ? "Unavailable" : `${Number.isInteger(value) ? value : value.toFixed(1)} min`;
}

const columns: Column[] = [
  { key: "equipment_id", label: "Equipment ID", format: (record) => record.equipment_id },
  { key: "terminal_id", label: "Terminal", format: (record) => record.terminal_id },
  { key: "current_state", label: "State", format: (record) => record.current_state },
  { key: "availability", label: "Availability", format: (record) => formatPercentage(record.availability), numeric: true },
  { key: "utilization", label: "Utilization", format: (record) => formatPercentage(record.utilization), numeric: true },
  { key: "downtime_minutes", label: "Downtime", format: (record) => formatMinutes(record.downtime_minutes), numeric: true },
  { key: "alarm_count", label: "Alarms", format: (record) => String(record.alarm_count), numeric: true },
  { key: "mttr_minutes", label: "MTTR", format: (record) => formatMinutes(record.mttr_minutes), numeric: true },
];

export function EquipmentTable({
  records,
  query,
  terminal,
  sort,
  direction,
  onQueryChange,
  onSortChange,
  onSelect,
}: EquipmentTableProps) {
  const visibleRecords = sortEquipment(filterEquipment(records, query, terminal), sort, direction);

  return (
    <section className="equipment-table-section">
      <label className="equipment-search" htmlFor="equipment-search">
        <span>Search equipment ID</span>
        <input
          id="equipment-search"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
        />
      </label>

      <div className="equipment-table-overflow">
        <table className="equipment-table">
          <caption>Equipment fleet</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  aria-label={column.label}
                  aria-sort={sort === column.key
                    ? direction === "asc" ? "ascending" : "descending"
                    : undefined}
                  className={column.numeric ? "equipment-cell-numeric" : undefined}
                  key={column.key}
                  scope="col"
                >
                  <button
                    type="button"
                    aria-label={`Sort by ${column.label}`}
                    onClick={() => onSortChange(column.key)}
                  >
                    <span aria-hidden="true">{column.label}</span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRecords.map((record) => (
              <tr key={record.equipment_id}>
                {columns.map((column) => (
                  <td
                    className={column.numeric ? "equipment-cell-numeric" : undefined}
                    key={column.key}
                  >
                    {column.key === "equipment_id" ? (
                      <button
                        type="button"
                        aria-label={`Open equipment ${record.equipment_id}`}
                        onClick={() => onSelect(record.equipment_id)}
                      >
                        {record.equipment_id}
                      </button>
                    ) : column.format(record)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
