# PF-104 Engineering Observability Design

**Status:** Draft for review  
**Date:** 2026-09-19  
**Parent slice:** PF-103 orchestration and run metadata  
**Scope decision:** Local streaming-run observability only

## Goal

Add an opt-in local Prometheus and Grafana stack for inspecting bounded,
Dagster-managed PortFlow streaming runs. The stack must reuse the verified
`stream_runs` SQLite contract, remain disposable, and leave the consumer's
transport safety and the public product unchanged.

PF-104 is an engineering tool for the repository owner. It is not a public
PortFlow feature and it is not a production deployment design.

## Approved decisions

- Observe the PF-103 streaming path only. The PostgreSQL and batch pipeline are
  outside this slice.
- Read `stream_runs` as the source of truth. Do not add per-message metrics,
  tracing, or new writes to the consumer hot path.
- Add one optional `observability` Compose profile containing a read-only
  PortFlow metrics exporter, Prometheus, and Grafana.
- Make the exporter refresh its view on each Prometheus scrape from the local
  SQLite state database.
- Keep the exporter dependency-free beyond Python's standard library so the
  optional profile does not enlarge the main PortFlow runtime or lockfile.
- Expose only bounded aggregate metrics. Never use `run_id`, error messages,
  raw payloads, broker addresses, or other unbounded values as metric labels.
- Bind published observability ports to loopback and document the stack as
  disposable local state.
- Keep the existing direct consumer CLI behavior. Direct CLI runs do not write
  `stream_runs` and therefore do not appear in PF-104 run metrics.
- Do not add a React route, public snapshot field, Pages artifact, hosted
  Prometheus service, hosted Grafana service, authentication system, alerting
  policy, or cloud dependency.

## Current boundary

PF-103 already provides:

- the bounded manual-commit stream consumer;
- durable event, dead-letter, and watermark state in SQLite;
- a `stream_runs` table with `running`, `succeeded`, and `failed` lifecycle
  states;
- input values, timestamps, terminal errors, and `ConsumeReport` counters for
  Dagster-managed runs;
- an optional Redpanda Compose profile; and
- an optional Dagster dependency group and manual local runbook.

The existing state database is normally at
`data/bronze-stream/.stream-state.sqlite3`. PF-104 must open this file in
read-only mode. The exporter must not create the directory, initialize the
schema, update watermarks, or alter event and run state.

## Non-goals

- No changes to `consume_telemetry_stream()` commit ordering or retry behavior.
- No instrumentation for individual Kafka messages, partitions, offsets, or
  payloads.
- No orchestration of the producer or batch PostgreSQL pipeline.
- No Dagster daemon, schedule, sensor, automatic retry, or hosted deployment.
- No public web UI or browser connection to SQLite, Prometheus, Grafana,
  Redpanda, or Dagster.
- No alert rules, notification channels, SLOs, authentication, or multi-user
  tenancy.
- No historical migration beyond reading the existing `stream_runs` schema.

## Architecture

The optional stack has three services:

```text
Dagster consumer --writes--> SQLite stream_runs
                                  |
                    read-only scrape on demand
                                  v
                       PortFlow metrics exporter
                                  |
                         Prometheus scrapes
                                  |
                       Grafana reads Prometheus
```

### Metrics exporter

Add a small Python HTTP service under `src/portflow/observability/` with a
`/metrics` endpoint. It opens the configured SQLite path with SQLite's read-only
URI mode, reads a consistent snapshot of `stream_runs`, and emits the
Prometheus text exposition format.

The exporter must:

1. bind to a configurable local port, defaulting to `9108`;
2. use `PORTFLOW_STREAM_STATE_PATH`, defaulting to
   `data/bronze-stream/.stream-state.sqlite3`;
3. return a successful scrape with an availability metric when the state file
   does not yet exist, so an unused optional stack is diagnosable;
4. report collection failure through a metric and never mutate the state file;
5. calculate a run duration from UTC timestamps, using the current UTC time for
   a still-running latest run; and
6. avoid exposing the state path, error message, or database exception in the
   metric label set.

The HTTP health behavior is intentionally small: `/metrics` is the only
required endpoint. Prometheus target health indicates that the exporter is
reachable; `portflow_stream_state_store_available` indicates whether the
configured state store could be read.

### Metric contract

The exporter emits these bounded metrics:

