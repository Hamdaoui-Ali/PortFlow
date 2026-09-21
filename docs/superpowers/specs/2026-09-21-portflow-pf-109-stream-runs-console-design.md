# PortFlow PF-109 Stream Runs Console

**Status:** Proposed for implementation on 2026-09-21

## Intent

PF-101 through PF-104 already produce a durable local stream-run record and a
Prometheus/Grafana observability path. An engineer running PortFlow locally
still has to leave the PortFlow Data Health page to answer a small, common
question: did the bounded Dagster consumer run, when did it run, and did it
produce duplicates, late messages, or dead letters?

PF-109 adds a compact, read-only Stream Runs section to the existing Data
Health page. It exposes only the latest bounded run history through the
loopback local API. It does not turn the public static site into a live
application and it does not replace Grafana for time-series investigation.

## Audience and success criteria

The audience is a developer or operator running the optional local streaming
stack. The feature succeeds when that person can open Data Health and, without
opening SQLite or Grafana, determine:

1. whether local stream-run state exists;
2. the status, start time, duration, and bounded outcome counters for the ten
   most recent Dagster-managed runs; and
3. whether the local run history is absent, readable, or unavailable.

The public browser must continue to render its committed snapshot when the
local API, PostgreSQL, broker, Dagster, and stream state file are unavailable.

## Scope

### Included

- A read-only `GET /api/stream-runs` endpoint on the existing loopback API.
- A small read model that reads the existing SQLite `stream_runs` table in
  read-only mode and never creates, updates, or deletes the state file.
- A fixed response limit of ten runs, ordered by `started_at DESC` and then
  `run_id DESC` for deterministic ties.
- A `Stream Runs` section rendered below the existing Data Health evidence and
  local data workspace.
- Explicit loading, absent, ready, malformed, and unavailable states.
- Accessible semantic table markup on desktop and horizontal scrolling on
  narrow screens, following the approved PortFlow UI system.
- Unit, API-dispatch, frontend-client, and frontend-component coverage.
- Local runbook and backlog documentation for the feature boundary.

### Excluded

- A new top-level navigation item or route.
- A public production API or any hosted service.
- Starting, stopping, retrying, or cancelling a stream run from the browser.
- Editing the `stream_runs` table or any SQLite state.
- Prometheus, Grafana, Dagster, Redpanda, or PostgreSQL schema changes.
- Full event-level inspection, arbitrary SQL filters, pagination, or log
  download.
- Changes to `web/public/data`, the snapshot manifest, or public data hashes.

## Product and visual design

Use the existing `Data Health` page because it is already the product's
operational trust surface and already contains local-only tooling. Do not add
another navigation label. Add one section with the following hierarchy:

1. kicker: `Local stream observability`;
2. heading: `Stream runs`;
3. one sentence explaining that this is optional local Dagster history and
   does not change the published snapshot;
4. a state message or the latest-runs table.

The table columns are:

| Column | Content |
|---|---|
| Status | Text label: Running, Succeeded, or Failed; never color alone |
| Started | Local run start timestamp rendered as a `<time>` element |
| Duration | Seconds for a completed run, or current elapsed duration for a running run |
| Messages | Consumed message count, or `Unavailable` for failed runs without counters |
| Bronze rows | Bronze row count, or `Unavailable` when the run has no report |
| Dead letters | Dead-letter count, or `Unavailable` when the run has no report |

The run ID and topic are shown as secondary text within the row rather than
additional columns. A failed row may show a bounded error type and message in
secondary text. Error text is treated as data and is never rendered as HTML.

The component uses existing divider-based table styling, `--cobalt` for
neutral data emphasis, `--teal` for succeeded state, `--warning` for running
state, and `--danger` for failed state. It keeps a minimum 44 px interactive
target for any control, although the first slice has no row action. On mobile,
the table remains a table inside an overflow container; it does not become a
card grid. Low-priority topic/error details may wrap or be hidden only if the
status and counters remain readable.

## Local API contract

### Configuration

Extend `LocalApiConfig` with an optional `stream_state_path: Path | None`.
When omitted, the service reads the repository-local disposable state file at
`data/bronze-stream/.stream-state.sqlite3`. `scripts/run_local_api.py` passes
the repository-root absolute path explicitly so the result does not depend on
the process working directory. Tests pass a temporary path.

### Request

```http
GET /api/stream-runs
```

The endpoint takes no query parameters and no request body. A fixed limit is
intentional: this local UI is a bounded status view, not a general database
query surface.

### Response

