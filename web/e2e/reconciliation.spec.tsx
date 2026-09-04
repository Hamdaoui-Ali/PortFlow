import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { App } from "../src/app/App";
import { snapshotCache } from "../src/data/cache";
import { loadSnapshot, type SnapshotFetch } from "../src/data/loadSnapshot";
import type { SnapshotV1 } from "../src/data/schema";

const reconciliationDir = process.env.PORTFLOW_RECONCILIATION_DIR;

function createFileFetcher(root: string): SnapshotFetch {
  return async (input) => {
    const url = new URL(String(input));
    const relativePath = url.pathname.replace(/^\/data\//, "");
    const filePath = path.resolve(root, relativePath);
    const rootPath = path.resolve(root);
    if (filePath !== rootPath && !filePath.startsWith(`${rootPath}${path.sep}`)) {
      return new Response(null, { status: 400 });
    }
    try {
      return new Response(await readFile(filePath), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    } catch {
      return new Response(null, { status: 404 });
    }
  };
}

async function readReconciliationSnapshot(): Promise<SnapshotV1> {
  if (!reconciliationDir) {
    throw new Error("PORTFLOW_RECONCILIATION_DIR is required for snapshot reconciliation");
  }
  return loadSnapshot(createFileFetcher(reconciliationDir), "http://reconciliation/");
}

afterEach(() => {
  cleanup();
  window.history.replaceState({}, "", "/");
  snapshotCache.clear();
});

describe("generated snapshot browser reconciliation", () => {
  it("renders the generated Overview values", async () => {
    const snapshot = await readReconciliationSnapshot();
    window.history.replaceState({}, "", "/#overview");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect((await screen.findAllByText(`${(snapshot.overview.availability.value! * 100).toFixed(1)}%`)).length).toBeGreaterThan(0);
    expect(screen.getByText(`${snapshot.overview.throughput} moves`)).toBeInTheDocument();
  });

  it("renders the generated Equipment record", async () => {
    const snapshot = await readReconciliationSnapshot();
    window.history.replaceState({}, "", "/#equipment");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByText("QC-001")).toBeInTheDocument();
  });

  it("renders the generated Incident records", async () => {
    const snapshot = await readReconciliationSnapshot();
    window.history.replaceState({}, "", "/#incidents");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(snapshot.incidents?.status).toBe("ready");
    if (snapshot.incidents?.status !== "ready") return;
    for (const record of snapshot.incidents.records) {
      expect((await screen.findAllByRole("link", { name: record.incident_id })).length).toBeGreaterThan(0);
    }
  });

  it("renders the generated replay event", async () => {
    const snapshot = await readReconciliationSnapshot();
    window.history.replaceState({}, "", "/#live-demo");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("heading", { name: "Live Demo" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
    expect(snapshot.event_replay?.length).toBe(288);
    expect(await screen.findByRole("status")).toHaveTextContent(
      new RegExp(`${snapshot.event_replay?.[0].event_id}.*${snapshot.event_replay?.[0].equipment_id}`),
    );
  });

  it("renders generated Data Health evidence", async () => {
    const snapshot = await readReconciliationSnapshot();
    window.history.replaceState({}, "", "/#data-health");
    render(<App loadData={() => Promise.resolve(snapshot)} />);

    expect(await screen.findByRole("heading", { name: "Data Health" })).toBeInTheDocument();
    expect(screen.getAllByText(String(snapshot.quality?.status === "ready" ? snapshot.quality.data.bronze_rows : 0)).length).toBeGreaterThan(0);
  });
});