| Metric | Type | Meaning |
| --- | --- | --- |
| `portflow_stream_state_store_available` | gauge | `1` when the configured SQLite state store was read successfully, otherwise `0`. |
| `portflow_stream_metrics_collection_success` | gauge | `1` when the most recent scrape collected state successfully, otherwise `0`. |
| `portflow_stream_runs_count{status}` | gauge | Number of stored runs for `running`, `succeeded`, or `failed`. |
| `portflow_stream_last_run_status{status}` | gauge | One-hot status for the most recently started stored run; all statuses are emitted. |
| `portflow_stream_last_run_started_at_seconds` | gauge | UTC Unix timestamp for the latest run, or `0` when no run exists. |
| `portflow_stream_last_run_finished_at_seconds` | gauge | UTC Unix timestamp for the latest run's finish, or `0` when unfinished or absent. |
| `portflow_stream_last_run_duration_seconds` | gauge | Duration of the latest run, or `0` when no run exists. |
| `portflow_stream_consumed_messages_total` | gauge | Sum of non-null `consumed_count` values across stored runs. |
| `portflow_stream_bronze_rows_total` | gauge | Sum of non-null `bronze_row_count` values across stored runs. |
| `portflow_stream_committed_batches_total` | gauge | Sum of non-null `committed_count` values across stored runs. |
| `portflow_stream_duplicate_messages_total` | gauge | Sum of non-null `duplicate_count` values across stored runs. |
| `portflow_stream_late_messages_total` | gauge | Sum of non-null `late_count` values across stored runs. |
| `portflow_stream_dead_letters_total` | gauge | Sum of non-null `dead_letter_count` values across stored runs. |

The aggregate counters are gauges because they are materialized from the
current SQLite table, not process-local monotonic counters. Failed rows with
null result counters contribute no result count; the dashboard must not label
those nulls as zero work.

The exporter may include standard `HELP` and `TYPE` lines, but it must not add
labels beyond the documented low-cardinality `status` label. Error details
remain available through the SQLite inspection runbook and Dagster logs.

### Prometheus

Add a committed Prometheus configuration that scrapes the exporter over the
Compose network at a short local interval. Prometheus data is stored in a
disposable named volume. The configuration must not scrape PostgreSQL,
Redpanda, the public site, or arbitrary host addresses.

### Grafana

Provision one local Prometheus data source and one starter dashboard. The
dashboard should make the following questions answerable without exposing
unbounded identifiers:

- Is the state store readable?
- Are runs currently active, succeeding, or failing?
- How long did the latest run take?
- How many messages were consumed, written to Bronze, committed, duplicated,
  late, or sent to the dead-letter path?

The dashboard is configuration checked into the repository, not a new PortFlow
product surface. Grafana and Prometheus ports must be bound to loopback only.

## Compose and local workflow

The default `docker compose up` behavior remains unchanged. The new services
start only when the `observability` profile is selected. The runbook will
document:

1. starting Redpanda and the observability profile;
2. pointing the exporter at the same `data/bronze-stream` directory used by the
   PF-103 consumer;
3. opening Prometheus and Grafana on their loopback ports;
4. running a Dagster consumer job and refreshing the dashboard; and
5. stopping and removing only disposable observability resources.

The profile must support a missing or empty stream state directory without
changing repository files or public data. The exporter volume is read-only;
Prometheus and Grafana use disposable named volumes.

## Failure behavior

- Missing state database: exporter remains reachable and reports availability
  and collection success as `0`; run metrics use empty-state values.
- SQLite read error: exporter remains reachable, reports collection success as
  `0`, and does not expose exception text in metrics.
- Malformed stored timestamps or invalid status values: exporter treats the
  collection as unsuccessful rather than inventing a partial dashboard view.
- Prometheus unavailable: the consumer and state database continue to work
  normally.
- Grafana unavailable: Prometheus and the consumer continue to work normally.
- Observability profile stopped: no PortFlow pipeline behavior changes.

## Testing and verification

Before implementation is considered complete:

- unit tests cover empty, running, succeeded, failed, and unreadable SQLite
  states;
- tests verify the exporter uses read-only access and does not mutate the
  state database;
- tests verify metric names, types, bounded labels, timestamp conversion,
  null-counter handling, and latest-run selection;
- Compose configuration tests verify the optional profile, loopback bindings,
  read-only state mount, Prometheus scrape target, and Grafana provisioning;
- the local runbook includes a manual smoke check for the `/metrics` endpoint;
- Ruff, mypy, the full Python suite, and the existing quality gate pass; and
- `web/public/data` remains byte-for-byte unchanged.

## Rollout and follow-up

PF-104 remains local, opt-in, and disposable. It gives engineers a repeatable
view of PF-103 run health without turning PortFlow into a hosted monitoring
platform. Future work may add batch-pipeline metrics or alerting only as a
separate approved slice with its own data and cardinality contract.
