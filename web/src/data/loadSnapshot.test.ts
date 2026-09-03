import { describe, expect, it } from "vitest";

import { loadSnapshot } from "./loadSnapshot";

const manifest = {
  datasets: {
    overview: {
      path: "snapshots/demo-v1/overview.json",
      sha256: "13046979b100d92a07ea391dbbe003a3e58333da33916db1bb62666a88c7320d",
    },
  },
  generated_at: "2026-09-02T23:55:02Z",
  quality_status: "PASS",
  record_counts: { telemetry: 288 },
  schema_version: 1,
  snapshot_id: "demo-v1",
  source_period_end: "2026-09-02T23:55:00Z",
  source_period_start: "2026-09-02T00:00:00Z",
};

const overview = {
  availability: {
    available_intervals: 272,
    scheduled_intervals: 288,
    value: 0.9444444444444444,
  },
  schema_version: 1,
  terminal_id: "TM-001",
};

const equipment = [
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
];

function successfulFetch(input: string | URL | Request): Promise<Response> {
  const url = String(input);
  if (url.endsWith("manifest.json")) {
    return Promise.resolve(Response.json(manifest));
  }
  if (url.endsWith("snapshots/demo-v1/overview.json")) {
    return Promise.resolve(Response.json(overview));
  }
  return Promise.resolve(new Response(null, { status: 404 }));
}

describe("loadSnapshot", () => {
  it("loads and validates the manifest before its overview dataset", async () => {
    const snapshot = await loadSnapshot(successfulFetch, "/PortFlow/");

    expect(snapshot.manifest.snapshot_id).toBe("demo-v1");
    expect(snapshot.overview.availability.value).toBe(0.9444444444444444);
  });

  it("reports an absent equipment dataset when the manifest has no equipment entry", async () => {
    const snapshot = await loadSnapshot(successfulFetch, "/PortFlow/");

    expect(snapshot.equipment).toEqual({ status: "absent" });
  });

  it("loads and validates equipment records without rejecting the overview", async () => {
    const equipmentManifest = {
      ...manifest,
      datasets: {
        ...manifest.datasets,
        equipment: {
          path: "snapshots/demo-v1/equipment.json",
          sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
      },
      record_counts: { telemetry: 288, equipment: 1 },
    };
    const equipmentFetch = (input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(Response.json(
        url.endsWith("manifest.json") ? equipmentManifest :
          url.endsWith("equipment.json") ? equipment : overview,
      ));
    };

    const snapshot = await loadSnapshot(equipmentFetch, "/PortFlow/");

    expect(snapshot.equipment).toEqual({ status: "ready", records: equipment });
    expect(snapshot.overview).toEqual(overview);
  });

  it("reports an unavailable equipment dataset when its fetch fails", async () => {
    const equipmentManifest = {
      ...manifest,
      datasets: {
        ...manifest.datasets,
        equipment: {
          path: "snapshots/demo-v1/equipment.json",
          sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
      },
    };
    const equipmentFetch = (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("manifest.json")) return Promise.resolve(Response.json(equipmentManifest));
      if (url.endsWith("equipment.json")) return Promise.reject(new Error("network down"));
      return Promise.resolve(Response.json(overview));
    };

    const snapshot = await loadSnapshot(equipmentFetch, "/PortFlow/");

    expect(snapshot.equipment).toEqual({ status: "unavailable" });
    expect(snapshot.overview).toEqual(overview);
  });

  it("reports a malformed equipment dataset when a record shape is invalid", async () => {
    const equipmentManifest = {
      ...manifest,
      datasets: {
        ...manifest.datasets,
        equipment: {
          path: "snapshots/demo-v1/equipment.json",
          sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
      },
    };
    const equipmentFetch = (input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(Response.json(
        url.endsWith("manifest.json") ? equipmentManifest :
          url.endsWith("equipment.json") ? [{ ...equipment[0], unexpected: true }] : overview,
      ));
    };

    const snapshot = await loadSnapshot(equipmentFetch, "/PortFlow/");

    expect(snapshot.equipment).toEqual({ status: "malformed" });
    expect(snapshot.overview).toEqual(overview);
  });

  it("reports an empty equipment dataset when the validated array has no records", async () => {
    const equipmentManifest = {
      ...manifest,
      datasets: {
        ...manifest.datasets,
        equipment: {
          path: "snapshots/demo-v1/equipment.json",
          sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
      },
    };
    const equipmentFetch = (input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(Response.json(
        url.endsWith("manifest.json") ? equipmentManifest :
          url.endsWith("equipment.json") ? [] : overview,
      ));
    };

    const snapshot = await loadSnapshot(equipmentFetch, "/PortFlow/");

    expect(snapshot.equipment).toEqual({ status: "empty" });
    expect(snapshot.overview).toEqual(overview);
  });

  it("rejects an unsupported manifest schema version", async () => {
    const invalidFetch = () => Promise.resolve(Response.json({ ...manifest, schema_version: 2 }));

    await expect(loadSnapshot(invalidFetch, "/PortFlow/")).rejects.toThrow(
      /manifest did not match schema version 1/i,
    );
  });

  it("rejects an unsafe dataset path", async () => {
    const unsafeManifest = {
      ...manifest,
      datasets: { overview: { ...manifest.datasets.overview, path: "../private.json" } },
    };
    const unsafeFetch = () => Promise.resolve(Response.json(unsafeManifest));

    await expect(loadSnapshot(unsafeFetch, "/PortFlow/")).rejects.toThrow(
      /manifest did not match schema version 1/i,
    );
  });

  it("rejects an availability value that contradicts its interval counts", async () => {
    const invalidOverview = {
      ...overview,
      availability: { ...overview.availability, value: null },
    };
    const invalidFetch = (input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(Response.json(url.endsWith("manifest.json") ? manifest : invalidOverview));
    };

    await expect(loadSnapshot(invalidFetch, "/PortFlow/")).rejects.toThrow(
      /overview dataset did not match schema version 1/i,
    );
  });

  it("accepts optional R2 dataset entries without breaking the overview loader", async () => {
    const fullManifest = {
      ...manifest,
      datasets: {
        ...manifest.datasets,
        equipment: {
          path: "snapshots/demo-v1/equipment.json",
          sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
        incidents: {
          path: "snapshots/demo-v1/incidents.json",
          sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        },
        event_replay: {
          path: "snapshots/demo-v1/event_replay.json",
          sha256: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        },
        quality: {
          path: "snapshots/demo-v1/quality.json",
          sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        },
      },
      record_counts: {
        telemetry: 288,
        equipment: 1,
        incidents: 2,
        event_replay: 288,
        quality: 1,
      },
    };
    const replay = [{
      available: true,
      equipment_id: "QC-001",
      event_id: "evt-1",
      event_timestamp: "2026-09-02T00:00:00Z",
      state: "ACTIVE",
      terminal_id: "TM-001",
    }];
    const fullFetch = (input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(Response.json(
        url.endsWith("manifest.json") ? fullManifest :
          url.endsWith("event_replay.json") ? replay : overview,
      ));
    };

    const snapshot = await loadSnapshot(fullFetch, "/PortFlow/");

    expect(snapshot.manifest.record_counts.equipment).toBe(1);
    expect(snapshot.overview.terminal_id).toBe("TM-001");
    expect(snapshot.event_replay).toHaveLength(1);
  });
});
