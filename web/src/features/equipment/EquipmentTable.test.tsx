import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EquipmentRecordV1 } from "../../data/schema";
import { EquipmentTable } from "./EquipmentTable";

const records: EquipmentRecordV1[] = [
  {
    alarm_count: 3,
    availability: 0.9444444444444444,
    available: true,
    current_state: "ACTIVE",
    downtime_minutes: 80,
    equipment_id: "QC-001",
    mtbf_hours: 24,
    mttr_minutes: 30,
    terminal_id: "TM-001",
    utilization: 0.7426470588235294,
  },
  {
    alarm_count: 1,
    availability: null,
    available: false,
    current_state: "MAINTENANCE",
    downtime_minutes: null,
    equipment_id: "QC-002",
    mtbf_hours: null,
    mttr_minutes: null,
    terminal_id: "TM-002",
    utilization: null,
  },
];

function renderTable(overrides: Partial<React.ComponentProps<typeof EquipmentTable>> = {}) {
  const props: React.ComponentProps<typeof EquipmentTable> = {
    direction: "asc",
    onQueryChange: vi.fn(),
    onSelect: vi.fn(),
    onSortChange: vi.fn(),
    query: "",
    records,
    sort: "availability",
    terminal: "all",
    ...overrides,
  };

  render(<EquipmentTable {...props} />);
  return props;
}

describe("EquipmentTable", () => {
  it("renders the fleet as a named native table with the approved columns and values", () => {
    renderTable({ terminal: "TM-001" });

    expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
    for (const heading of [
      "Equipment ID",
      "Terminal",
      "State",
      "Availability",
      "Utilization",
      "Downtime",
      "Alarms",
      "MTTR",
    ]) {
      expect(screen.getByRole("columnheader", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByRole("columnheader", { name: "Availability" }))
      .toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByRole("button", { name: "Open equipment QC-001" })).toBeInTheDocument();
    expect(screen.getByText("TM-001")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("94.4%")).toBeInTheDocument();
    expect(screen.getByText("74.3%")).toBeInTheDocument();
    expect(screen.getByText("80 min")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("30 min")).toBeInTheDocument();
    expect(screen.queryByText("QC-002")).not.toBeInTheDocument();
  });

  it("labels search and reports query and sort changes", () => {
    const onQueryChange = vi.fn();
    const onSortChange = vi.fn();
    renderTable({ onQueryChange, onSortChange });

    fireEvent.change(screen.getByRole("searchbox", { name: "Search equipment ID" }), {
      target: { value: "QC-002" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sort by MTTR" }));

    expect(onQueryChange).toHaveBeenCalledWith("QC-002");
    expect(onSortChange).toHaveBeenCalledWith("mttr_minutes");
  });

  it("exposes equipment selection through a keyboard-focusable native button", () => {
    const onSelect = vi.fn();
    renderTable({ onSelect });
    const equipmentButton = screen.getByRole("button", { name: "Open equipment QC-001" });

    equipmentButton.focus();
    expect(equipmentButton).toHaveFocus();
    fireEvent.click(equipmentButton);

    expect(onSelect).toHaveBeenCalledWith("QC-001");
  });

  it("shows Unavailable for nullable table metrics", () => {
    renderTable({ terminal: "TM-002" });

    expect(screen.getAllByText("Unavailable")).toHaveLength(4);
  });
});