All successful endpoint responses use HTTP 200 and this JSON shape:

```json
{
  "status": "ready",
  "limit": 10,
  "runs": [
    {
      "run_id": "dagster-run-001",
      "topic": "portflow.telemetry",
      "status": "succeeded",
      "started_at": "2026-09-21T10:00:00Z",
      "finished_at": "2026-09-21T10:00:10Z",
      "duration_seconds": 10.0,
      "consumed_messages": 12,
      "bronze_rows": 10,
      "committed_batches": 5,
      "duplicate_messages": 1,
      "late_messages": 1,
      "dead_letters": 0,
      "error_type": null,
      "error_message": null
    }
  ]
}
```

The endpoint status is one of:

- `ready`: the state file was readable; `runs` may be empty;
- `absent`: no state file exists yet; `runs` is empty;
- `malformed`: the file or a stored row violates the stream-run contract;
- `unavailable`: the file could not be opened or read safely.

`malformed` and `unavailable` return an empty `runs` array. They do not make
the published snapshot invalid and do not cause the existing `/api/status`
database status to change.

Timestamps are UTC ISO-8601 strings. `duration_seconds` is non-negative and
uses the injected current UTC time for a running run. Counter fields are
integers or `null`; the UI maps `null` to `Unavailable`. `error_message` is
optional, whitespace-normalized, and bounded to 280 characters before it is
returned. The read model never returns `bronze_dir`, polling settings, or raw
SQLite errors.

### Read-only boundary

The reader opens the resolved SQLite URI with `mode=ro`, performs one bounded
`SELECT`, and closes the connection in `finally`. A missing file must not be
created. The reader must not call `StreamStateStore`, because that class
initializes and writes schema state. Any filesystem, SQLite, timestamp, or
stored-status failure is converted to the declared `malformed` or
`unavailable` result rather than leaking an exception or a traceback to the
browser.

## Frontend behavior

Add `getStreamRuns(signal?)` to the existing `LocalApiClient` and keep the
response types in `web/src/data/localApi.ts`. Add a focused
`LocalStreamRuns` component under `web/src/features/health/`.

The component fetches once on mount with an `AbortController` and renders:

- checking: `Checking local stream runs` as a status message;
- absent: `No local stream runs yet.` plus the optional Dagster/local-streaming
  explanation;
- ready with no rows: `No stream runs recorded yet.`;
- ready with rows: the semantic table described above;
- malformed or unavailable: a non-critical status message explaining that
  local run history cannot be read and that the published snapshot is still
  independent;
- aborted request: no state update after unmount.

The component must not make the Data Health page `aria-live`, must not mark
the snapshot invalid, and must not show a fake success state when the local
API is absent. The existing `LocalDataWorkspace` behavior remains unchanged.

## Error handling and security

- The endpoint is available only through the existing loopback server and its
  existing origin allowlist.
- No request-provided path, SQL, limit, or sort expression is accepted.
- No credentials, database URLs, absolute Bronze paths, stack traces, or raw
  SQLite messages are sent to the browser.
- Run IDs, topics, error types, and bounded error text are escaped by React's
  normal text rendering.
- Missing local state is an expected empty state, not a server error.
- Read failures remain visible as a bounded status message and do not affect
  the public snapshot contract.

## Verification

### Python

- Reader tests cover missing state without file creation, deterministic
  ordering and ten-row bounding, running duration, nullable counters,
  whitespace/error truncation, malformed status/timestamp, and byte-for-byte
  read-only preservation.
- Local API tests cover the new service method, `GET` route, empty/ready
  response, method rejection, and safe unavailable response.
- Existing observability, local API, and full Python suites remain green.

### Frontend

- Client tests cover the exact request path and typed response parsing.
- Component tests cover checking, absent, ready table, running/failed row
  text, malformed/unavailable state, and abort cleanup.
- Data Health integration tests confirm the new section does not change the
  snapshot status or existing Data Health evidence.
- Frontend typecheck, Vitest, build, and existing performance budgets remain
  green.

### Repository boundary

- `web/public/data` is byte-for-byte unchanged.
- The public route list is unchanged.
- Ruff, mypy, and SonarCloud-sensitive path/error handling remain clean.

## Documentation

Update `docs/runbooks/local-streaming.md` with the endpoint's local-only
boundary, the Data Health location, expected absent state, and the fact that
Grafana remains the detailed observability surface. Update `README.md` with a
short pointer. Add PF-109 to `docs/product/BACKLOG.md` as complete only after
the implementation and verification gates pass.
