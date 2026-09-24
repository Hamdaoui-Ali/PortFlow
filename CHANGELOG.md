# Changelog

## PF-123 Overview KPI drill-downs - 2026-09-24

The Overview KPI rail now offers direct paths into the two operational detail
views that explain its most actionable signals.

- `Open equipment` links equipment availability to the existing Equipment view.
- `Open incidents` links active incidents to the existing Incidents view.
- Native hash links preserve the current query parameters and shareable view
  behavior, with no data, API, route, or dependency changes.
- The link treatment reuses the approved focus and color tokens and remains
  inside the existing bundle, startup, and snapshot budgets.

## PF-122 Shareable investigation links - 2026-09-23

Operators can now copy the exact URL-backed PortFlow view from the global
filter band.

- `Copy view link` preserves the current route, query parameters, filters,
  sorting, and detail context.
- Success and failure feedback uses an accessible output region without moving
  focus.
- Clipboard failures keep the browser address bar as the actionable fallback.

The feature remains client-side and adds no backend, persistence, analytics, or
public snapshot schema changes.

## PF-118 Overview incident pulse - 2026-09-23

Overview now exposes a compact, snapshot-backed incident pulse beside the
existing equipment context.

- Up to three records are ranked open-first, then by severity, opening instant,
  and stable incident ID.
- Each record shows visible severity, lifecycle status, root cause, equipment
  context, and a native link to the existing incident detail route.
- Absent, empty, unavailable, and malformed incident datasets remain explicit
  instead of being presented as a healthy or complete incident history.

The feature adds no endpoint, polling loop, public-data schema change, cloud
dependency, or live operational claim.

## PF-117 Overview equipment pulse - 2026-09-23

Overview now exposes a compact, snapshot-backed equipment pulse beneath the
aggregate availability card.

- Up to three equipment records are shown with unavailable records first,
  lower availability next, higher downtime as a secondary signal, and a stable
  equipment ID tie-breaker.
- Each equipment ID uses a native link to the existing Equipment detail route,
  preserving keyboard, modifier-click, and new-tab behavior.
- Absent, empty, unavailable, and malformed equipment datasets remain explicit
  instead of being presented as a healthy or complete fleet.

The feature adds no endpoint, polling loop, public-data schema change, cloud
dependency, or live operational claim.

## PF-116 Incident detail context - 2026-09-23

Incident detail now exposes compact, snapshot-backed context for the affected
equipment while preserving PortFlow's static-data boundary.

- The detail view derives the matching equipment record and shows terminal,
  state, availability, utilization, and downtime when that record is present.
- A native equipment route link makes the incident-to-equipment workflow
  reversible without adding a client-side navigation dependency.
- Absent, empty, unavailable, malformed, and no-match snapshot states remain
  explicit instead of being presented as healthy or complete context.

The feature adds no endpoint, polling loop, public-data schema change, cloud
dependency, or live operational claim.

## PF-115 Equipment detail context - 2026-09-22

The PF-115 implementation adds diagnostic context to a selected equipment
record while keeping PortFlow a static snapshot product.

- Equipment detail now derives a deterministic activity timeline from the
  existing replay events, collapsing adjacent duplicate states without
  mutating published data.
- Related incidents are filtered to the selected equipment, sorted newest
  first, and linked to the existing incident detail route.
- Absent, empty, unavailable, malformed, and no-match data states remain
  explicit instead of being presented as healthy or complete history.
- Responsive context sections, keyboard-reachable links, UTC timestamps, and
  reliable return-focus behavior are covered by the frontend tests.

The feature adds no endpoint, polling loop, public-data schema change, cloud
dependency, or live operational claim.

## PF-108 Databricks result comparison - 2026-09-21

PortFlow now includes a local, credential-free comparator for an operator-supplied
Databricks Gold result.

- `python -m labs.portflow_databricks compare` verifies the PF-107 handoff,
  canonicalizes the supplied `overview_kpis` rows, and writes deterministic
  match or mismatch evidence below ignored `.databricks/pf108/`.
- The comparison performs no cloud execution, credential lookup, workspace
  API call, notebook upload, or public-data write.
- A mismatch returns a non-zero status with the bounded
  `result_hash_mismatch` reason and remains explicit manual evidence.

## PF-107 Databricks Free Edition Delta/PySpark lab - 2026-09-21

