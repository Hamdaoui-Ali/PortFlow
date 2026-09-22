import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IncidentRecordV1, ReplayEventV1 } from "../../data/schema";
import type { EquipmentActivityView, EquipmentIncidentView } from "./equipmentContext";
import { EquipmentContextPanel } from "./EquipmentContextPanel";

const activityEvent: ReplayEventV1 = {
  available: true,
  equipment_id: "QC-001",
  event_id: "evt-000001",
  event_timestamp: "2026-09-02T02:00:00Z",
  state: "ACTIVE",
  terminal_id: "TM-001",
};

const incident: IncidentRecordV1 = {
  equipment_id: "QC-001",
  incident_id: "inc-000002",
  opened_at: "2026-09-02T02:15:00Z",
  resolved_at: null,
  root_cause: "Motor overload",
  severity: "CRITICAL",
  status: "OPEN",
  terminal_id: "TM-001",
};

function renderContext(
  activity: EquipmentActivityView,
  incidents: EquipmentIncidentView,
) {
  return render(<EquipmentContextPanel activity={activity} incidents={incidents} />);
}

describe("EquipmentContext", () => {
  it("renders replay activity and related incidents with accessible structure", () => {
    renderContext(
      { status: "ready", events: [activityEvent] },
      { status: "ready", records: [incident] },
    );

    expect(screen.getByRole("heading", { name: "Equipment activity" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Equipment activity" })).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getAllByRole("time")[0]).toHaveAttribute("dateTime", activityEvent.event_timestamp);
    expect(screen.getByRole("heading", { name: "Related incidents" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Related incidents" })).toBeInTheDocument();
    expect(screen.getByText("Motor overload")).toBeInTheDocument();
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /inc-000002/ })).toHaveAttribute(
      "href",
      "?incident=inc-000002#incidents",
    );
  });

  it.each([
    ["absent", "Replay activity is not included in this snapshot."],
    ["empty", "No replay activity is available in this snapshot."],
    ["no-match", "No replay events match this equipment."],
  ] as const)("renders the %s activity state honestly", (status, message) => {
    renderContext({ status, events: [] }, { status: "absent", records: [] });

    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it.each([
    ["absent", "Incident history is not included in this snapshot."],
    ["empty", "No incidents are present in this snapshot."],
    ["no-match", "No incidents match this equipment."],
    ["unavailable", "Incident history is unavailable for this snapshot."],
    ["malformed", "Incident history could not be read from this snapshot."],
  ] as const)("renders the %s incident state honestly", (status, message) => {
    renderContext(
      { status: "absent", events: [] },
      { status, records: [] },
    );

    expect(screen.getByText(message)).toBeInTheDocument();
  });
});
