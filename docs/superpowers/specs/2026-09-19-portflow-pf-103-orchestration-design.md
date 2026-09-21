# PF-103 Orchestration and Run Metadata Design

**Status:** Draft for review
**Date:** 2026-09-19
**Parent slice:** PF-102 stream safety
**Next slice after this:** PF-104 engineering observability

## Goal

Add an opt-in local Dagster entry point for the existing bounded telemetry
consumer and persist one auditable run record for every Dagster-managed
execution. PF-103 must make a stream run easy to start, inspect, and diagnose
without changing the consumer's commit safety, the public static product, or
the permanent-$0 deployment boundary.

The first PF-103 slice is intentionally small: one manually triggered consumer
job, one run record per job execution, and no producer orchestration. The
existing producer and consumer CLIs remain available for broker-level work.

## Approved decisions

- Orchestrate the **streaming path**, not the batch PostgreSQL-to-Gold path.
- Record metadata at the **run level**, not per batch or per message.
- Extend the existing disposable **SQLite state store** with a `stream_runs`
  table.
- Orchestrate the **bounded consumer run only**; the producer remains an
  existing CLI.
- Use Dagster's `context.run_id` as the canonical run ID.
- Record `running`, `succeeded`, and `failed` lifecycle states.
- Record inputs, result counters, timestamps, and terminal error details.
- Keep Dagster in an optional orchestration dependency group.
- Trigger runs manually through the Dagster CLI or local UI; add no daemon,
  schedule, sensor, or always-on service.
- Create `stream_runs` rows for Dagster-managed executions only. Preserve the
  existing non-Dagster CLI behavior.

## Current boundary

PF-102 currently provides:

- a canonical telemetry event codec and typed producer/consumer protocols;
- a bounded manual-commit consumer in
  `src/portflow/streaming/consumer.py`;
- durable event identity, dead-letter, and watermark state in
  `src/portflow/streaming/state.py`;
- deterministic Bronze writes through the existing ingestion writer;
- a local Redpanda Compose profile and broker-optional integration tests;
- bounded producer and consumer entry points under `scripts/`.

The consumer already accepts a caller-provided `run_id` for canonical DLQ
envelopes and returns a `ConsumeReport`. PF-103 will use those existing
interfaces rather than moving stream decisions into Dagster code.

## Non-goals

- No React, CSS, route, public snapshot, or public-data changes.
- No browser connection to Dagster, Redpanda, Kafka, SQLite, Parquet, or the
  local consumer.
- No orchestration of the deterministic producer in this slice.
- No orchestration of the PostgreSQL, Silver, Gold, dbt, or public export path.
- No automatic retries, schedules, sensors, or background daemons.
- No Dagster service in `compose.yaml` and no persistent hosted Dagster
  deployment.
- No change to the PF-102 at-least-once transport guarantee.
- No per-message run metadata, distributed tracing, metrics backend, or public
  streaming UI.
- No automatic DLQ reprocessing, Schema Registry, Avro/Protobuf, transactions,
  authentication, or multi-broker deployment.
- No migration of historical PF-101/PF-102 state databases beyond adding the
  new table when the current store initializes.

## Design choices

### 1. Typed Dagster job around the existing consumer

Add an optional orchestration package under `src/portflow/orchestration/`.
Expose one `stream_consumer_job` whose single consumer op calls a typed
application function that reuses `consume_telemetry_stream()`.

The orchestration layer owns only lifecycle coordination:

1. resolve non-secret run configuration;
2. obtain Dagster's `context.run_id`;
3. create the SQLite `running` record;
4. construct the existing consumer, DLQ producer, and state-store clients;
5. call the existing bounded consumer;
6. record success or failure;
7. close owned resources without masking the primary error.

The stream consumer remains responsible for polling, validation, duplicate and
lateness classification, Bronze/DLQ ordering, source commits, and
`ConsumeReport` values. This keeps the PF-102 safety boundary transport-aware
and independently testable.

The existing `scripts/run_stream_consumer.py` remains a supported non-Dagster
entry point. Shared construction or execution helpers may be extracted to
avoid duplicated wiring, but the CLI must not begin writing `stream_runs`
records as a side effect of this slice.

