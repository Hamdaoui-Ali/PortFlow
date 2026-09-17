# Local Redpanda streaming

This runbook explains how to publish deterministic telemetry to the opt-in local Redpanda
service and consume it into the existing Bronze Parquet contract.

## Architecture boundary

- Redpanda is disposable local development state and listens on host port `19092`.
- The stream topic is `portflow.telemetry`; the default consumer group is `portflow-bronze`.
- The consumer uses manual synchronous commits: a batch is committed only after its Bronze
  partition has been written and validated.
- Stream Bronze output defaults to `data/bronze-stream`, separate from the existing PostgreSQL
  Bronze path.
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
python -m uv run python scripts/run_stream_producer.py --seed 42 --count 12
python -m uv run python scripts/run_stream_consumer.py --max-messages 12 --run-id stream-run-000042 --bronze-dir data/bronze-stream
python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
docker compose --profile streaming down -v redpanda
```

The producer reports the topic and published count. The consumer reports consumed rows,
Bronze rows, committed batches, and batch count. With the default batch size of `50`, twelve
events are written in one batch by the runner; the integration check deliberately uses a batch
size of `5` to verify three commits.

`docker compose --profile streaming down -v redpanda` removes only disposable local Redpanda
resources and state. It does not stop PostgreSQL, modify the committed public snapshot, or change
the PostgreSQL workflow.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORTFLOW_REDPANDA_BROKERS` | `localhost:19092` | Kafka-compatible broker address |
| `PORTFLOW_REDPANDA_TOPIC` | `portflow.telemetry` | Telemetry topic |
| `PORTFLOW_REDPANDA_GROUP` | `portflow-bronze` | Consumer group |
| `PORTFLOW_STREAM_BATCH_SIZE` | `50` | Maximum events per Bronze write |
| `PORTFLOW_STREAM_BRONZE_DIR` | `data/bronze-stream` | Default stream Bronze root |

The producer uses each event ID as its Kafka key and canonical JSON as its value. The consumer
validates the telemetry contract and the two PortFlow headers before writing the existing
`telemetry_events` Bronze columns and metadata.

## Failure and recovery behavior

- A malformed payload or header raises a validation error before the writer is called. It produces
  no Bronze partition and no committed offset for that current batch.
- A Bronze writer failure or commit failure closes the consumer and leaves the current batch
  uncommitted. A crash after the write and before the commit can replay that batch; this is the
  deliberate at-least-once PF-101 boundary.
- **Docker Linux engine unavailable:** start Docker Desktop's Linux engine, then retry the
  `docker compose --profile streaming up -d --wait redpanda` command.
- **Broker timeout:** confirm the `redpanda` service is healthy, verify
  `$env:PORTFLOW_REDPANDA_BROKERS` is `localhost:19092`, and rerun the bounded producer and
  consumer. The integration test creates a unique topic and group for each run.
- **No broker configured:** the real integration test skips with
  `PORTFLOW_REDPANDA_BROKERS is not set`; this is intentional for broker-free unit and CI
  collection.

## PF-102 boundary

PF-101 does not provide streaming deduplication, late-event handling, dead-letter topics, or a
replay/backfill policy. Those behaviors belong to PF-102. Schema Registry, Avro/Protobuf,
transactions, multi-broker deployment, authentication, and a public streaming UI are also
outside this local development slice.
