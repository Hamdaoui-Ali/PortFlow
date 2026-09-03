import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { IncidentDatasetState, IncidentRecordV1, SnapshotV1 } from "../../data/schema";
import { App } from "../../app/App";

const records: IncidentRecordV1[] = [
  {
    equipment_id: "QC-001",
    incident_id: "inc-000001",
    opened_at: "2026-09-02T03:00:00Z",
    resolved_at: "2026-09-02T03:30:00Z",
    root_cause: "Hydraulic leak",
    severity: "MAJOR",
    status: "RESOLVED",
    terminal_id: "TM-001",
  },
  {
    equipment_id: "QC-002",
    incident_id: "inc-000002",
    opened_at: "2026-09-02T20:00:00Z",
    resolved_at: null,
    root_cause: "Motor overload",
    severity: "CRITICAL",
    status: "OPEN",
    terminal_id: "TM-001",
  },
];

const snapshot = {
  manifest: {
    datasets: { overview: { path: "overview.json", sha256: "a".repeat(64) } },
    generated_at: "2026-09-02T23:55:02Z",
    quality_status: "PASS",
    record_counts: { telemetry: 288 },
    schema_version: 1,
    snapshot_id: "demo-v1",
    source_period_end: "2026-09-02T23:55:00Z",
    source_period_start: "2026-09-02T00:00:00Z",
  },
  overview: {
    availability: { available_intervals: 1, scheduled_intervals: 1, value: 1 },
    schema_version: 1,
    terminal_id: "TM-001",
  },
  incidents: { status: "ready", records },
} as SnapshotV1;

function renderIncidents(dataset: IncidentDatasetState = snapshot.incidents!) {
  window.history.replaceState({}, "", "/PortFlow/?#incidents");
  return render(<App loadData={() => Promise.resolve({ ...snapshot, incidents: dataset })} />);
}

describe("IncidentPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/PortFlow/#incidents");
  });

  it("shows analysis summaries and incident rows", async () => {
    renderIncidents();

    expect(await screen.findByRole("heading", { name: "Incident exploration" })).toBeInTheDocument();
    expect(screen.getByText("Average resolution")).toBeInTheDocument();
    expect(screen.getAllByText("Hydraulic leak").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Motor overload").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "inc-000001" })).toBeInTheDocument();
  });

  it("filters the incident table by severity", async () => {
    renderIncidents();

    fireEvent.change(await screen.findByLabelText("Incident severity"), { target: { value: "CRITICAL" } });

    expect(screen.getByText("inc-000002")).toBeInTheDocument();
    expect(screen.queryByText("inc-000001")).not.toBeInTheDocument();
  });

  it("opens a lifecycle detail view and returns to the incident list", async () => {
    renderIncidents();

    fireEvent.click(await screen.findByRole("link", { name: "inc-000001" }));
    expect(screen.getByRole("heading", { name: "Incident inc-000001" })).toBeInTheDocument();
    expect(screen.getByText("30 minutes")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Back to incident list/ }));
    expect(screen.getByRole("heading", { name: "Incident exploration" })).toBeInTheDocument();
  });

  it.each([
    ["absent", "Incident dataset not published"],
    ["empty", "Incident history empty"],
    ["malformed", "Published incident data malformed"],
    ["unavailable", "Incident data unavailable"],
  ] as const)("shows the %s incident dataset state", async (status, heading) => {
    renderIncidents({ status });
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
