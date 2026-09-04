import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ManifestV1, QualityDatasetState } from "../../data/schema";
import { DataHealthPage } from "./DataHealthPage";

const manifest = {
  generated_at: "2026-09-04T00:00:00Z",
  snapshot_id: "demo-v2",
} as ManifestV1;

const healthyQuality = {
  status: "ready",
  data: {
    bronze_rows: 305,
    silver_rows: 305,
    quarantine_rows: 0,
    reason_counts: {},
    dbt_test_status: "PASS",
  },
} as const satisfies QualityDatasetState;

const invalidQuality = {
  status: "ready",
  data: {
    bronze_rows: 304,
    silver_rows: 305,
    quarantine_rows: 0,
    reason_counts: {},
    dbt_test_status: "PASS",
  },
} as const satisfies QualityDatasetState;

describe("DataHealthPage", () => {
  const renderPage = (quality: QualityDatasetState) => render(<main><DataHealthPage manifest={manifest} quality={quality} /></main>);

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-04T12:00:00Z"));
  });

  afterEach(() => vi.useRealTimers());

  it("renders healthy status, counts, empty rejections, and semantic table", () => {
    renderPage(healthyQuality);

    expect(screen.getByRole("heading", { name: "Data Health" })).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getAllByText("305")).toHaveLength(2);
    expect(screen.getByText("No rejected records")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /rejection reasons/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Reason" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Rejected records" })).toBeInTheDocument();
  });

  it("explains stale evidence and exposes generated metadata and threshold", () => {
    vi.setSystemTime(new Date("2026-09-05T00:00:00.001Z"));
    renderPage(healthyQuality);

    expect(screen.getByText("Stale")).toBeInTheDocument();
    expect(screen.getByText("Data is healthy but stale.")).toBeInTheDocument();
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
    expect(document.querySelector('time[datetime="2026-09-04T00:00:00Z"]')).toBeInTheDocument();
    expect(screen.getByText("Stale after 24 hours")).toBeInTheDocument();
  });

  it("explains invalid pipeline evidence and does not mark main or table live", () => {
    renderPage(invalidQuality);

    expect(screen.getByText("Invalid")).toBeInTheDocument();
    expect(screen.getByText("Layer counts do not reconcile: Bronze rows must equal Silver rows plus quarantine rows.")).toBeInTheDocument();
    expect(screen.getByText("Pipeline status")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByRole("main")).not.toHaveAttribute("aria-live");
    expect(screen.getByRole("table")).not.toHaveAttribute("aria-live");
  });

  it.each(["absent", "unavailable", "malformed", "empty"] as const)("explains missing quality state: %s", (status) => {
    renderPage({ status });

    expect(screen.getByText("Invalid")).toBeInTheDocument();
    expect(screen.getByText(`Quality evidence is ${status}.`)).toBeInTheDocument();
    expect(screen.getByText("Pipeline status")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });
});
