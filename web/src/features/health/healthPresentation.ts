import type { ManifestV1, QualityDatasetState, QualityV1 } from "../../data/schema";

export const STALE_AFTER_MS = 24 * 60 * 60 * 1000;

type HealthStatus = "healthy" | "stale" | "invalid";

export interface HealthViewModel {
  status: HealthStatus;
  message: string;
  generatedAt: string;
  snapshotAgeMs: number;
  staleAfterMs: number;
  pipelineStatus: string;
  counts: {
    bronze: number | null;
    silver: number | null;
    quarantine: number | null;
    rejected: number | null;
  };
  rejections: {
    rows: Array<{ reason: string; count: number }>;
    emptyMessage: string;
  };
  reconciliation: {
    valid: boolean;
    layers: string;
    reasons: string;
  };
  rules: {
    staleAfter: string;
    layerCounts: string;
    rejectionTotals: string;
  };
}

const rules = {
  staleAfter: "Stale after 24 hours",
  layerCounts: "Bronze = Silver + quarantine",
  rejectionTotals: "Rejection reasons = quarantine rows",
};

const emptyRejections = { rows: [], emptyMessage: "No rejected records." };

function snapshotAgeMs(manifest: ManifestV1, now: Date): number {
  return Math.max(0, now.getTime() - Date.parse(manifest.generated_at));
}

function unavailableModel(manifest: ManifestV1, now: Date, status: QualityDatasetState["status"]): HealthViewModel {
  return {
    status: "invalid",
    message: `Quality evidence is ${status}.`,
    generatedAt: manifest.generated_at,
    snapshotAgeMs: snapshotAgeMs(manifest, now),
    staleAfterMs: STALE_AFTER_MS,
    pipelineStatus: "Unavailable",
    counts: { bronze: null, silver: null, quarantine: null, rejected: null },
    rejections: emptyRejections,
    reconciliation: { valid: false, layers: "Layer reconciliation is unavailable.", reasons: "Rejection reconciliation is unavailable." },
    rules,
  };
}

function rejectionRows(data: QualityV1): Array<{ reason: string; count: number }> {
  return Object.entries(data.reason_counts)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([reason, count]) => ({ reason, count }));
}

export function deriveHealthViewModel(
  manifest: ManifestV1,
  quality: QualityDatasetState,
  now: Date,
): HealthViewModel {
  const age = snapshotAgeMs(manifest, now);
  if (quality.status !== "ready") return unavailableModel(manifest, now, quality.status);

  const { data } = quality;
  const rows = rejectionRows(data);
  const layerCountsValid = data.bronze_rows === data.silver_rows + data.quarantine_rows;
  const reasonTotal = rows.reduce((total, row) => total + row.count, 0);
  const reasonsValid = reasonTotal === data.quarantine_rows;
  const reconciliation = {
    valid: layerCountsValid && reasonsValid,
    layers: layerCountsValid
      ? "Bronze rows reconcile with Silver and quarantine rows."
      : "Layer counts do not reconcile.",
    reasons: reasonsValid
      ? "Rejection reason totals reconcile with quarantine rows."
      : "Rejection reason totals do not reconcile.",
  };

  let status: HealthStatus = age > STALE_AFTER_MS ? "stale" : "healthy";
  let message = status === "stale" ? "Data is healthy but stale." : "Data is healthy and current.";
  if (data.dbt_test_status !== "PASS") {
    status = "invalid";
    message = "Pipeline quality checks did not pass.";
  } else if (!layerCountsValid) {
    status = "invalid";
    message = "Layer counts do not reconcile: Bronze rows must equal Silver rows plus quarantine rows.";
  } else if (!reasonsValid) {
    status = "invalid";
    message = "Rejection totals do not reconcile: rejection reason counts must equal quarantine rows.";
  }

  return {
    status,
    message,
    generatedAt: manifest.generated_at,
    snapshotAgeMs: age,
    staleAfterMs: STALE_AFTER_MS,
    pipelineStatus: data.dbt_test_status,
    counts: {
      bronze: data.bronze_rows,
      silver: data.silver_rows,
      quarantine: data.quarantine_rows,
      rejected: reasonTotal,
    },
    rejections: { rows, emptyMessage: "No rejected records." },
    reconciliation,
    rules,
  };
}
