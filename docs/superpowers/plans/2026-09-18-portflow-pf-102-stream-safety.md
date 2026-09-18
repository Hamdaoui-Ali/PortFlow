# PF-102 Stream Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add restart-safe telemetry deduplication, bounded lateness handling, and canonical dead-letter publication to the existing local Redpanda consumer without changing PortFlow's public static product.

**Architecture:** Keep the existing manual-commit consumer and deterministic Bronze writer, adding a local SQLite state store keyed by TelemetryEvent.event_id and a transport-neutral DLQ envelope publisher. Each source batch is classified first, then accepted events are written to Bronze, state is committed, DLQ records are delivered, and only then is the source offset committed synchronously.

**Tech Stack:** Python 3.12, standard-library sqlite3, existing Pydantic TelemetryEvent, canonical JSON, confluent-kafka, Polars/Parquet, pytest, Ruff, mypy, Docker Compose Redpanda.

**Spec:** docs/superpowers/specs/2026-09-18-portflow-pf-102-stream-safety-design.md

## Global Constraints

- Keep the public PortFlow application static and snapshot-driven; the browser never connects to Redpanda, Kafka, SQLite, Parquet, or the local consumer.
- Keep PF-102 telemetry-only on the existing portflow.telemetry source topic plus portflow.telemetry.dlq; do not add alarm, incident, movement, weather, or other topic contracts.
- Use the existing TelemetryEvent model, canonical UTF-8 JSON, and the existing TABLE_SPECS["telemetry_events"] Bronze schema.
- Use event_id as the primary identity and store the SHA-256 digest of the canonical encoded event for conflict detection.
- Use <bronze-dir>/.stream-state.sqlite3 for disposable local state; do not add a Python database dependency.
- Set PORTFLOW_REDPANDA_DLQ_TOPIC=portflow.telemetry.dlq and PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS=300 as the defaults.
- Classify lateness against the topic watermark at the start of the source batch; events equal to watermark - allowed_lateness are accepted.
- Commit a source offset only after Bronze publication/state recording and all required DLQ publication succeed.
- Preserve at-least-once behavior; a crash before source commit may repeat a DLQ record, but accepted Bronze rows must be idempotent through the state store and existing partition hash check.
- Do not automatically scan or migrate old PF-101 Bronze partitions; document a clean disposable stream Bronze directory for PF-102 runs.
- Keep the local Compose service single-node and broker-optional tests unchanged unless the new DLQ integration requires a test-only topic.
- Write each test before its production implementation, observe the intended failure, keep each task independently testable, and commit each completed task separately.

---

## File Map

| File | Responsibility |
| --- | --- |
| src/portflow/streaming/config.py | Add DLQ topic and allowed-lateness configuration and validation. |
| src/portflow/streaming/state.py | Own SQLite schema, event lookups, outcome records, and topic watermark transactions. |
| src/portflow/streaming/dead_letter.py | Encode canonical DLQ envelopes and publish them through the existing producer protocol. |
| src/portflow/streaming/consumer.py | Classify messages, coordinate Bronze/state/DLQ ordering, and report outcomes. |
| src/portflow/streaming/codec.py | Reuse canonical event encoding for stable payload digests. |
| src/portflow/streaming/__init__.py | Export stable PF-102 public symbols only. |
| scripts/run_stream_consumer.py | Wire state and DLQ resources into the bounded local runner. |
| .env.example | Document the new DLQ and lateness variables. |
| tests/unit/test_streaming_config.py | Configuration defaults, rejection, and source/DLQ collision tests. |
| tests/unit/test_streaming_state.py | Persistence, transaction, conflict, and watermark tests. |
| tests/unit/test_streaming_dead_letter.py | Canonical envelope, byte preservation, headers, and delivery tests. |
| tests/unit/test_streaming_consumer.py | Duplicate, conflict, late, malformed, ordering, restart, and report tests. |
| tests/unit/test_streaming_compose.py | Runner/config contract tests for the expanded stream workflow. |
| tests/streaming/test_redpanda.py | Opt-in broker-backed source/DLQ round-trip and Silver compatibility. |
| docs/runbooks/local-streaming.md | Explain state, lateness, DLQ inspection, reset, and retry behavior. |
| README.md | Keep the local streaming boundary and PF-102 limitations visible. |
| docs/product/BACKLOG.md | Record PF-102 completion only after verification. |
| CHANGELOG.md | Record the PF-102 stream-safety release note. |

