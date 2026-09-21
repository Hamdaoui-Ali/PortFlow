# PF-101 Redpanda local streaming into Bronze

Date: 2026-09-17  
Status: Proposed for review  
Preserves: the static public product boundary and the existing Bronze contract

## Goal

Add a local, reproducible streaming path for telemetry without changing the
public PortFlow site. A deterministic telemetry producer will publish validated
events to a local Redpanda topic. A consumer will validate those messages and
write the same `telemetry_events` Bronze columns and metadata already produced
by the PostgreSQL extractor.

The result is a second local producer behind the existing Bronze boundary, not a
public live-data feature.

## User-visible outcome

After PF-101, a contributor can:

1. start PostgreSQL and an opt-in single-node Redpanda service locally;
2. publish the seeded telemetry fixture to `portflow.telemetry`;
3. consume the messages with a named consumer group;
4. inspect an immutable Parquet partition under the existing Bronze directory;
5. run the existing Silver stage against the stream partition together with the
   required reference partitions from the existing batch path;
6. repeat the producer and consumer flow with the same seed and receive the
   same validated event payloads and Bronze row shape.

The public static application, committed snapshots, and normal V1 verification
command remain unchanged.

## Scope

### Included

- A Redpanda Community-compatible local Docker Compose service behind a
  `streaming` profile. The default PostgreSQL-only workflow must not start it.
- The `confluent-kafka` Python client, wrapped behind small PortFlow interfaces
  so unit tests do not construct broker clients.
- One topic: `portflow.telemetry`.
- One message contract: the canonical JSON representation of the existing
  `TelemetryEvent` model, keyed by `event_id`.
- A deterministic producer that uses the existing seeded telemetry simulator.
- A consumer with manual offset commits. It commits an offset only after the
  corresponding Bronze partition has been written, re-read, schema-checked,
  hashed, and atomically published.
- A streaming-to-Bronze adapter that maps each validated telemetry event to the
  existing `TABLE_SPECS["telemetry_events"]` column order and metadata fields.
- Unit tests with fake producer/consumer clients and an opt-in Redpanda
  integration test.
- A local streaming runbook and a separate verification command.

### Excluded

- Alarm, incident, movement, weather, or other topics. They can be added as
  separate contracts after telemetry works.
- Dead-letter topics, duplicate suppression, late-event reconciliation, and
  replay/backfill policy. These are PF-102 concerns.
- Schema Registry, Avro, Protobuf, transactions, exactly-once processing,
  multi-broker deployment, Redpanda Console, and production authentication.
- Changes to the React application, public snapshot files, or the public
  deployment.
- Cloud brokers, public writes, credentials, or a continuously running service.

## Options considered

### A. `confluent-kafka` synchronous client — selected

Use the high-level `Producer` and `Consumer` APIs with a small PortFlow adapter.
This matches the existing synchronous Python pipeline, exposes explicit
`flush`, `poll`, `commit`, and `close` operations, and is one of the Python
clients Redpanda validates for its Kafka-compatible API.

The client is used only for the local streaming extension. PortFlow code does
not expose its types outside `src/portflow/streaming/`.

### B. `kafka-python`

This is a viable pure-Python alternative and is also listed by Redpanda as a
validated Python client. It would avoid a native client dependency, but it adds
less value for this local production-style exercise and has a less direct fit
with the desired producer delivery and consumer commit controls.

### C. Shelling out to `rpk`

This would minimize Python dependencies but make the producer and consumer
harder to unit-test, harder to embed in the pipeline, and dependent on a CLI
installation outside the Python environment. It is rejected for the data path.

References used for this decision:

- Redpanda Kafka client compatibility:
  https://docs.redpanda.com/streaming/current/develop/kafka-clients/
- Redpanda local Docker quickstart:
  https://docs.redpanda.com/streaming/current/get-started/quick-start/
- Confluent Python client API and commit configuration:
  https://github.com/confluentinc/confluent-kafka-python/blob/master/docs/index.rst

## Architecture and data flow

```text
existing TelemetryEvent simulator
            |
            v
  canonical JSON producer
            |
            v
  Redpanda: portflow.telemetry
            |
            v
  manual-commit consumer group: portflow-bronze
            |
            | parse JSON + Pydantic TelemetryEvent validation
            v
  shared telemetry-to-Bronze adapter
            |
            v
  immutable Bronze Parquet partition
            |
            v
  existing Silver -> Gold -> public export path
```

The browser remains downstream of versioned public JSON. It never connects to
Redpanda, Kafka, PostgreSQL, Parquet, or the local consumer.

The stream path does not replace the PostgreSQL extraction of reference tables.
For a full analytical run, the telemetry partition is combined with the
existing `terminals` and `equipment` Bronze partitions so Silver can resolve
foreign-key references. PF-101 proves the transport and Bronze boundary; it
does not claim that telemetry alone is a complete public snapshot.

## Message contract

Topic: `portflow.telemetry`  
Key: UTF-8 `event_id`  
Value: UTF-8 canonical JSON for `TelemetryEvent` with sorted keys and compact
separators  
Headers: `portflow-event-type=telemetry` and
`portflow-schema-version=1`

The value is intentionally the existing domain contract rather than a second
payload schema. The consumer validates the decoded value through
`TelemetryEvent`, including UTC timestamps, identifier patterns, numeric
ranges, and state/availability consistency.

