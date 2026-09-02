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
    const fullFetch = (input: string | URL | Request) =>
      Promise.resolve(Response.json(String(input).endsWith("manifest.json") ? fullManifest : overview));

    const snapshot = await loadSnapshot(fullFetch, "/PortFlow/");

    expect(snapshot.manifest.record_counts.equipment).toBe(1);
    expect(snapshot.overview.terminal_id).toBe("TM-001");
  });
});