### 2. SQLite run metadata contract

Add a `stream_runs` table to the existing
`configured-bronze-dir/.stream-state.sqlite3` database:

```sql
CREATE TABLE stream_runs (
    run_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    bronze_dir TEXT NOT NULL,
    batch_size INTEGER NOT NULL,
    max_messages INTEGER NOT NULL,
    allowed_lateness_seconds INTEGER NOT NULL,
    poll_timeout_seconds REAL NOT NULL,
    idle_timeout_seconds REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    consumed_count INTEGER,
    bronze_row_count INTEGER,
    committed_count INTEGER,
    batch_count INTEGER,
    duplicate_count INTEGER,
    late_count INTEGER,
    dead_letter_count INTEGER,
    error_type TEXT,
    error_message TEXT
);
```

The run ID is unique and comes from Dagster. Transport credentials and broker
addresses are not persisted. All non-secret values that affect execution are
normalized into the row so a reviewer can understand how the run was invoked.

Successful rows contain every `ConsumeReport` counter and a UTC
`finished_at`. Failed rows contain the terminal exception type and message and
may leave result counters null because a failed consumer call does not return a
complete report. The schema does not claim that null counters mean zero work;
the source offset, Bronze state, and DLQ state remain the authoritative safety
records.

The state store exposes typed operations rather than leaking SQLite objects:

```python
from datetime import datetime
from pathlib import Path


class StreamStateStore:
    def start_run(self, *, run_id: str, inputs: StreamRunInputs) -> None: ...

    def record_run_success(
        self,
        *,
        run_id: str,
        report: ConsumeReport,
        finished_at: datetime,
    ) -> None: ...

    def record_run_failure(
        self,
        *,
        run_id: str,
        error_type: str,
        error_message: str,
        finished_at: datetime,
    ) -> None: ...

    def get_run(self, run_id: str) -> StreamRun | None: ...
```

The concrete `StreamRunInputs` and `StreamRun` dataclasses should be frozen,
slot-based, and typed like the existing state models. Lifecycle updates must
be atomic and must reject an unknown run ID or an invalid terminal transition.
Dagster run IDs are unique, so a duplicate start is an explicit state error
rather than an implicit overwrite.

### 3. Lifecycle and error semantics

The op inserts `running` before creating the broker clients. On a successful
consumer return, it stores the report and marks the row `succeeded`. On any
consumer or resource error, it records `failed` and re-raises the original
exception.

The sequence is:

```text
Dagster context.run_id
        |
        v
SQLite start_run(status=running)
        |
        v
existing consume_telemetry_stream(..., run_id=context.run_id)
        |
   +----+----+
   |         |
success   exception
   |         |
   v         v
record    record
succeeded failed
   |         |
return    re-raise original error
```

Run metadata is separate from per-batch stream commits. A failure while
recording failure metadata must never replace the original consumer exception.
If a terminal success update fails after the consumer has committed its final
batch, the Dagster op reports the metadata error; the underlying Bronze,
processed-event, watermark, and source-commit records remain authoritative.

No automatic retry policy is configured. A later manual run is a new Dagster
run ID and follows the existing PF-102 duplicate and at-least-once rules.

Cleanup follows the current consumer contract: owned clients are closed in a
`finally` path, and cleanup failures do not hide a primary processing error.

### 4. Dagster configuration and manual execution

The optional orchestration dependency group provides the Dagster runtime and
the local UI component when UI execution is desired. The base PortFlow install
does not import Dagster or require it for existing tests and scripts.

The job accepts explicit, non-secret run configuration for:

- `topic`;
- `bronze_dir`;
- `batch_size`;
- `max_messages`;
- `allowed_lateness_seconds`;
- `poll_timeout_seconds`;
- `idle_timeout_seconds`.

Broker addresses, group identity, and other connection properties continue to
come from the existing `StreamingConfig` environment variables. The resolved
topic and other non-secret values are copied into `stream_runs` before the
consumer starts.

The runbook will document a manual local execution path using Dagster's CLI
and an optional local UI path. Both paths invoke the same `stream_consumer_job`.
There is no schedule or daemon to keep running after the command exits.

### 5. File and module map