The producer uses the simulator's stable event order and does not add wall-clock
timestamps or random identifiers. A delivery error fails the producer command
and returns a non-zero exit status.

## Streaming-to-Bronze contract

The adapter maps a validated `TelemetryEvent` into the existing telemetry source
row shape:

```text
event_id
schema_version
equipment_id
terminal_id
event_timestamp
ingestion_timestamp
state
available
load_percent
temperature_c
created_at
updated_at
```

For stream-originated rows, `created_at` and `updated_at` use the event's
`ingestion_timestamp`, matching the deterministic seeded PostgreSQL rows.
Bronze metadata remains unchanged:

- `source_table = "telemetry_events"`;
- `extraction_run_id` is supplied by the consumer command;
- `source_updated_at = ingestion_timestamp`;
- `extracted_at = ingestion_timestamp + 2 seconds`, preserving the existing
  deterministic writer convention.

The adapter sorts a batch by `(ingestion_timestamp, event_id)` before writing so
the output is deterministic even if a consumer returns a batch in another
order. It uses the existing Bronze partition writer and column order rather
than creating a second Parquet format.

PF-101 provides at-least-once delivery semantics. The consumer disables
automatic offset commits and commits the last processed offset synchronously
only after Bronze publication succeeds. A crash after Bronze publication but
before the offset commit may produce a repeated row on retry; PF-102 will add
stable deduplication and late-event handling.

## Components and boundaries

### `src/portflow/streaming/codec.py`

Owns canonical serialization and decoding of `TelemetryEvent`. It exposes
typed functions for `event -> bytes` and `bytes -> TelemetryEvent` and converts
JSON, UTF-8, and validation failures into one PortFlow stream-validation error.

### `src/portflow/streaming/config.py`

Owns environment-backed configuration with safe local defaults:

- `PORTFLOW_REDPANDA_BROKERS=localhost:19092`;
- `PORTFLOW_REDPANDA_TOPIC=portflow.telemetry`;
- `PORTFLOW_REDPANDA_GROUP=portflow-bronze`;
- `PORTFLOW_STREAM_BATCH_SIZE=50`.

It must reject empty broker, topic, group, or non-positive batch values.

### `src/portflow/streaming/producer.py`

Owns the producer adapter and deterministic fixture publishing. The module
depends on a narrow producer protocol, not a concrete client in its business
logic. The concrete `confluent-kafka` construction stays in a factory at the
edge.

### `src/portflow/streaming/consumer.py`

Owns polling, validation, batch boundaries, Bronze publication, synchronous
offset commits, and clean client shutdown. It must not silently discard a
malformed message or commit past an unpersisted message.

### `src/portflow/ingestion/postgres_to_bronze.py`

Gains a small public, transport-neutral telemetry batch writer or delegates to
an adjacent Bronze writer module. The existing PostgreSQL extraction behavior
and tests remain unchanged.

### Docker and scripts

`compose.yaml` gains only the opt-in Redpanda service. A separate streaming
runner/verification script starts the profile, publishes the deterministic
fixture, consumes it into a temporary Bronze directory, and runs the focused
checks. The existing `verify_r2.ps1` remains PostgreSQL-only so the published V1
gate does not acquire a broker dependency.

## Error handling

- Broker connection or startup failure: fail with a bounded, actionable error;
  do not fabricate data or write an empty Bronze partition.
- Producer delivery failure: surface the broker error and exit non-zero.
- Invalid JSON, UTF-8, headers, or `TelemetryEvent` fields: fail the current
  consumer batch, write no partition for that batch, and leave its offsets
  uncommitted. DLQ routing is intentionally deferred to PF-102.
- Bronze write, re-read, hash, or atomic rename failure: leave offsets
  uncommitted and retain no temporary Bronze file.
- Interrupt or normal shutdown: close the producer/consumer and do not claim
  messages that were not durably written.

## Testing and acceptance

### Unit tests

- canonical serialization is stable and round-trips through the domain model;
- invalid payloads return the stable stream-validation error;
- producer uses the event ID as the message key and the approved topic/headers;
- producer delivery errors are surfaced;
- consumer validates every message before writing a batch;
- invalid messages do not call the Bronze writer or commit offsets;
- successful batches commit only after the writer returns success;
- stream rows match the existing telemetry Bronze columns and metadata;
- batches are deterministic regardless of input ordering;
- configuration rejects invalid environment values.

### Redpanda integration test

An opt-in `redpanda` marker runs against the Compose service and proves:

1. the producer publishes the deterministic fixture;
2. the consumer reads exactly the requested event count;
3. a Bronze Parquet partition exists with the expected columns and row count;
4. the partition can be read by the existing Silver stage;
5. the consumer group has committed only after Bronze publication.

The test is skipped with a clear message when no local broker is configured;
the dedicated streaming verification command starts the broker before running
it. The standard V1 gate remains green without Docker Redpanda.

### Definition of done

PF-101 is complete when the focused unit and integration checks pass, the local
runbook reproduces the flow, the existing Python and frontend gates still pass,
the public data diff remains empty, and no public application or cloud runtime
dependency is introduced.

## Rollout and follow-up

The change is opt-in for local contributors and has no effect on the deployed
Pages artifact. The next streaming slice, PF-102, may add dead-letter topics,
duplicate suppression, late-event policy, and replay tooling after this
transport and Bronze boundary are verified.
