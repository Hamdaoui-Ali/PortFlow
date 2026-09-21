# PF-102 Stream Safety Design

**Status:** Draft for review
**Date:** 2026-09-18
**Parent slice:** PF-101 local Redpanda streaming
**Next slice after this:** PF-103 orchestration and run metadata

## Goal

Extend PortFlow's opt-in local telemetry stream with restart-safe duplicate
suppression, a bounded lateness policy, and dead-letter handling while keeping
the existing Bronze contract and the public static product unchanged.

PF-102 must make a bounded consumer run safe to retry after a crash. A record
may be delivered more than once, but a successfully published Bronze event must
not be written as a second logical event by a later retry. Records that cannot
be accepted safely must be preserved for inspection rather than silently
dropped.

## Current boundary

PF-101 currently provides:

- a canonical `TelemetryEvent` JSON codec in `src/portflow/streaming/codec.py`;
- a synchronous producer protocol in `src/portflow/streaming/producer.py`;
- a manual-commit consumer in `src/portflow/streaming/consumer.py`;
- an atomic, deterministic telemetry Bronze writer in
  `src/portflow/ingestion/postgres_to_bronze.py`;
- a single-node local Redpanda service under the `streaming` Compose profile;
- bounded producer and consumer runners under `scripts/`.

The current consumer validates each message, writes one Bronze batch, and
commits the last source message only after the writer returns. It has no
durable event identity state, no lateness decision, and no dead-letter route.

## Non-goals

- No React, CSS, snapshot, route, or public-data changes.
- No browser connection to Redpanda, Kafka, SQLite, Parquet, or the local
  consumer.
- No changes to the PostgreSQL extraction path or the `TABLE_SPECS` telemetry
  Bronze schema.
- No exactly-once guarantee across Redpanda and Parquet; PF-102 remains
  at-least-once at the transport boundary.
- No compaction, replay UI, backfill engine, or automatic reprocessing of DLQ
  records.
- No production authentication, Schema Registry, transactions, multi-broker
  deployment, or additional streaming topics beyond the telemetry DLQ topic.
- No automatic discovery of every old PF-101 Bronze partition. A PF-102 run
  starts with a state database in the configured stream Bronze directory; the
  runbook will say how to use a clean disposable stream directory when needed.

## Design choices

### 1. Durable local state keyed by event identity

Use the Python standard-library `sqlite3` module. Store the state database at:

```text
<bronze-dir>/.stream-state.sqlite3
```

The state database is local disposable pipeline state, not a public artifact.
It uses one connection per `StreamStateStore` instance, `PRAGMA
synchronous=FULL`, and explicit transactions. The design does not add a new
runtime dependency.

The primary identity is the domain `TelemetryEvent.event_id`. The state table
stores a SHA-256 digest of the canonical encoded event, so a repeated event ID
with changed content is distinguishable from an exact duplicate.

The state schema is:

```sql
CREATE TABLE processed_events (
    event_id TEXT PRIMARY KEY,
    payload_sha256 TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('bronze', 'dead_letter')),
    reason_code TEXT
);

CREATE TABLE watermarks (
    topic TEXT PRIMARY KEY,
    max_ingestion_timestamp TEXT NOT NULL
);
```

No wall-clock timestamp is stored. This keeps state decisions independent of
the machine clock and preserves deterministic test fixtures.

The state store exposes small operations rather than leaking SQLite objects
into the consumer:

```python
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from portflow.domain.models import TelemetryEvent


@dataclass(frozen=True, slots=True)
class ProcessedEventState:
    event_id: str
    payload_sha256: str
    ingestion_timestamp: datetime
    outcome: str
    reason_code: str | None


class StreamStateStore:
    def __init__(self, path: Path) -> None: ...

    def get_event(self, event_id: str) -> ProcessedEventState | None: ...

    def get_watermark(self, topic: str) -> datetime | None: ...

    def record_bronze(self, *, topic: str, events: Sequence[TelemetryEvent]) -> None: ...

    def record_dead_letter(
        self,
        *,
        topic: str,
        event: TelemetryEvent,
        reason_code: str,
    ) -> None: ...

    def close(self) -> None: ...
```

