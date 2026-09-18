# Changelog

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
