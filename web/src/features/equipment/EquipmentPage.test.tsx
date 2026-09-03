import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../../app/App";
import { snapshotCache } from "../../data/cache";
import type { EquipmentDatasetState, EquipmentRecordV1, SnapshotV1 } from "../../data/schema";

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
    availability: 0.875,
    available: false,
    current_state: "MAINTENANCE",
    downtime_minutes: 180,
    equipment_id: "QC-002",
    mtbf_hours: 18,
    mttr_minutes: 45,
    terminal_id: "TM-002",
    utilization: 0.625,
  },
];

const snapshot: SnapshotV1 = {
  manifest: {
    datasets: {
      overview: {
        path: "snapshots/demo-v1/overview.json",
        sha256: "13046979b100d92a07ea391dbbe003a3e58333da33916db1bb62666a88c7320d",
      },
      equipment: {
        path: "snapshots/demo-v1/equipment.json",
        sha256: "23046979b100d92a07ea391dbbe003a3e58333da33916db1bb62666a88c7320d",
      },
    },
    generated_at: "2026-09-02T23:55:02Z",
    quality_status: "PASS",
    record_counts: { equipment: 2, telemetry: 288 },
    schema_version: 1,
    snapshot_id: "demo-v1",
    source_period_end: "2026-09-02T23:55:00Z",
    source_period_start: "2026-09-02T00:00:00Z",
  },
  overview: {
    availability: {
      available_intervals: 272,
      scheduled_intervals: 288,
      value: 0.9444444444444444,
    },
    schema_version: 1,
    terminal_id: "TM-001",
  },
  equipment: { status: "ready", records },
};

function renderEquipment(dataset: EquipmentDatasetState = snapshot.equipment!) {
  window.history.replaceState({}, "", "/#equipment");
  return render(<App loadData={() => Promise.resolve({ ...snapshot, equipment: dataset })} />);
}

describe("EquipmentPage", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/");
    snapshotCache.clear();
  });

  it.each([
    ["absent", "Equipment dataset not published"],
    ["unavailable", "Equipment data unavailable"],
    ["malformed", "Published equipment data malformed"],
    ["empty", "Equipment fleet empty"],
  ] as const)("shows the %s dataset state without fleet rows", async (status, heading) => {
    renderEquipment({ status });

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Equipment fleet" })).not.toBeInTheDocument();
  });

  it("shows no results while preserving the equipment search", async () => {
    window.history.replaceState({}, "", "/?search=rtg#equipment");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("status", { name: "No matching equipment" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search equipment ID" })).toHaveValue("rtg");
    expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
  });

  it("filters fleet rows with the global terminal filter", async () => {
    renderEquipment();
    expect(await screen.findByRole("button", { name: "Open equipment QC-001" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Terminal" }), {
      target: { value: "TM-002" },
    });

    expect(screen.getByRole("button", { name: "Open equipment QC-002" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open equipment QC-001" })).not.toBeInTheDocument();
  });

  it("writes search and sort changes to the equipment URL", async () => {
    window.history.replaceState({}, "", "/?terminal=TM-001#equipment");
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    const search = await screen.findByRole("searchbox", { name: "Search equipment ID" });

    fireEvent.change(search, { target: { value: "QC-00" } });
    fireEvent.click(screen.getByRole("button", { name: "Sort by Availability" }));
    fireEvent.click(screen.getByRole("button", { name: "Sort by Availability" }));

    expect(window.location.hash).toBe("#equipment");
    expect(window.location.search).toBe(
      "?terminal=TM-001&search=QC-00&sort=availability&direction=desc",
    );
    expect(screen.getByRole("columnheader", { name: "Availability" }))
      .toHaveAttribute("aria-sort", "descending");
  });

  it("opens detail and returns to the preserved fleet state", async () => {
    window.history.replaceState(
      {},
      "",
      "/?search=QC&sort=availability&direction=desc#equipment",
    );
    render(<App loadData={() => Promise.resolve(snapshot)} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open equipment QC-001" }));

    expect(screen.getByRole("heading", { name: "QC-001" })).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).get("equipment")).toBe("QC-001");

    fireEvent.click(screen.getByRole("button", { name: "Back to equipment fleet" }));

    expect(screen.getByRole("searchbox", { name: "Search equipment ID" })).toHaveValue("QC");
    expect(screen.getByRole("columnheader", { name: "Availability" }))
      .toHaveAttribute("aria-sort", "descending");
    expect(new URLSearchParams(window.location.search).has("equipment")).toBe(false);
  });

  it("restores URL-selected detail on browser navigation", async () => {
    renderEquipment();
    await screen.findByRole("table", { name: "Equipment fleet" });

    window.history.pushState({}, "", "/?equipment=QC-002#equipment");
    fireEvent.popState(window);

    expect(await screen.findByRole("heading", { name: "QC-002" })).toBeInTheDocument();
  });

  it("offers a fleet return when the URL selects an unknown equipment ID", async () => {
    window.history.replaceState({}, "", "/?equipment=QC-999#equipment");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("heading", { name: "Equipment not found" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to equipment fleet" }));
    expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
  });

  it("keeps the stale warning before equipment content", async () => {
    window.history.replaceState({}, "", "/#equipment");
    const { rerender } = render(<App loadData={() => Promise.resolve(snapshot)} />);
    await screen.findByRole("heading", { name: "Equipment fleet" });

    rerender(<App loadData={() => Promise.reject(new Error("network down"))} />);

    const warning = await screen.findByRole("status", { name: "Showing last valid snapshot" });
    const fleetHeading = screen.getByRole("heading", { name: "Equipment fleet" });
    expect(warning.compareDocumentPosition(fleetHeading) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });
});
