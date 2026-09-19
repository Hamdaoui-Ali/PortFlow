# Local Redpanda streaming

This runbook explains how to publish deterministic telemetry to the opt-in local Redpanda
service and consume it into the existing Bronze Parquet contract with restart-safe stream
decisions.

## Architecture boundary

- Redpanda is disposable local development state and listens on host port `19092`.
- The source topic is `portflow.telemetry`; the default consumer group is `portflow-bronze`.
- The default dead-letter topic is `portflow.telemetry.dlq`.
- The consumer uses manual synchronous commits. A batch is committed only after its Bronze
  partition, durable state, and any required DLQ records have succeeded.
- Stream Bronze output defaults to `data/bronze-stream`, separate from the existing PostgreSQL
  Bronze path.
- Restart state is stored at `data/bronze-stream/.stream-state.sqlite3`. It is disposable local
  pipeline state, not a public data artifact.
- The public browser remains static and reads committed JSON snapshots only. Streaming does not
  write `web/public/data`, start a public API, or connect the hosted site to Redpanda.

## Prerequisites

- Python `3.12` or newer with the locked project environment.
- `uv` installed; use `python -m pip install uv` if it is not already available.
- Docker Desktop running with its Linux engine enabled.
- The repository's development dependencies installed:

```powershell
Set-Location C:/Users/aliha/PortFlow
python -m pip install uv
python -m uv sync --extra dev --frozen
```

## Run the bounded local workflow

These commands publish and consume twelve deterministic events:

```powershell
Set-Location C:/Users/aliha/PortFlow
docker compose --profile streaming up -d --wait redpanda
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
$env:PORTFLOW_REDPANDA_DLQ_TOPIC = "portflow.telemetry.dlq"
$env:PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS = "300"
python -m uv run python scripts/run_stream_producer.py --seed 42 --count 12
python -m uv run python scripts/run_stream_consumer.py --max-messages 12 --run-id stream-run-000042 --bronze-dir data/bronze-stream
python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
docker compose --profile streaming down -v redpanda
```

The producer reports the topic and published count. The consumer reports consumed messages,
Bronze rows, duplicate count, late count, DLQ count, committed batches, and batch count. With the
default batch size of `50`, twelve events are written in one batch by the runner; the integration
checks deliberately use smaller batches to verify multiple commits and restart behavior.

`docker compose --profile streaming down -v redpanda` removes only disposable local Redpanda
resources and state. It does not stop PostgreSQL, modify the committed public snapshot, or change
the PostgreSQL workflow.

## Optional Dagster orchestration (PF-103)

Dagster is an optional local dependency for manually launching one bounded streaming consumer
run. It does not add a daemon, schedule, sensor, automatic retry, or always-on service. Install the
extra and start the disposable broker before launching a run:

```powershell
Set-Location C:/Users/aliha/PortFlow
python -m uv sync --extra dev --extra orchestration
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
$env:PORTFLOW_REDPANDA_GROUP = "portflow-bronze"
$env:PORTFLOW_REDPANDA_DLQ_TOPIC = "portflow.telemetry.dlq"
docker compose --profile streaming up -d --wait redpanda
```

Create a user-owned YAML file named `pf-103-run.yaml` with the exact op configuration below:

```yaml
ops:
  consume_stream:
    config:
      topic: portflow.telemetry
      bronze_dir: data/bronze-stream
      batch_size: 2
      max_messages: 12
      allowed_lateness_seconds: 300
      poll_timeout_seconds: 1.0
      idle_timeout_seconds: 30.0
```

Launch the job manually from the repository root:

```powershell
python -m uv run --extra dev --extra orchestration dagster job execute `
  -m portflow.orchestration.streaming `
  -j stream_consumer_job `
  -c pf-103-run.yaml
```

The local Dagster UI may be used instead of the CLI to launch the same job. No daemon or schedule
is required. Dagster's generated `run_id` is the canonical identifier for these orchestrated
executions, and the consumer records run metadata in
`data/bronze-stream/.stream-state.sqlite3`. Inspect the lifecycle fields with:

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/bronze-stream/.stream-state.sqlite3'); c.row_factory=sqlite3.Row; print(*[dict(row) for row in c.execute('SELECT run_id, status, started_at, finished_at, error_type, error_message FROM stream_runs ORDER BY started_at DESC')], sep='\n')"
```

Failed rows may have null report counters because a failure can happen before the consumer
returns its report; null counters do not prove that zero messages were processed. A failed run's
original consumer error remains the execution error even if writing failure metadata also fails.

The existing `scripts/run_stream_consumer.py` command remains a direct, non-Dagster execution path
and does not write `stream_runs`. Dagster run IDs are canonical only for Dagster-managed runs.
After a manual fixture, stop only the disposable broker resources:

```powershell
docker compose --profile streaming down -v redpanda
```

The browser remains static, `web/public/data` remains unchanged, and no automatic retry is
configured.

## Optional engineering observability (PF-104)

PF-104 adds an opt-in local Prometheus and Grafana view for Dagster-managed stream runs. The
metrics exporter reads `data/bronze-stream/.stream-state.sqlite3` through a read-only container
mount and refreshes its aggregate view on each Prometheus scrape. It never initializes the
database or changes event, watermark, Bronze, DLQ, or run state. Direct CLI consumer runs do not
write `stream_runs`, so only PF-103 Dagster executions appear in this dashboard.

Start the broker and observability services from the repository root:

```powershell
Set-Location C:/Users/aliha/PortFlow
docker compose --profile streaming --profile observability up -d --wait redpanda portflow-metrics prometheus grafana
```

Check the exporter directly:

```powershell
Invoke-WebRequest http://127.0.0.1:9108/metrics
```

Open the local tools at:

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

