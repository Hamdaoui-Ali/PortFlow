import { describe, expect, it, vi } from "vitest";

import { createLocalApi, LocalApiError } from "./localApi";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("local API client", () => {
  it("reads local status", async () => {
    const requests: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetcher = async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ input, init });
      return jsonResponse({
        api: "ready",
        database: "connected",
        schema: "ready",
        pipeline: "idle",
      });
    };

    const status = await createLocalApi("/api", fetcher).getStatus();

    expect(status.database).toBe("connected");
    expect(requests).toHaveLength(1);
    expect(String(requests[0].input)).toBe("/api/status");
    expect(requests[0].init?.method).toBe("GET");
  });

  it("reads the bounded stream-run history with an abort signal", async () => {
    const payload = {
      status: "ready" as const,
      limit: 10,
      runs: [{
        run_id: "run-001",
        topic: "portflow.telemetry",
        status: "succeeded" as const,
        started_at: "2026-09-21T11:00:00.000000Z",
        finished_at: "2026-09-21T11:00:10.000000Z",
        duration_seconds: 10,
        consumed_messages: 12,
        bronze_rows: 10,
        committed_batches: 5,
        duplicate_messages: 1,
        late_messages: 1,
        dead_letters: 0,
        error_type: null,
        error_message: null,
      }],
    };
    const fetcher = vi.fn(async () => jsonResponse(payload));
    const client = createLocalApi("/api", fetcher);
    const signal = new AbortController().signal;

    await expect(client.getStreamRuns(signal)).resolves.toEqual(payload);
    expect(fetcher).toHaveBeenCalledWith("/api/stream-runs", {
      method: "GET",
      signal,
    });
  });

  it("keeps non-success stream-run responses as LocalApiError", async () => {
    const fetcher = vi.fn(async () => jsonResponse({
      error: "server_error",
      message: "Local API request failed",
    }, 500));

    await expect(createLocalApi("/api", fetcher).getStreamRuns()).rejects.toMatchObject({
      name: "LocalApiError",
      status: 500,
      body: {
        error: "server_error",
      },
    } satisfies Partial<LocalApiError>);
  });

  it("posts an import payload as JSON", async () => {
    const payload = {
      table: "terminals",
      records: [{
        terminal_id: "TM-101",
        name: "Local Terminal",
      }],
    };
    const fetcher = async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/api/import");
      expect(init?.method).toBe("POST");
      expect(init?.headers).toEqual({ "Content-Type": "application/json" });
      expect(JSON.parse(String(init?.body))).toEqual(payload);
      return jsonResponse({
        table_name: "terminals",
        received_count: 1,
        inserted_count: 1,
        updated_count: 0,
      });
    };

    const result = await createLocalApi("/api", fetcher).importRecords(payload);

    expect(result.inserted_count).toBe(1);
  });

  it("surfaces the safe validation body for a failed request", async () => {
    const fetcher = async () => jsonResponse({
      error: "validation",
      issues: [{ row_index: 0, field: "terminal_id", code: "SCHEMA_INVALID" }],
    }, 400);

    await expect(createLocalApi("/api", fetcher).importRecords({
      table: "terminals",
      records: [],
    })).rejects.toMatchObject({
      name: "LocalApiError",
      status: 400,
      body: {
        error: "validation",
      },
    } satisfies Partial<LocalApiError>);
  });
});