`record_bronze` inserts all accepted events and advances the topic watermark to
the greatest accepted `ingestion_timestamp` in one SQLite transaction.
`record_dead_letter` records valid, non-conflicting events routed to DLQ so the
same valid event does not create an unbounded sequence of identical DLQ records
after retries. A `duplicate_conflict` retains the first event's state and is
not inserted as a second row; a crash before the source commit may therefore
publish that conflict to DLQ again. Malformed payloads do not have a validated
event ID and likewise rely on normal at-least-once source-offset behavior.

### 2. Duplicate policy

For a valid event whose `event_id` is already in state:

- If its canonical payload digest matches the stored digest, classify it as an
  exact duplicate. Do not call the Bronze writer, do not update the watermark,
  and do not publish a new DLQ record.
- If its digest differs, classify it as `duplicate_conflict` and route the
  original record to DLQ. Do not overwrite the first accepted state.

Duplicates that occur twice in the same source batch are handled with the same
rules using a pending in-memory map before the state transaction is written.

### 3. Bounded lateness policy

Add `allowed_lateness_seconds` to `StreamingConfig` with the environment
variable `PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS` and a default of `300`.
Reject negative values.

For a valid event that is not a duplicate, compare its
`ingestion_timestamp` with the topic watermark loaded at the start of the
source batch:

```text
late when event.ingestion_timestamp
      < watermark - allowed_lateness_seconds
```

An event equal to the boundary is accepted. Events in the same source batch
do not make one another late; the watermark advances only after accepted
events are durably written and recorded. This makes classification independent
of the order in which a batch happens to be assembled.

When no watermark exists, the first valid event is not late. A late event is
not written to Bronze and is routed with reason code `late_event`.

### 4. Dead-letter contract

Add `dlq_topic` to `StreamingConfig` with the environment variable
`PORTFLOW_REDPANDA_DLQ_TOPIC` and default `portflow.telemetry.dlq`. Reject an
empty value and reject a DLQ topic equal to the source topic.

DLQ values are canonical UTF-8 JSON with sorted keys and compact separators.
Binary fields are base64 encoded so the original payload and headers can be
reconstructed exactly. The envelope is:

```json
{
  "reason": "human-readable validation or policy detail",
  "reason_code": "invalid_telemetry",
  "run_id": "stream-run-000042",
  "schema_version": 1,
  "source_headers": [
    {"name": "portflow-event-type", "value_base64": "dGVsZW1ldHJ5"}
  ],
  "source_key_base64": "ZXZ0LTAwMDA0Mi0wMDAwMDE=",
  "source_offset": 17,
  "source_partition": 0,
  "source_topic": "portflow.telemetry",
  "source_value_base64": "..."
}
```

`source_headers` preserves header order, header names, and null values. A
missing source key or value is represented by JSON `null`. The DLQ message key
uses the original source key when available and otherwise the UTF-8 text
`<source-topic>:<partition>:<offset>`. DLQ messages carry:

```text
portflow-dead-letter-reason=<reason_code>
portflow-schema-version=1
```

The reason codes are the fixed set `invalid_telemetry`, `late_event`, and
`duplicate_conflict`.

The dead-letter module exposes transport-neutral types and a publisher that
uses the existing `ProducerClient` protocol:

```python
from collections.abc import Sequence
from dataclasses import dataclass

from portflow.streaming.codec import Header
from portflow.streaming.producer import ProducerClient


@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    source_topic: str
    source_partition: int
    source_offset: int
    source_key: bytes | None
    source_value: bytes | None
    source_headers: Sequence[Header] | None
    reason_code: str
    reason: str
    run_id: str


def encode_dead_letter(record: DeadLetterRecord) -> bytes: ...


def publish_dead_letters(
    records: Sequence[DeadLetterRecord],
    *,
    producer: ProducerClient,
    topic: str,
    flush_timeout: float = 10.0,
) -> int: ...
```

The publisher uses the existing producer delivery callback and flush rules. A
delivery error or non-zero flush remainder raises `ProducerDeliveryError` and
prevents the corresponding source offset commit.

### 5. Consumer ordering and commit safety