PortFlow now includes a credential-free offline handoff bundle for validating
the shared Parquet-to-Bronze/Silver/Gold Delta contract before an optional
manual Databricks Free Edition run.

- The local `run`/`verify` commands generate deterministic fixture, notebook,
  schema, and expected-result hashes under ignored `.databricks/` artifacts.
- The committed source notebook uses Serverless-compatible DataFrame and Delta
  APIs with Unity Catalog widget parameters.
- The default workflow never contacts Databricks or looks up credentials;
  `cloud_execution` remains `not_run`.

## PF-106 BigQuery portability evidence - 2026-09-20

PortFlow now includes a local, credential-free BigQuery portability bundle that
generates GoogleSQL-ready SQL and verifies its manifest without sending work to
BigQuery.

### PF-106 boundaries

- Portability artifacts are disposable local engineering evidence under
  `.portability/`, are not public data, and never update `web/public/data`.
- The default workflow is offline: it neither requires nor inspects credentials,
  and the manifest records `cloud_execution` as `not_run`.
- A future authenticated BigQuery dry run remains an explicit handoff, outside
  the default workflow.

## PF-105 benchmark evidence - 2026-09-20

PortFlow now includes an opt-in benchmark harness for comparing the shared telemetry
workload across DuckDB, Polars, and optional Docker-isolated PySpark.

### Included

- Deterministic smoke, small, medium, and large fixture profiles with logical hashes.
- Versioned JSON reports with median and p95 timing, engine status, bounded reason codes, and
  canonical result hashes.
- A pinned Spark image, cross-engine result equivalence checks, report verification, and a
  local benchmark runbook.

### PF-105 boundaries

- Benchmark fixtures and reports are disposable local engineering evidence under
  .benchmarks/; benchmark data is not public data and never updates web/public/data.
- Timing is host-specific and is not a hosted performance guarantee.
- PySpark remains optional; missing Docker produces a bounded unavailable result rather than
  silently substituting another engine.

## PF-104 engineering observability - 2026-09-19

PortFlow now includes an optional local Prometheus and Grafana stack for inspecting bounded
Dagster-managed streaming runs through the PF-103 `stream_runs` contract.

### Included

- A dependency-free read-only metrics exporter with a `/metrics` endpoint.
- An opt-in `observability` Compose profile with Prometheus and Grafana.
- A provisioned Grafana dashboard for state-store availability, run status, duration, and stream
  outcome totals.
- Unit, configuration, Compose, and documentation coverage for missing state, malformed state,
  bounded labels, loopback ports, and read-only mounts.

### PF-104 boundaries

- Metrics are local, scrape-time aggregates; no per-message instrumentation, tracing, alerts, or
  hosted monitoring service is added.
- Run IDs, exception messages, broker addresses, and raw payloads are not metric labels.
- The exporter does not mutate SQLite state, the public browser remains static, and
  `web/public/data` is unchanged.

## PF-103 local orchestration - 2026-09-19

PortFlow now includes optional local Dagster orchestration for one bounded telemetry consumer
run. Each Dagster execution records durable run lifecycle metadata in the existing Bronze
directory's SQLite state and uses Dagster's generated run ID as its canonical run identifier.

### Included

- An optional `orchestration` dependency extra with Dagster and the local Dagster webserver.
- A typed `stream_consumer_job` with explicit topic, Bronze path, batch, limit, lateness, poll,
  and idle-timeout configuration.
- `running`, `succeeded`, and `failed` run metadata with timestamps, report counters, and terminal
  error details when available.
- Manual CLI/UI execution documentation, SQLite inspection guidance, and failure-preserving
  cleanup behavior.
- Broker-optional unit coverage, full Python regression coverage, and a passing Redpanda round trip.

### PF-103 boundaries

- Orchestration covers the streaming consumer path only; the existing direct producer and consumer
  CLI commands remain unchanged and do not write `stream_runs`.
- Execution remains local and manual. Producer orchestration, schedules, sensors, automatic
  retries, always-on services, hosted Dagster, and a public streaming UI remain out of scope.
- Stream output, SQLite state, and DLQ data remain disposable local state; the public browser stays
  static and `web/public/data` is unchanged.

## PF-102 stream safety - 2026-09-18

PortFlow's opt-in local telemetry stream is now safe to retry across consumer restarts. The
consumer persists event identity and topic watermarks in a local SQLite state file, applies a
five-minute bounded-lateness policy, and preserves rejected records in a canonical dead-letter
topic before committing source offsets.

