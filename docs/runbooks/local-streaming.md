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
