import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  LocalApiError,
  type LocalApiClient,
  type LocalSchemaResponse,
  type LocalStatus,
  type ImportPayload,
} from "../../data/localApi";
import { LocalDataWorkspace } from "./LocalDataWorkspace";

const readyStatus: LocalStatus = {
  api: "ready",
  database: "connected",
  schema: "ready",
  pipeline: "idle",
};

const schema: LocalSchemaResponse = {
  tables: [{
    table_name: "terminals",
    primary_key: "terminal_id",
    columns: [
      { name: "terminal_id", kind: "string", required: true, nullable: false, description: "Stable terminal identifier." },
      { name: "name", kind: "string", required: true, nullable: false, description: "Human-readable terminal name." },
      { name: "timezone_name", kind: "string", required: true, nullable: false, description: "IANA timezone name." },
      { name: "created_at", kind: "datetime", required: true, nullable: false, description: "UTC creation timestamp." },
      { name: "updated_at", kind: "datetime", required: true, nullable: false, description: "UTC update timestamp." },
    ],
  }],
};

class FakeLocalApi implements LocalApiClient {
  statusError: Error | null = null;
  importCalls: ImportPayload[] = [];
  refreshCalls = 0;

  getStatus(): Promise<LocalStatus> {
    return this.statusError ? Promise.reject(this.statusError) : Promise.resolve(readyStatus);
  }

  getSchema(): Promise<LocalSchemaResponse> {
    return Promise.resolve(schema);
  }

  seed(): Promise<{ seed: number; row_counts: Record<string, number>; digest_sha256: string }> {
    return Promise.resolve({ seed: 42, row_counts: { terminals: 1 }, digest_sha256: "demo" });
  }

  importRecords(payload: ImportPayload) {
    this.importCalls.push(payload);
    return Promise.resolve({
      table_name: payload.table,
      received_count: payload.records.length,
      inserted_count: payload.records.length,
      updated_count: 0,
    });
  }

  refresh() {
    this.refreshCalls += 1;
    return Promise.resolve({ manifest_path: "web/public/data/manifest.json" });
  }
}

describe("LocalDataWorkspace", () => {
  it("shows local API unavailable without hiding health content", async () => {
    const api = new FakeLocalApi();
    api.statusError = new LocalApiError(503, {
      error: "database_unavailable",
      message: "Local database unavailable",
    });

    render(<LocalDataWorkspace api={api} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Local API unavailable");
  });

  it("shows connected local data actions", async () => {
    render(<LocalDataWorkspace api={new FakeLocalApi()} />);

    expect(await screen.findByText("Local database connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seed demo data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate and import" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh snapshot" })).toBeInTheDocument();
  });

  it("imports JSON and reports counts", async () => {
    const api = new FakeLocalApi();
    render(<LocalDataWorkspace api={api} />);
    await screen.findByText("Local database connected");

    fireEvent.change(screen.getByLabelText("JSON records"), {
      target: {
        value: JSON.stringify([{
          terminal_id: "TM-101",
          name: "Local Terminal",
          timezone_name: "UTC",
          created_at: "2026-09-02T00:00:00Z",
          updated_at: "2026-09-02T00:00:02Z",
        }]),
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Validate and import" }));

    expect(await screen.findByText(/Imported 1 record:/)).toBeInTheDocument();
    expect(api.importCalls[0].table).toBe("terminals");
  });

  it("shows validation issues returned by the API", async () => {
    const api = new FakeLocalApi();
    api.importRecords = () => Promise.reject(new LocalApiError(400, {
      error: "validation",
      issues: [{
        row_index: 0,
        field: "terminal_id",
        code: "SCHEMA_INVALID",
        detail: "terminal_id has an invalid identifier",
      }],
    }));
    render(<LocalDataWorkspace api={api} />);
    await screen.findByText("Local database connected");

    fireEvent.change(screen.getByLabelText("JSON records"), { target: { value: "[]" } });
    fireEvent.click(screen.getByRole("button", { name: "Validate and import" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("terminal_id has an invalid identifier");
  });

  it("calls the snapshot callback after refresh", async () => {
    const api = new FakeLocalApi();
    let refreshCallbackCalls = 0;
    render(
      <LocalDataWorkspace
        api={api}
        onSnapshotRefresh={() => { refreshCallbackCalls += 1; }}
      />,
    );
    await screen.findByText("Local database connected");

    fireEvent.click(screen.getByRole("button", { name: "Refresh snapshot" }));

    await waitFor(() => expect(refreshCallbackCalls).toBe(1));
    expect(api.refreshCalls).toBe(1);
  });
});
