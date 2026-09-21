import { useEffect, useMemo, useState } from "react";

import { createLocalApi, type LocalApiClient, type StreamRunSummary, type StreamRunsResponse } from "../../data/localApi";

interface LocalStreamRunsProps {
  readonly api?: LocalApiClient;
}

interface RunRowProps {
  readonly run: StreamRunSummary;
}

function statusLabel(status: StreamRunSummary["status"]): string {
  return status[0].toUpperCase() + status.slice(1);
}

function formatCount(value: number | null): string {
  return value === null ? "Unavailable" : String(value);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return remainingSeconds === 0 ? `${minutes}m` : `${minutes}m ${remainingSeconds}s`;
}

function formatTimestamp(value: string): string {
  return value.replace("T", " ").replace(".000000Z", " UTC").replace("Z", " UTC");
}

function statusMessage(status: Exclude<StreamRunsResponse["status"], "ready">): string {
  if (status === "absent") return "No local stream runs yet.";
  return `Local stream run history is ${status}. The published snapshot is unchanged.`;
}

function RunRow({ run }: Readonly<RunRowProps>) {
  return (
    <tr>
      <th scope="row">
        <span className={`stream-run-status stream-run-status-${run.status}`}>{statusLabel(run.status)}</span>
        <span className="stream-run-id">{run.run_id}</span>
        <span className="stream-run-topic">{run.topic}</span>
        {run.error_message && (
          <span className="stream-run-error">
            {run.error_type ? `${run.error_type}: ` : ""}{run.error_message}
          </span>
        )}
      </th>
      <td><time dateTime={run.started_at}>{formatTimestamp(run.started_at)}</time></td>
      <td>{formatDuration(run.duration_seconds)}</td>
      <td>{formatCount(run.consumed_messages)}</td>
      <td>{formatCount(run.bronze_rows)}</td>
      <td>{formatCount(run.dead_letters)}</td>
    </tr>
  );
}

export function LocalStreamRuns({ api }: Readonly<LocalStreamRunsProps>) {
  const client = useMemo(() => api ?? createLocalApi(), [api]);
  const [response, setResponse] = useState<StreamRunsResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    void client.getStreamRuns(controller.signal).then((nextResponse) => {
      if (active && !controller.signal.aborted) setResponse(nextResponse);
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (active && !controller.signal.aborted) {
        setResponse({ status: "unavailable", limit: 10, runs: [] });
      }
    });

    return () => {
      active = false;
      controller.abort();
    };
  }, [client]);

  return (
    <section className="stream-runs" aria-labelledby="stream-runs-title">
      <header className="stream-runs-header">
        <p className="section-kicker">Local stream observability</p>
        <h2 id="stream-runs-title">Stream runs</h2>
        <p>Review the latest local consumer runs without changing the published snapshot or the Data Health assessment.</p>
      </header>

      {!response && (
        <output className="stream-runs-status" aria-label="Checking local stream runs">
          Checking local stream runs
        </output>
      )}

      {response && response.status !== "ready" && (
        <output
          className="stream-runs-status"
          aria-label={statusMessage(response.status)}
        >
          {statusMessage(response.status)}
        </output>
      )}

      {response?.status === "ready" && response.runs.length === 0 && (
        <output className="stream-runs-status">No local stream runs yet.</output>
      )}

      {response?.status === "ready" && response.runs.length > 0 && (
        <div className="stream-runs-table-scroll">
          <table className="stream-runs-table" aria-label="Latest stream runs">
            <caption>Latest stream runs</caption>
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Started</th>
                <th scope="col">Duration</th>
                <th scope="col">Messages</th>
                <th scope="col">Bronze rows</th>
                <th scope="col">Dead letters</th>
              </tr>
            </thead>
            <tbody>{response.runs.map((run) => <RunRow key={run.run_id} run={run} />)}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
