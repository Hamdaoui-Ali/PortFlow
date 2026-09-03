import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EquipmentRecordV1 } from "../../data/schema";
import { EquipmentDetail } from "./EquipmentDetail";

const record: EquipmentRecordV1 = {
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
};

describe("EquipmentDetail", () => {
  it("renders the selected equipment fields with explicit labels and units", () => {
    render(<EquipmentDetail record={record} onBack={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "QC-001" })).toBeInTheDocument();
    for (const label of [
      "Terminal",
      "State",
      "Availability",
      "Utilization",
      "Downtime",
      "Alarms",
      "MTTR",
      "MTBF",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("TM-001")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("94.4%")).toBeInTheDocument();
    expect(screen.getByText("74.3%")).toBeInTheDocument();
    expect(screen.getByText("80 min")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("30 min")).toBeInTheDocument();
    expect(screen.getByText("24 hr")).toBeInTheDocument();
  });

  it("renders Unavailable for every nullable metric instead of fabricating values", () => {
    render(<EquipmentDetail
      record={{
        ...record,
        availability: null,
        downtime_minutes: null,
        mtbf_hours: null,
        mttr_minutes: null,
        utilization: null,
      }}
      onBack={vi.fn()}
    />);

    expect(screen.getAllByText("Unavailable")).toHaveLength(5);
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
    expect(screen.queryByText("0 min")).not.toBeInTheDocument();
  });

  it("returns to the fleet through an accessible control", () => {
    const onBack = vi.fn();
    render(<EquipmentDetail record={record} onBack={onBack} />);

    fireEvent.click(screen.getByRole("button", { name: "Back to equipment fleet" }));

    expect(onBack).toHaveBeenCalledOnce();
  });
});