---

### Task 1: Extend the streaming configuration contract

**Files:**
- Modify: src/portflow/streaming/config.py
- Modify: .env.example
- Modify: tests/unit/test_streaming_config.py
- Modify: src/portflow/streaming/__init__.py

**Interfaces:**

Extend the frozen dataclass to:

~~~python
@dataclass(frozen=True, slots=True)
class StreamingConfig:
    brokers: str
    topic: str
    group_id: str
    batch_size: int
    dlq_topic: str
    allowed_lateness_seconds: int
~~~

StreamingConfig.from_env() must use these defaults:

~~~text
PORTFLOW_REDPANDA_BROKERS=localhost:19092
PORTFLOW_REDPANDA_TOPIC=portflow.telemetry
PORTFLOW_REDPANDA_GROUP=portflow-bronze
PORTFLOW_REDPANDA_DLQ_TOPIC=portflow.telemetry.dlq
PORTFLOW_STREAM_BATCH_SIZE=50
PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS=300
~~~

It must trim string values, reject empty source or DLQ topics, reject a DLQ topic equal to the source topic, reject non-integer or negative lateness, and preserve the existing broker/group/batch validation. The existing consumer_properties() and producer_properties() dictionaries remain unchanged.

- [ ] Step 1: Write failing configuration tests.

Add these assertions to tests/unit/test_streaming_config.py:

~~~python
def test_defaults_include_pf102_safety_values() -> None:
    assert StreamingConfig.from_env({}) == StreamingConfig(
        brokers="localhost:19092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
        dlq_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
    )


