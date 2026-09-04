import { describe, expect, it } from "vitest";

import type { ManifestV1, QualityDatasetState } from "../../data/schema";
import { deriveHealthViewModel, STALE_AFTER_MS } from "./healthPresentation";

const manifest = {
  datasets: {
    overview: {
      path: "snapshots/demo-v2/overview.json",
      sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    },
  },
  generated_at: "2026-09-04T00:00:00Z",
  quality_status: "PASS",
  record_counts: { telemetry: 305 },
  schema_version: 1,
  snapshot_id: "demo-v2",
  source_period_end: "2026-09-04T00:00:00Z",
  source_period_start: "2026-09-03T00:00:00Z",
} as const satisfies ManifestV1;
const readyQuality = {
  status: "ready",
  data: {
    bronze_rows: 305,
    silver_rows: 305,
    quarantine_rows: 0,
    reason_counts: {},
    dbt_test_status: "PASS",
  },
} as const satisfies QualityDatasetState;

const now = (value: string) => new Date(value);

describe("deriveHealthViewModel", () => {
  it("presents healthy evidence at the exact stale threshold", () => {
    expect(deriveHealthViewModel(manifest, readyQuality, now("2026-09-05T00:00:00Z"))).toEqual({
      status: "healthy",
      message: "Data is healthy and current.",
      generatedAt: "2026-09-04T00:00:00Z",
      snapshotAgeMs: STALE_AFTER_MS,
      staleAfterMs: STALE_AFTER_MS,
      pipelineStatus: "PASS",
      counts: { bronze: 305, silver: 305, quarantine: 0, rejected: 0 },
      rejections: { rows: [], emptyMessage: "No rejected records." },
      reconciliation: {
        valid: true,
        layers: "Bronze rows reconcile with Silver and quarantine rows.",
        reasons: "Rejection reason totals reconcile with quarantine rows.",
      },
      rules: {
        staleAfter: "Stale after 24 hours",
        layerCounts: "Bronze = Silver + quarantine",
        rejectionTotals: "Rejection reasons = quarantine rows",
      },
    });
  });

  it("is stale one millisecond after the threshold", () => {
    const result = deriveHealthViewModel(manifest, readyQuality, now("2026-09-05T00:00:00.001Z"));
    expect(result.status).toBe("stale");
    expect(result.message).toBe("Data is healthy but stale.");
    expect(result.snapshotAgeMs).toBe(STALE_AFTER_MS + 1);
  });

  it("clamps an earlier clock to zero age", () => {
    expect(deriveHealthViewModel(manifest, readyQuality, now("2026-09-03T00:00:00Z")).snapshotAgeMs).toBe(0);
  });

  it("reports invalid layer counts before later evidence failures", () => {
    const quality = { ...readyQuality, data: { ...readyQuality.data, bronze_rows: 304 } };
    const result = deriveHealthViewModel(manifest, quality, now("2026-09-04T01:00:00Z"));
    expect(result.status).toBe("invalid");
    expect(result.message).toBe("Layer counts do not reconcile: Bronze rows must equal Silver rows plus quarantine rows.");
    expect(result.reconciliation.valid).toBe(false);
  });

  it("reports invalid rejection totals when reason counts exceed quarantine", () => {
    const quality = { ...readyQuality, data: { ...readyQuality.data, bronze_rows: 307, quarantine_rows: 2, reason_counts: { RANGE_INVALID: 3 } } };
    const result = deriveHealthViewModel(manifest, quality, now("2026-09-04T01:00:00Z"));
    expect(result.status).toBe("invalid");
    expect(result.message).toBe("Rejection totals do not reconcile: rejection reason counts must equal quarantine rows.");
  });

  it("sorts rejection rows by reason code and preserves explicit empty state", () => {
    const quality = { ...readyQuality, data: { ...readyQuality.data, bronze_rows: 308, silver_rows: 305, quarantine_rows: 3, reason_counts: { Z_LAST: 1, A_FIRST: 2 } } };
    const result = deriveHealthViewModel(manifest, quality, now("2026-09-04T01:00:00Z"));
    expect(result.rejections).toEqual({
      rows: [{ reason: "A_FIRST", count: 2 }, { reason: "Z_LAST", count: 1 }],
      emptyMessage: "No rejected records.",
    });
  });

  it.each(["absent", "unavailable", "malformed", "empty"] as const)("explains %s quality evidence", (status) => {
    const result = deriveHealthViewModel(manifest, { status }, now("2026-09-04T01:00:00Z"));
    expect(result.status).toBe("invalid");
    expect(result.message).toBe(`Quality evidence is ${status}.`);
    expect(result.pipelineStatus).toBe("Unavailable");
    expect(result.counts).toEqual({ bronze: null, silver: null, quarantine: null, rejected: null });
    expect(result.rejections).toEqual({ rows: [], emptyMessage: "Rejection evidence unavailable." });
  });
});
