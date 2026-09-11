import { describe, expect, it } from "vitest";

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