Grafana uses the disposable local default password `portflow`. Set
`$env:PORTFLOW_GRAFANA_ADMIN_PASSWORD` before starting the profile when a different local
password is needed. The ports are bound to loopback and are not a hosted or public service.

The dashboard reports state-store availability, active/succeeded/failed run counts, latest run
duration, and aggregate consumed, Bronze, committed, duplicate, late, and dead-letter totals. It
does not expose run IDs, exception messages, broker addresses, or raw payloads as metric labels.

Stop only the disposable observability services and their named volumes with:

```powershell
docker compose --profile observability down -v
```

Stop the optional broker separately when it is no longer needed:

```powershell
docker compose --profile streaming down -v redpanda
```

These commands do not remove the tracked directory sentinel, PostgreSQL data, stream Bronze
files, or `web/public/data`.

### PF-104 troubleshooting

- **`state_store_available=0`:** run a PF-103 Dagster job using `data/bronze-stream`, then refresh
  the dashboard. A missing state database is a valid empty-state condition.
- **Prometheus target is down:** confirm `portflow-metrics` is healthy and inspect
  `http://127.0.0.1:9108/metrics` directly before restarting the observability profile.
- **Loopback port already in use:** stop the local process using port `3000`, `9090`, or `9108`,
  or change the host-side binding in the disposable local Compose file before starting again.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORTFLOW_REDPANDA_BROKERS` | `localhost:19092` | Kafka-compatible broker address |
| `PORTFLOW_REDPANDA_TOPIC` | `portflow.telemetry` | Source telemetry topic |
| `PORTFLOW_REDPANDA_GROUP` | `portflow-bronze` | Consumer group |
| `PORTFLOW_REDPANDA_DLQ_TOPIC` | `portflow.telemetry.dlq` | Rejected-record topic |
| `PORTFLOW_STREAM_BATCH_SIZE` | `50` | Maximum source messages per Bronze decision batch |
| `PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS` | `300` | Inclusive lateness window behind the topic watermark |
| `PORTFLOW_STREAM_BRONZE_DIR` | `data/bronze-stream` | Default stream Bronze root and state directory |

The equivalent defaults can be copied directly into a PowerShell session:

```text
PORTFLOW_REDPANDA_DLQ_TOPIC=portflow.telemetry.dlq
PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS=300
data/bronze-stream/.stream-state.sqlite3
```

The producer uses each event ID as its Kafka key and canonical JSON as its value. The consumer
validates the telemetry contract and the two PortFlow headers before writing the existing
`telemetry_events` Bronze columns and metadata.

## PF-102 decisions and recovery

- Exact duplicate event IDs with the same canonical payload digest are counted and committed
  without a second Bronze write or DLQ record.
- A new event is late when its `ingestion_timestamp` is earlier than
  `watermark - allowed_lateness_seconds`. Equality at the boundary is accepted. The watermark is
  captured before each source batch, so messages in one batch do not make one another late.
- Invalid JSON, UTF-8, headers, or telemetry validation produce an `invalid_telemetry` DLQ record.
- A valid event outside the lateness window produces a `late_event` DLQ record.
- Reusing an event ID with a different canonical payload produces a `duplicate_conflict` DLQ
  record and never overwrites the first durable state.
- DLQ envelopes preserve the source topic, partition, offset, key, raw value, ordered headers,
  reason, run ID, and reason code. Binary fields are base64 encoded.
- A DLQ candidate requires both a producer and a configured topic. The consumer checks this before
  the Bronze writer or state store mutates.
- Source offsets remain uncommitted when Bronze writing, state persistence, DLQ publication, or
  synchronous commit fails.
- A crash before the source commit may repeat a malformed or conflict DLQ record. Reopening the
  same Bronze directory and state database suppresses accepted events and valid events already
  recorded as dead letters.

## Reset a disposable stream fixture

Only remove the disposable stream Bronze directory when intentionally resetting a local fixture.
This removes the Parquet partitions and `.stream-state.sqlite3` for that fixture; it does not touch
repository roots or public snapshot files.

```powershell
Set-Location C:/Users/aliha/PortFlow
if (Test-Path -LiteralPath "data/bronze-stream") {
    Remove-Item -LiteralPath "data/bronze-stream" -Recurse -Force
}
New-Item -ItemType Directory -Path "data/bronze-stream" -Force | Out-Null
```

## Inspect the dead-letter topic

Use the configured topic with a Kafka-compatible inspection tool or a short local consumer. The
record headers include `portflow-dead-letter-reason` and `portflow-schema-version=1`; the JSON
envelope contains the original source location and base64 fields. Do not copy DLQ payloads into
`web/public/data`.

## Troubleshooting

- **Docker Linux engine unavailable:** start Docker Desktop's Linux engine, then retry the
  `docker compose --profile streaming up -d --wait redpanda` command.
- **Broker timeout or missing DLQ topic:** confirm the `redpanda` service is healthy, verify
  `$env:PORTFLOW_REDPANDA_BROKERS` is `localhost:19092`, and check that the configured source and
  DLQ topic names are different. The integration test creates unique topics and groups for each run.
- **State database corruption:** stop the consumer, preserve the failing directory for inspection,
  and restart with a clean disposable stream directory only when replaying the fixture is
  intentional. Do not delete repository roots or public snapshots.
- **No broker configured:** the real integration test skips with
  `PORTFLOW_REDPANDA_BROKERS is not set; start the streaming Compose profile`; this is intentional
  for broker-free unit and CI collection.

## Scope after PF-102

PF-102 adds restart-safe local deduplication, bounded lateness, and dead-letter handling. PF-103
is the next streaming slice for orchestration and run metadata. Schema Registry, Avro/Protobuf,
transactions, multi-broker deployment, authentication, automatic DLQ reprocessing, and a public
streaming UI remain outside this local development slice.