### Included

- Durable `<bronze-dir>/.stream-state.sqlite3` state with canonical payload digests and atomic
  Bronze/watermark updates.
- Exact-duplicate suppression, duplicate-conflict detection, and inclusive lateness-boundary
  handling.
- Canonical UTF-8 JSON DLQ envelopes with base64 binary fields, ordered headers, source position,
  and the fixed reason codes `invalid_telemetry`, `late_event`, and `duplicate_conflict`.
- Commit ordering that requires Bronze, state, and DLQ publication to succeed first, plus runner
  wiring for the configured DLQ topic and allowed lateness.
- Unit, broker-optional integration, documentation, and static-browser-boundary coverage.

### PF-102 boundaries

- Stream output, SQLite state, and DLQ data remain disposable local state; the public browser stays
  static and `web/public/data` is unchanged.
- Delivery remains at least once at the Redpanda/Parquet boundary. A crash before source commit
  may repeat a malformed or conflict DLQ record.
- PF-103 orchestration and run metadata, automatic DLQ reprocessing, Schema Registry,
  transactions, multi-broker deployment, authentication, and a public streaming UI remain out of
  scope.

## PF-101 local streaming - 2026-09-17

PortFlow now includes an opt-in, local Kafka-compatible telemetry path backed by Redpanda. The
bounded producer emits deterministic `TelemetryEvent` records to `portflow.telemetry`; the
consumer validates the canonical message contract, writes the existing telemetry Bronze schema,
and synchronously commits offsets only after a successful atomic write.

### Included

- Pinned one-node Redpanda Compose service under the `streaming` profile on host port `19092`.
- Lazy Confluent Kafka adapters behind transport-neutral producer and consumer protocols.
- Deterministic CLI runners, unit coverage with fake clients, and a broker-backed round-trip test.
- A separate GitHub Actions streaming workflow and local PowerShell verification command.
- A local streaming runbook that preserves the static/public-data boundary.

### PF-101 boundaries

- Stream output is disposable local Bronze data and never writes `web/public/data` or the hosted
  static site.
- Delivery is at least once; a crash after Bronze publication and before offset commit may replay
  a batch.
- Deduplication, late events, and dead-letter topics are delivered in PF-102; automatic
  replay/backfill remains deferred. Schema Registry, serialization formats beyond canonical JSON,
  transactions, multi-broker deployment, authentication, and a public streaming UI are excluded.

## PortFlow V1 - 2026-09-16

PortFlow V1 is published at `https://hamdaoui-ali.github.io/PortFlow/`. The merged `main` commit passed CI and
the GitHub Actions Pages workflow completed both its build and deploy jobs.

### Included in V1

- Static operations control-tower views for Overview, Equipment, Incidents, Live Demo, and Data Health.
- A deterministic local PostgreSQL, validation, reconciliation, and snapshot-export pipeline.
- Published `demo-v2` replay data with explicit simulated-data disclosure.
- Loopback-only local data workspace and deterministic navigation state.
- Accessibility and responsive hardening, including readable trend checkpoints at narrow widths, zero page-level overflow at 320px and 375px, and equipment-detail return focus.
- GitHub Pages base-path safety checks for `/PortFlow/`.
- A deterministic one-worker frontend verification setting after the prior two-worker mode reproduced nondeterministic focus/navigation failures under the review environment.

### Verification

- 69 Python tests passed.
- 189 frontend tests passed, including failure-state, trend-label, and equipment-focus coverage.
- Ruff, mypy, TypeScript, Pages-path verification, byte budgets, and three Lighthouse runs passed.
- The public root, hashed assets, manifest, versioned datasets, and brand mark returned HTTP 200.
- The published overview displayed the simulated-data disclosure and 94.4% equipment availability.
- Public route checks passed for Overview, Equipment, Incidents, Live Demo, and Data Health.
- Reduced-motion emulation disabled live motion styles while the replay still entered its playing state.

### Known boundaries

- The public build is static and snapshot-based; generated events and replay are simulated.
- No production runtime backend, live commercial feed, public write API, authentication, or public database is included.
- The local API remains loopback-only and PostgreSQL remains disposable local/CI state.
- The committed `demo-v2` snapshot is stale relative to the evidence date.
- The repository's `main` branch protection rules remain a separate hardening follow-up; the Pages environment and
  deploy job are restricted to `main`.
