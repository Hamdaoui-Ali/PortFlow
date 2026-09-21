import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ImportPayload,
  LocalApiClient,
  StreamRunsResponse,
} from "../../data/localApi";
import { LocalStreamRuns } from "./LocalStreamRuns";

const readyRunPayload = {
  status: "ready",
  limit: 10,
  runs: [{
    run_id: "dagster-run-001",
    topic: "portflow.telemetry",
    status: "succeeded",
    started_at: "2026-09-21T11:00:00.000000Z",
    finished_at: "2026-09-21T11:00:10.000000Z",
    duration_seconds: 10,
    consumed_messages: 2,
    bronze_rows: 1,
    committed_batches: 0,
    duplicate_messages: 0,
    late_messages: 0,
    dead_letters: null,
    error_type: null,
    error_message: null,
  }],
} satisfies StreamRunsResponse;

function resolvedApi(payload: StreamRunsResponse): LocalApiClient {
  return {
    getStatus: vi.fn(),
    getSchema: vi.fn(),
    getStreamRuns: vi.fn().mockResolvedValue(payload),
    seed: vi.fn(),
    importRecords: vi.fn<(payload: ImportPayload) => Promise<unknown>>(),
    refresh: vi.fn(),
  } as unknown as LocalApiClient;
}

function deferredApi(): {
  api: LocalApiClient;
  resolveAfterAbort: () => void;
} {
  let resolvePending: (payload: StreamRunsResponse) => void = () => undefined;
  const pending = new Promise<StreamRunsResponse>((resolve) => {
    resolvePending = resolve;
  });
  return {
    api: {
      getStatus: vi.fn(),
      getSchema: vi.fn(),
      getStreamRuns: vi.fn().mockReturnValue(pending),
      seed: vi.fn(),
      importRecords: vi.fn(),
      refresh: vi.fn(),
    } as unknown as LocalApiClient,
    resolveAfterAbort: () => resolvePending({ status: "absent", limit: 10, runs: [] }),
  };
}

describe("LocalStreamRuns", () => {
  it("shows a checking message while the request is pending", () => {
    const api = resolvedApi(readyRunPayload);
    vi.mocked(api.getStreamRuns).mockReturnValue(new Promise<StreamRunsResponse>(() => {}));

    render(<LocalStreamRuns api={api} />);

    expect(screen.getByRole("status", { name: "Checking local stream runs" })).toBeInTheDocument();
  });

  it("explains an absent state without marking Data Health invalid", async () => {
    render(<LocalStreamRuns api={resolvedApi({ status: "absent", limit: 10, runs: [] })} />);

    expect(await screen.findByText("No local stream runs yet.")).toBeInTheDocument();
    expect(screen.queryByText("Invalid")).not.toBeInTheDocument();
  });

  it("renders a ready table with accessible status and nullable counters", async () => {
    render(<LocalStreamRuns api={resolvedApi(readyRunPayload)} />);

    const table = await screen.findByRole("table", { name: "Latest stream runs" });
    expect(within(table).getByRole("row", { name: /Succeeded.*dagster-run-001/ })).toBeInTheDocument();
    expect(within(table).getByText("Unavailable")).toBeInTheDocument();
    expect(within(table).getByText("2")).toBeInTheDocument();
    expect(within(table).getByText("portflow.telemetry")).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Status" })).toBeInTheDocument();
  });

  it("renders failed error detail as escaped text", async () => {
    render(<LocalStreamRuns api={resolvedApi({
      status: "ready",
      limit: 10,
      runs: [{
        ...readyRunPayload.runs[0],
        status: "failed",
        error_type: "ConsumerError",
        error_message: "<script>alert('x')</script>",
      }],
    })} />);

    expect(await screen.findByText("ConsumerError: <script>alert('x')</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).not.toBeInTheDocument();
  });

  it.each(["malformed", "unavailable"] as const)("shows a bounded %s state", async (status) => {
    render(<LocalStreamRuns api={resolvedApi({ status, limit: 10, runs: [] })} />);

    expect(await screen.findByRole("status", {
      name: new RegExp(`Local stream run history is ${status}`),
    })).toBeInTheDocument();
  });

  it("does not update state after an aborted request", async () => {
    const request = deferredApi();
    const { unmount } = render(<LocalStreamRuns api={request.api} />);

    unmount();
    request.resolveAfterAbort();
    await Promise.resolve();

    expect(screen.queryByText("No local stream runs yet.")).not.toBeInTheDocument();
  });
});
