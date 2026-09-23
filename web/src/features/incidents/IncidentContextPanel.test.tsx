import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { IncidentContextPanel } from "./IncidentContextPanel";

const equipmentRecord: EquipmentRecordV1 = {
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

describe("IncidentContextPanel", () => {
  it("renders the matching equipment context and native route link", () => {
    render(
      <IncidentContextPanel
        dataset={{ status: "ready", records: [equipmentRecord] }}
        equipmentId="QC-001"
      />,
    );

    expect(screen.getByRole("heading", { name: "Equipment context" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open equipment QC-001" })).toHaveAttribute(
      "href",
      "?equipment=QC-001#equipment",
    );
    expect(screen.getByText("TM-001")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("94.4%")).toBeInTheDocument();
    expect(screen.getByText("74.3%")).toBeInTheDocument();
    expect(screen.getByText("80 min")).toBeInTheDocument();
  });

  it.each([
    [undefined, "Equipment context is not included in this snapshot."],
    [{ status: "empty" }, "No equipment records are present in this snapshot."],
    [{ status: "unavailable" }, "Equipment context is unavailable for this snapshot."],
    [{ status: "malformed" }, "Equipment context could not be read from this snapshot."],
    [
      { status: "ready", records: [] },
      "No equipment record matches this incident.",
    ],
  ] as const)("renders an honest %s state", (dataset, message) => {
    render(<IncidentContextPanel dataset={dataset as EquipmentDatasetState | undefined} equipmentId="QC-001" />);

    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open equipment QC-001" })).not.toBeInTheDocument();
  });
});