@pytest.mark.parametrize(
    "env",
    [
        {"PORTFLOW_REDPANDA_DLQ_TOPIC": ""},
        {"PORTFLOW_REDPANDA_TOPIC": "same", "PORTFLOW_REDPANDA_DLQ_TOPIC": "same"},
        {"PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS": "not-an-int"},
        {"PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS": "-1"},
    ],
)
def test_rejects_invalid_pf102_values(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        StreamingConfig.from_env(env)
~~~

Update direct StreamingConfig(...) constructions in the existing config, consumer, producer, and compose tests with the two new fields.

- [ ] Step 2: Run the focused tests to verify the intended failure.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py -q
~~~

Expected: FAIL because StreamingConfig does not yet accept dlq_topic and allowed_lateness_seconds.

- [ ] Step 3: Implement the minimal configuration change.

Add required-value parsing for the two topic values, parse lateness with int(), reject values below zero, and add the source/DLQ equality check. Add the two variables to .env.example next to the existing streaming variables. Export StreamingConfig as before; do not export implementation helpers.

- [ ] Step 4: Run tests and static checks.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/config.py tests/unit/test_streaming_config.py
~~~

Expected: all configuration tests pass and Ruff reports no errors.

- [ ] Step 5: Commit the configuration contract.

~~~powershell
git add src/portflow/streaming/config.py src/portflow/streaming/__init__.py .env.example tests/unit/test_streaming_config.py
git commit -m "build: configure PF-102 stream safety"
~~~

---

### Task 2: Add the durable SQLite stream state store

**Files:**
- Create: src/portflow/streaming/state.py
- Create: tests/unit/test_streaming_state.py
- Modify: src/portflow/streaming/codec.py

**Interfaces:**

Add a stable digest helper beside the existing codec:

~~~python
def telemetry_payload_sha256(event: TelemetryEvent) -> str:
    """Return the SHA-256 digest of encode_telemetry_event(event)."""
~~~

Create state.py with:

~~~python
@dataclass(frozen=True, slots=True)
class ProcessedEventState:
    event_id: str
    payload_sha256: str
    ingestion_timestamp: datetime
    outcome: Literal["bronze", "dead_letter"]
    reason_code: str | None


class StreamStateError(RuntimeError):
    """Raised when durable stream state cannot be read or updated safely."""


class StreamStateStore:
    def __init__(self, path: Path) -> None: ...
    def get_event(self, event_id: str) -> ProcessedEventState | None: ...
    def get_watermark(self, topic: str) -> datetime | None: ...
    def record_bronze(self, *, topic: str, events: Sequence[TelemetryEvent]) -> None: ...
    def record_dead_letter(self, *, topic: str, event: TelemetryEvent, reason_code: str) -> None: ...
    def close(self) -> None: ...
~~~

The constructor creates the parent directory and the two tables from the spec using UTC ISO-8601 text. Set PRAGMA synchronous=FULL and use explicit transactions. record_bronze() must insert each accepted event and update the topic watermark to the greatest ingestion_timestamp in one transaction. If any insert conflicts with a different digest, raise StreamStateError and roll back the whole transaction. record_dead_letter() inserts only valid non-conflicting events; it must reject an attempt to overwrite a different existing event state.

- [ ] Step 1: Write failing state-store tests.

Create tests for persistence, watermarking, dead-letter outcomes, conflict protection, and transaction rollback. The persistence test must close and reopen the same path:

~~~python
def test_state_survives_reopen_and_tracks_watermark(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    event = valid_event("evt-000042-000001", minute=0)

    store.record_bronze(topic="portflow.telemetry", events=[event])
    store.close()

    reopened = StreamStateStore(tmp_path / "state.sqlite3")
    saved = reopened.get_event(event.event_id)

    assert saved is not None
    assert saved.outcome == "bronze"
    assert saved.payload_sha256 == telemetry_payload_sha256(event)
    assert reopened.get_watermark("portflow.telemetry") == event.ingestion_timestamp
~~~

Add a rollback test that attempts to record a valid event and then a second event with the same event_id but a different payload in one record_bronze() call, asserts StreamStateError, and verifies neither event nor watermark was partially added.

- [ ] Step 2: Run state tests to verify the intended failure.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_state.py -q
~~~

Expected: FAIL because state.py and telemetry_payload_sha256() do not yet exist.

- [ ] Step 3: Implement the SQLite state store.

Use sqlite3.connect(path), create the schema with CREATE TABLE IF NOT EXISTS, and convert SQLite errors into StreamStateError without hiding the original exception. Use parameterized SQL only. Validate UTC timestamps before writing and normalize them with the existing cursor timestamp convention.

- [ ] Step 4: Run state tests, regression tests, and static checks.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_state.py tests/unit/test_cursor.py tests/unit/test_streaming_codec.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/state.py src/portflow/streaming/codec.py tests/unit/test_streaming_state.py
./.venv/Scripts/python.exe -m mypy src/portflow/streaming/state.py src/portflow/streaming/codec.py
~~~

- [ ] Step 5: Commit the durable state store.

~~~powershell
git add src/portflow/streaming/state.py src/portflow/streaming/codec.py tests/unit/test_streaming_state.py
git commit -m "feat: persist stream event state"
~~~

---

### Task 3: Add canonical dead-letter encoding and publication

**Files:**
- Create: src/portflow/streaming/dead_letter.py
- Create: tests/unit/test_streaming_dead_letter.py

**Interfaces:**

Implement the spec's transport-neutral types:

~~~python
@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    source_topic: str
    source_partition: int
    source_offset: int
    source_key: bytes | None
    source_value: bytes | None
    source_headers: Sequence[Header] | None
    reason_code: Literal["invalid_telemetry", "late_event", "duplicate_conflict"]
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
~~~

encode_dead_letter() must use sorted JSON keys, compact separators, ensure_ascii=False, UTF-8, and base64 for every binary field. Preserve source header order and null values. publish_dead_letters() must use the original source key when present, otherwise <topic>:<partition>:<offset>, add the two DLQ headers, call poll(0.0) after each produce(), flush once, and raise ProducerDeliveryError for callback failures or non-zero flush remainder.

- [ ] Step 1: Write failing dead-letter tests.

Create a record with non-ASCII reason text, a binary payload, a null header value, and an ordered header list. Assert the encoded JSON is deterministic and decodes back to the original bytes. Add a fake producer test:

~~~python
def test_publish_dead_letters_preserves_key_and_reason_header() -> None:
    producer = FakeProducer()
    record = dead_letter_record(source_key=b"evt-000042-000001")

    published = publish_dead_letters(
        [record],
        producer=producer,
        topic="portflow.telemetry.dlq",
    )

    assert published == 1
    assert producer.calls[0].topic == "portflow.telemetry.dlq"
    assert producer.calls[0].key == b"evt-000042-000001"
    assert producer.calls[0].headers == [
        ("portflow-dead-letter-reason", b"invalid_telemetry"),
        ("portflow-schema-version", b"1"),
    ]
    assert producer.flush_calls == [10.0]
~~~

Add tests for a missing source key fallback and a delivery callback error that raises ProducerDeliveryError.

- [ ] Step 2: Run dead-letter tests to verify the intended failure.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_dead_letter.py -q
~~~

Expected: FAIL because dead_letter.py does not exist.

- [ ] Step 3: Implement canonical envelope encoding.

Use base64.b64encode(value).decode("ascii") for non-null binary values and None for null values. Build the exact envelope field names from the spec; reject empty topic, run ID, reason, or unsupported reason code with ValueError before publishing.

- [ ] Step 4: Implement the delivery adapter and run tests.

Keep the module dependent on the existing ProducerClient protocol rather than importing confluent_kafka. Capture callback errors in a local list and construct no success result until both callback and flush checks pass.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_dead_letter.py tests/unit/test_streaming_producer.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/dead_letter.py tests/unit/test_streaming_dead_letter.py
./.venv/Scripts/python.exe -m mypy src/portflow/streaming/dead_letter.py
~~~

- [ ] Step 5: Commit dead-letter support.

~~~powershell
git add src/portflow/streaming/dead_letter.py tests/unit/test_streaming_dead_letter.py
git commit -m "feat: publish canonical stream dead letters"
~~~

---

### Task 4: Add PF-102 classification and commit ordering to the consumer

**Files:**
- Modify: src/portflow/streaming/consumer.py
- Modify: tests/unit/test_streaming_consumer.py
- Modify: src/portflow/streaming/__init__.py

**Interfaces:**

Extend ConsumerMessage with:

~~~python
def key(self) -> bytes | None: ...
def partition(self) -> int: ...
~~~

Extend consume_telemetry_stream() with these keyword arguments:

~~~python
dead_letter_producer: ProducerClient | None = None
dead_letter_topic: str | None = None
allowed_lateness_seconds: int = 300
state_store: StreamStateStore | None = None
~~~

Extend ConsumeReport with:

~~~python
duplicate_count: int
late_count: int
dead_letter_count: int
~~~

The consumer must count every non-EOF source message toward max_messages, including malformed, duplicate, late, and conflict records. It must own and close an internally-created state store, but must not close an injected test store. The existing consumer close behavior remains in finally.

- [ ] Step 1: Write failing consumer tests.

Extend FakeMessage with message_key and message_partition, and extend FakeProducer so its calls, flushes, and delivery errors can be inspected. Add these focused behaviors:

~~~python
def test_exact_duplicate_is_not_written_twice(tmp_path: Path) -> None:
    event = valid_event("evt-000042-000001", minute=0)
    consumer = FakeConsumer([message_for(event), message_for(event)])
    writer_calls: list[Sequence[TelemetryEvent]] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        writer_calls.append(events)
        return result_for(len(events), tmp_path)

    store_path = tmp_path / "state.sqlite3"
    first = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=2,
        writer=writer,
        state_store=StreamStateStore(store_path),
    )

    assert first.bronze_row_count == 1
    assert first.duplicate_count == 1
    assert len(writer_calls) == 1
~~~

Add separate tests proving:

- a changed payload with the same event ID publishes duplicate_conflict, leaves the first state intact, and does not call the writer;
- a boundary event is accepted and an event one microsecond beyond the late boundary is published as late_event;
- malformed bytes are published as invalid_telemetry and only then committed;
- missing DLQ dependencies fail before the writer or state store mutates;
- a writer failure, state failure, or DLQ delivery failure leaves commits empty;
- a batch containing only exact duplicates skips the writer;
- reopening a state store suppresses an event already written by a prior run;
- ConsumeReport counts source messages, Bronze rows, duplicates, late events, DLQ records, commits, and batches exactly.

- [ ] Step 2: Run consumer tests to verify the intended failure.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_consumer.py -q
~~~

Expected: FAIL because the fake message protocol, new consumer arguments, and PF-102 classification are not implemented.

- [ ] Step 3: Implement message classification.

Create small private helpers in consumer.py for:

1. extracting key() and partition() from the message;
2. constructing a DeadLetterRecord from raw message data;
3. comparing event digests against state and the current batch's pending map;
4. checking lateness against the watermark captured before the batch;
5. committing a classified batch in the exact Bronze -> state -> DLQ -> source commit order.

For StreamValidationError, retain the raw payload and headers and classify invalid_telemetry instead of raising directly. For valid late or conflict events, retain the TelemetryEvent only for state/report bookkeeping; never send a second payload schema to Bronze.

- [ ] Step 4: Implement safe batch finalization.

Before writing or recording anything, fail the batch if DLQ candidates exist without both a producer and topic. Then:

~~~text
accepted events -> existing writer -> state.record_bronze()
DLQ candidates -> publish_dead_letters() -> record valid non-conflicting DLQ events
last source message -> consumer.commit(asynchronous=False)
~~~

If the accepted list is empty, skip the writer. If a failure occurs, do not call commit() for that batch. Preserve the existing partition EOF and idle timeout behavior.

- [ ] Step 5: Run focused and regression tests.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_consumer.py tests/unit/test_streaming_state.py tests/unit/test_streaming_dead_letter.py tests/unit/test_streaming_producer.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/consumer.py src/portflow/streaming tests/unit/test_streaming_consumer.py
./.venv/Scripts/python.exe -m mypy src/portflow/streaming
~~~

- [ ] Step 6: Commit the consumer safety boundary.

~~~powershell
git add src/portflow/streaming/consumer.py src/portflow/streaming/__init__.py tests/unit/test_streaming_consumer.py
git commit -m "feat: make stream consumption restart safe"
~~~

---

### Task 5: Wire the bounded consumer runner and contract tests

**Files:**
- Modify: scripts/run_stream_consumer.py
- Modify: tests/unit/test_streaming_compose.py
- Modify: src/portflow/streaming/__init__.py

**Interfaces:**

The runner must derive the state path from the parsed Bronze directory:

~~~python
state_store = StreamStateStore(args.bronze_dir / ".stream-state.sqlite3")
dead_letter_producer = create_producer(config)
consume_telemetry_stream(
    consumer,
    topic=config.topic,
    bronze_dir=args.bronze_dir,
    run_id=args.run_id,
    batch_size=config.batch_size,
    max_messages=args.max_messages,
    dead_letter_producer=dead_letter_producer,
    dead_letter_topic=config.dlq_topic,
    allowed_lateness_seconds=config.allowed_lateness_seconds,
    state_store=state_store,
)
~~~

The runner must close the state store in a finally block. DLQ flushing is owned by publish_dead_letters() inside the consumer, so the runner must not add a second publication or flush. Keep the existing --max-messages, --run-id, and --bronze-dir CLI flags and sorted JSON report output.

- [ ] Step 1: Write failing runner/contract tests.

Add a test that patches StreamingConfig.from_env, create_consumer, create_producer, and consume_telemetry_stream, invokes main() with a temporary --bronze-dir, and asserts the exact DLQ topic, lateness value, and state path passed to the consumer. Add assertions that .stream-state.sqlite3 is excluded from the public data path and that the existing Compose service is still under the streaming profile.

- [ ] Step 2: Run the contract tests to verify the intended failure.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_compose.py -q
~~~

Expected: FAIL because the runner does not pass PF-102 dependencies.

- [ ] Step 3: Implement runner wiring and stable exports.

Import StreamStateStore, pass the configured PF-102 values, and close owned resources without masking the primary exception. Export StreamStateStore, DeadLetterRecord, encode_dead_letter, and publish_dead_letters only if they are intended stable public symbols; keep private helpers unexported.

- [ ] Step 4: Run runner, unit, and type checks.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_compose.py tests/unit/test_streaming_consumer.py -q
./.venv/Scripts/python.exe -m ruff check scripts/run_stream_consumer.py src/portflow/streaming tests/unit/test_streaming_compose.py
./.venv/Scripts/python.exe -m mypy scripts/run_stream_consumer.py src/portflow/streaming
~~~

- [ ] Step 5: Commit the bounded runner wiring.

~~~powershell
git add scripts/run_stream_consumer.py src/portflow/streaming/__init__.py tests/unit/test_streaming_compose.py
git commit -m "feat: wire PF-102 into the stream runner"
~~~

---

### Task 6: Extend the broker-backed round-trip coverage

**Files:**
- Modify: tests/streaming/test_redpanda.py
- Modify: scripts/verify_streaming.ps1 only if the focused test requires a new environment override

**Interfaces:**

Keep the existing redpanda marker and skip reason. Create unique source and DLQ topic names per test, pass both topics through copied StreamingConfig values, and keep the source topic one-partition/replication-one. Use the production producer, consumer, state store, and Bronze writer adapters.

- [ ] Step 1: Write the integration assertions before implementation changes.

Add a broker-backed scenario containing:

1. one accepted event;
2. the exact same event again;
3. a later accepted event that advances the watermark;
4. a valid event older than the five-minute window;
5. a changed payload reusing an accepted event ID;
6. malformed JSON with the expected source headers.

Assert the first run reports one exact duplicate, one late event, two dead letters for the conflict and malformed record, and only accepted events in Bronze. Read the DLQ topic and assert its envelopes preserve source topic, partition, offset, payload bytes, and reason codes. Start a second consumer group with the same Bronze directory and state path, consume the same source records, and assert that Bronze row count does not increase.

- [ ] Step 2: Run the integration test without a broker.

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/streaming/test_redpanda.py -m redpanda -q
~~~

Expected: the test skips with the existing clear broker-unavailable reason; it must not fail because the broker is absent.

- [ ] Step 3: Implement the broker-backed assertions and cleanup.

Use the existing AdminClient fixture pattern. Delete both unique topics in a finally block when they exist. Keep all generated Bronze data under the temporary test directory and do not write web/public/data.

- [ ] Step 4: Run broker-free static checks.

~~~powershell
./.venv/Scripts/python.exe -m ruff check tests/streaming/test_redpanda.py
python -c "import pathlib, yaml; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
~~~

- [ ] Step 5: Commit the integration coverage.

~~~powershell
git add tests/streaming/test_redpanda.py scripts/verify_streaming.ps1
git commit -m "test: verify PF-102 stream safety"
~~~

---

### Task 7: Document PF-102 operations and completion

**Files:**
- Modify: docs/runbooks/local-streaming.md
- Modify: README.md
- Modify: docs/product/BACKLOG.md
- Modify: CHANGELOG.md

**Interfaces:**

The runbook must document the exact defaults, state path, duplicate behavior, five-minute lateness rule, three DLQ reason codes, and the fact that the public browser remains static. Include PowerShell examples for a clean disposable stream directory, a consumer run, and DLQ inspection using the configured topic. Explain that source offsets remain uncommitted when Bronze or DLQ publication fails, and that a crash before source commit may repeat a malformed DLQ record.

- [ ] Step 1: Write documentation checks first.

Add or update documentation contract assertions so the runbook contains:

~~~text
PORTFLOW_REDPANDA_DLQ_TOPIC=portflow.telemetry.dlq
PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS=300
data/bronze-stream/.stream-state.sqlite3
invalid_telemetry
late_event
duplicate_conflict
~~~

Keep the PF-101 commands and static/public boundary language intact.

- [ ] Step 2: Update the runbook and README.

Add a reset section that says to remove only the disposable stream Bronze directory and state file when intentionally restarting a fixture. Do not suggest removing repository roots or public snapshot files. Add DLQ troubleshooting for missing topic/broker and state corruption.

- [ ] Step 3: Record PF-102 in the backlog and changelog.

Mark PF-102 complete only after the complete verification checkpoint. Preserve the existing PF-101 history and the outstanding main-branch-protection note.

- [ ] Step 4: Run documentation and whitespace checks.

~~~powershell
git diff --check
rg -n "PF-102|dead.?letter|late_event|duplicate_conflict|stream-state" README.md docs/runbooks/local-streaming.md docs/product/BACKLOG.md CHANGELOG.md
~~~

- [ ] Step 5: Commit documentation.

~~~powershell
git add README.md docs/runbooks/local-streaming.md docs/product/BACKLOG.md CHANGELOG.md
git commit -m "docs: document PF-102 stream safety"
~~~

---

### Task 8: Run the complete PF-102 verification checkpoint

**Files:**
- Read: docs/superpowers/specs/2026-09-18-portflow-pf-102-stream-safety-design.md
- Read: docs/superpowers/plans/2026-09-18-portflow-pf-102-stream-safety.md
- Verify: all PF-102 implementation and test files
- Verify: web/public/data remains unchanged

**Interfaces:**

No new interfaces are introduced in this task. It proves the PF-102 safety boundary without regressing PF-101, the local analytical pipeline, or the static product.

- [ ] Step 1: Run the focused PF-102 and PF-101 unit suite.

~~~powershell
python -m uv lock --check
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py tests/unit/test_streaming_state.py tests/unit/test_streaming_dead_letter.py tests/unit/test_streaming_producer.py tests/unit/test_streaming_consumer.py tests/unit/test_streaming_compose.py tests/unit/test_cursor.py tests/unit/test_telemetry_contract.py -q
./.venv/Scripts/python.exe -m ruff check src scripts tests/unit/test_streaming_config.py tests/unit/test_streaming_state.py tests/unit/test_streaming_dead_letter.py tests/unit/test_streaming_producer.py tests/unit/test_streaming_consumer.py tests/unit/test_streaming_compose.py
./.venv/Scripts/python.exe -m mypy src
~~~

Expected: all focused tests pass, Ruff is clean, mypy is clean, and no new dependency was added to pyproject.toml or uv.lock.

- [ ] Step 2: Run the real Redpanda verification when Docker is available.

~~~powershell
./scripts/verify_streaming.ps1
~~~

Expected: the Compose service reaches healthy, the source/DLQ round-trip passes, accepted rows remain Silver-compatible, and down -v removes only disposable local broker data. If Docker Desktop's Linux engine is unavailable, record the exact error and do not claim the real round-trip passed.

- [ ] Step 3: Run the existing data and frontend gates.

~~~powershell
./scripts/verify_r2.ps1
npm --prefix web test -- --run --maxWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
git diff --exit-code -- web/public/data
~~~

Expected: the existing pipeline and frontend gates remain green, and the public data directory is unchanged.

- [ ] Step 4: Inspect the final diff and status.

~~~powershell
git diff --check
git status --short --branch
git log -12 --oneline --decorate
~~~

Expected: no whitespace errors, no untracked state/database files, and only focused PF-102 commits plus the approved spec and plan documents are present.

## Completion checkpoint

Stop after Task 8. Report the PF-102 commit hashes, focused unit count, whether the real Redpanda round-trip ran or was skipped because Docker was unavailable, the existing V1 gate result, and that PF-103 remains the next streaming slice. Do not claim main branch protection was configured by this plan.