Extend `ConsumerMessage` with `partition()` and `key()` methods so a DLQ
record can retain source position and key. The local Compose and integration
contract continues to use one source partition.

Extend `consume_telemetry_stream` with:

```python
def consume_telemetry_stream(
    consumer: ConsumerClient,
    *,
    topic: str,
    bronze_dir: Path,
    run_id: str,
    batch_size: int,
    max_messages: int,
    writer: BronzeWriter = write_telemetry_bronze_batch,
    dead_letter_producer: ProducerClient | None = None,
    dead_letter_topic: str | None = None,
    allowed_lateness_seconds: int = 300,
    state_store: StreamStateStore | None = None,
    poll_timeout_seconds: float = 1.0,
    idle_timeout_seconds: float = 30.0,
) -> ConsumeReport: ...
```

If a message needs DLQ and no producer/topic is supplied, fail before source
commit with an actionable `StreamConsumerError`. This prevents silent drops.

Each bounded source batch follows this order:

1. Poll and classify every message in the batch. Invalid payloads become
   `invalid_telemetry` DLQ candidates; valid messages become accepted events,
   exact duplicates, or policy DLQ candidates.
2. If any DLQ candidate exists, verify that both a DLQ producer and DLQ topic
   are available before making Bronze or state mutations.
3. Write accepted events with the existing deterministic Bronze writer. Skip
   the writer when the batch contains no accepted events.
4. Record accepted Bronze events and the new watermark in the state store.
5. Publish all DLQ candidates and, after successful delivery, record valid
   non-conflicting events as `dead_letter` in the state store. Conflicts leave
   the original event state untouched.
6. Synchronously commit the last source message in the batch.

If any step fails, the consumer closes without claiming uncommitted source
messages. A retry may repeat a Bronze write or DLQ publication, but the
existing Bronze hash check and durable event state make the accepted event
path idempotent after recovery.

The consumer report becomes:

```python
@dataclass(frozen=True, slots=True)
class ConsumeReport:
    consumed_count: int
    bronze_row_count: int
    committed_count: int
    batch_count: int
    duplicate_count: int
    late_count: int
    dead_letter_count: int
```

`consumed_count` counts source messages polled, including invalid, duplicate,
and late messages. `bronze_row_count` counts rows written by the existing
writer. `dead_letter_count` counts DLQ records published in the run, not
repeated source messages that were already recorded as `dead_letter`.

### 6. CLI and configuration behavior

`scripts/run_stream_consumer.py` will:

- create a `StreamStateStore` at `<bronze-dir>/.stream-state.sqlite3`;
- create a producer for the configured DLQ topic;
- pass the configured DLQ topic and allowed lateness to the consumer;
- close both consumer and state/producer resources on success or failure;
- print the expanded `ConsumeReport` as sorted JSON.

`StreamingConfig` defaults become:

```text
PORTFLOW_REDPANDA_BROKERS=localhost:19092
PORTFLOW_REDPANDA_TOPIC=portflow.telemetry
PORTFLOW_REDPANDA_GROUP=portflow-bronze
PORTFLOW_REDPANDA_DLQ_TOPIC=portflow.telemetry.dlq
PORTFLOW_STREAM_BATCH_SIZE=50
PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS=300
```

The source producer remains unchanged. The public `StreamingConfig` and
consumer property dictionaries keep their existing broker and manual-commit
values.

## File and module map