| File | Responsibility |
| --- | --- |
| `src/portflow/orchestration/__init__.py` | Keep the optional orchestration package boundary small. |
| `src/portflow/orchestration/streaming.py` | Define the Dagster job/op and typed lifecycle coordination. |
| `src/portflow/streaming/state.py` | Add the run schema, typed run models, and lifecycle operations. |
| `src/portflow/streaming/consumer.py` | Preserve the existing stream safety behavior and report contract. |
| `scripts/run_stream_consumer.py` | Preserve the non-Dagster CLI and its current run-ID behavior. |
| `pyproject.toml` | Add an optional orchestration dependency group. |
| `docs/runbooks/local-streaming.md` | Document optional installation, manual Dagster execution, and run inspection. |
| `tests/unit/test_streaming_state.py` | Test the run table, lifecycle transitions, atomic updates, and restart behavior. |
| `tests/unit/test_streaming_orchestration.py` | Test run-ID propagation, success, failure, cleanup, and optional Dagster job wiring. |
| `tests/streaming/test_redpanda.py` | Keep the existing broker test; add one opt-in orchestrated consumer path only if it adds coverage not available in unit tests. |
| `docs/product/BACKLOG.md` | Record PF-103 only after the implementation gate passes. |
| `CHANGELOG.md` | Record the opt-in local orchestration capability. |
| `README.md` | Keep the local streaming boundary and optional dependency clear. |

No frontend or `web/public/data` files are in scope.

## Error handling

- A malformed message, late event, duplicate conflict, Bronze error, DLQ error,
  or broker error continues to follow PF-102 behavior.
- A consumer error marks the Dagster run `failed` and is re-raised.
- A failure to write the failed-run row is chained or logged without masking
  the original exception.
- A failure to write a successful terminal row fails the Dagster op, but does
  not roll back already committed stream output; the run record and stream
  state remain inspectable for diagnosis.
- Unknown or duplicate run IDs, invalid transitions, malformed run inputs, and
  invalid timestamps raise `StreamStateError` or `ValueError` before unsafe
  state changes.
- Run metadata never causes a source offset to be committed. The existing
  consumer ordering remains the only commit authority.

## Testing and acceptance

### Unit tests

- The SQLite initializer creates `stream_runs` alongside the existing PF-102
  tables without changing old event-state behavior.
- `start_run` persists all approved normalized inputs and `running` status.
- `record_run_success` persists all `ConsumeReport` counters and a terminal
  timestamp.
- `record_run_failure` persists the exception type/message and a terminal
  timestamp.
- Unknown run IDs, duplicate starts, and repeated terminal transitions fail
  safely without overwriting existing metadata.
- Reopening the same state database returns the same run record.
- The orchestration op passes Dagster's run ID to the consumer and writes the
  matching SQLite row.
- A successful fake consumer produces a `succeeded` row.
- A failing fake consumer produces a `failed` row and re-raises the original
  exception.
- Cleanup is performed on both success and failure, and cleanup errors do not
  mask the processing error.
- The optional orchestration import is isolated so the base test suite remains
  valid without Dagster installed.

### Optional broker verification

When Docker and the streaming Compose profile are available, an opt-in test
may execute the real Dagster consumer job against Redpanda and verify the
resulting run row together with the existing Bronze, DLQ, and commit checks.
The broker-free unit suite remains the required default check for this slice.

### Definition of done

PF-103 is complete when:

- the optional Dagster job can be run manually against the local Redpanda
  profile;
- every Dagster-managed run has a durable `running` and terminal lifecycle
  record unless the SQLite store itself is unavailable;
- success and failure metadata are tested without changing PF-102 commit
  behavior;
- the existing CLI and public static product remain backward-compatible;
- focused tests, full Python tests, Ruff, mypy, and the optional orchestration
  checks pass;
- the local streaming runbook documents installation, execution, inspection,
  and disposable-state cleanup;
- the public-data diff remains empty and no public UI changes are introduced.

## Rollout and follow-up

PF-103 remains local, opt-in, and disposable. It adds no hosted service and no
public runtime dependency. PF-104 may add engineering observability after the
run lifecycle and state contract are verified; it should consume the run
metadata contract rather than add per-message instrumentation to PF-103.
