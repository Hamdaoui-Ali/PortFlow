import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { EquipmentDatasetState, EquipmentRecordV1 } from "../../data/schema";
import { OverviewEquipmentPulse } from "./OverviewEquipmentPulse";

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

describe("OverviewEquipmentPulse", () => {
  it("renders ranked records with native equipment links and metrics", () => {
    render(
      <OverviewEquipmentPulse
        dataset={{
          status: "ready",
          records: [
            {
              ...equipmentRecord,
              availability: 0.8,
              available: false,
              current_state: "DOWN",
              downtime_minutes: 40,
              equipment_id: "QC-002",
              terminal_id: "TM-002",
            },
            equipmentRecord,
          ],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Equipment pulse" })).toBeInTheDocument();
    expect(screen.getByText(
      "Unavailable or lower-availability records appear first in this snapshot.",
    )).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Equipment pulse records" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open equipment QC-002" })).toHaveAttribute(
      "href",
      "?equipment=QC-002#equipment",
    );
    expect(screen.getByRole("link", { name: "Open equipment QC-001" })).toHaveAttribute(
      "href",
      "?equipment=QC-001#equipment",
    );
    expect(screen.getByText("TM-001")).toBeInTheDocument();
    expect(screen.getByText("TM-002")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("DOWN")).toBeInTheDocument();
    expect(screen.getByText("94.4%")).toBeInTheDocument();
    expect(screen.getAllByText("80 min")).toHaveLength(2);
  });

  it.each([
    [undefined, "Equipment pulse is not included in this snapshot."],
    [{ status: "empty" }, "No equipment records are present in this snapshot."],
    [{ status: "unavailable" }, "Equipment pulse is unavailable for this snapshot."],
    [{ status: "malformed" }, "Equipment pulse could not be read from this snapshot."],
    [{ status: "ready", records: [] }, "No equipment records are present in this snapshot."],
  ] as const)("renders an honest dataset state", (dataset, message) => {
    render(<OverviewEquipmentPulse dataset={dataset as EquipmentDatasetState | undefined} />);

    expect(screen.getByRole("status")).toHaveTextContent(message);
    expect(screen.queryByRole("list", { name: "Equipment pulse records" })).not.toBeInTheDocument();
  });
});