| File | Responsibility |
| --- | --- |
| `src/portflow/streaming/config.py` | Add DLQ topic and lateness configuration validation. |
| `src/portflow/streaming/state.py` | Own SQLite schema, event lookups, durable outcomes, and topic watermark. |
| `src/portflow/streaming/dead_letter.py` | Own DLQ envelope encoding, headers, and producer publication. |
| `src/portflow/streaming/consumer.py` | Classify messages, coordinate writer/state/DLQ ordering, and report outcomes. |
| `src/portflow/streaming/producer.py` | Reuse the existing fakeable producer protocol and delivery error. |
| `src/portflow/streaming/__init__.py` | Export only stable PF-102 public symbols. |
| `scripts/run_stream_consumer.py` | Wire the state store and DLQ producer into the bounded CLI. |
| `.env.example` | Document the new topic and lateness variables. |
| `tests/unit/test_streaming_state.py` | Restart persistence, conflict detection, and watermark transactions. |
| `tests/unit/test_streaming_dead_letter.py` | Canonical envelope, binary preservation, headers, and delivery failure. |
| `tests/unit/test_streaming_config.py` | New defaults, invalid values, and source/DLQ topic collision. |
| `tests/unit/test_streaming_consumer.py` | Duplicate, conflict, late, malformed, ordering, and report behavior. |
| `tests/streaming/test_redpanda.py` | Publish source records, exercise DLQ, and verify committed offsets. |
| `docs/runbooks/local-streaming.md` | Add state reset, DLQ inspection, lateness, and retry guidance. |
| `README.md` | Keep the streaming boundary link and limitations current. |
| `docs/product/BACKLOG.md` | Mark PF-102 complete only after verification. |
| `CHANGELOG.md` | Record the post-PF-101 stream-safety slice. |

## Error handling

- Invalid JSON, UTF-8, headers, or `TelemetryEvent` validation: publish
  `invalid_telemetry` to DLQ, then commit only after successful DLQ delivery.
- A valid event outside the lateness window: publish `late_event` and commit
  only after successful DLQ delivery.
- Same event ID with a different canonical payload: publish
  `duplicate_conflict`; never overwrite the first event state.
- DLQ producer failure: raise `ProducerDeliveryError` through the consumer;
  leave the source offset uncommitted.
- State database corruption or transaction failure: fail the run before
  committing the affected source batch and preserve the original error.
- Bronze write, reread, hash, or atomic rename failure: leave the source
  offset uncommitted and let the existing writer clean staging output.
- Broker errors other than partition EOF and idle timeout: preserve current
  `StreamConsumerError` behavior.
- Consumer or state-store close errors must not hide the primary processing
  failure; cleanup errors are chained or reported separately.

## Testing and acceptance

### Unit tests

- Configuration defaults include the DLQ topic and five-minute lateness; empty
  and invalid values fail; source/DLQ topic collisions fail.
- A state store reopened from the same path returns the same event state and
  watermark.
- `record_bronze` is atomic: a failed transaction does not leave partial event
  rows or a partially advanced watermark.
- Exact duplicate payloads are suppressed, while same-ID changed payloads are
  classified as conflicts.
- Boundary lateness is accepted and one microsecond below the boundary is
  dead-lettered.
- The DLQ envelope round-trips original bytes, ordered headers, null values,
  source position, reason code, and run ID.
- The consumer writes Bronze before state/commit, publishes DLQ before commit,
  and does not commit after writer, state, or DLQ failure.
- Invalid, late, and conflict records are counted in the report and do not
  reach the Bronze writer.
- A batch containing only duplicates does not create a Parquet partition.
- Reopening the consumer with the same state path suppresses a previously
  published event.

### Redpanda integration test

Extend the opt-in test to create unique source and DLQ topics, publish a
mixture of valid, duplicate, late, and malformed records, and verify:

1. accepted valid events produce the expected Bronze rows;
2. exact duplicates do not increase Bronze row count;
3. late, conflicting, and malformed records appear in the DLQ with preserved
   source metadata;
4. source offsets are committed only after Bronze/DLQ publication;
5. reopening the state store and rerunning the same messages does not create
   additional Bronze rows;
6. the resulting accepted Bronze partition remains readable by the existing
   Silver transformation.

The test remains skipped with a clear message when no broker is configured.
The dedicated PowerShell verification command starts the Compose profile and
cleans up disposable Redpanda data as PF-101 already does.

### Definition of done

PF-102 is complete when the focused unit tests, existing regression tests, and
broker-optional integration test pass; the real Redpanda verification passes
when Docker is available; the local runbook documents recovery and DLQ use;
the public data diff is empty; and the browser remains static and unchanged.

## Rollout and follow-up

PF-102 remains opt-in and local. It adds only disposable state under the
configured stream Bronze directory and one Kafka-compatible DLQ topic. The
next slice, PF-103, may add orchestration and run metadata without changing
the public static boundary.
