# PF-103 Orchestration and Run Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, manually triggered Dagster consumer job that records durable run-level metadata in the existing SQLite stream state database.

**Architecture:** Extend `StreamStateStore` with a `stream_runs` table and typed lifecycle operations. Add an optional `src/portflow/orchestration/` package whose Dagster job wraps the existing `consume_telemetry_stream()` function, passes Dagster's `context.run_id` through as the canonical stream run ID, and records `running`, `succeeded`, or `failed` state without changing the consumer's commit ordering.

**Tech Stack:** Python 3.12, `sqlite3`, Dagster 1.x, `dagster-webserver` 1.x for optional local UI use, pytest, Ruff, mypy, uv, and the existing Confluent-compatible Redpanda clients.

**Spec:** `docs/superpowers/specs/2026-09-19-portflow-pf-103-orchestration-design.md`

## Global Constraints

- Keep the public browser static; do not modify React, CSS, routes, or `web/public/data`.
- Orchestrate the bounded consumer run only; do not orchestrate the deterministic producer or the PostgreSQL-to-Gold batch pipeline.
- Store run metadata at `configured-bronze-dir/.stream-state.sqlite3` in a `stream_runs` table.
- Use Dagster's `context.run_id` as the canonical run ID.
- Use only the lifecycle states `running`, `succeeded`, and `failed`.
- Record normalized non-secret inputs, result counters, timestamps, and terminal error details.
- Keep Dagster optional; do not add it to the core `[project].dependencies` list.
- Provide manual CLI/UI execution only; add no daemon, schedule, sensor, automatic retry, or always-on service.
- Keep the existing non-Dagster `scripts/run_stream_consumer.py` behavior unchanged; it must not create `stream_runs` rows.
- Preserve PF-102 source-commit ordering and at-least-once behavior; run metadata never authorizes a source commit.
- A failure while recording failure metadata must not replace the original consumer exception.
- Use `python -m uv ...` for Python commands and keep generated data outside committed public snapshots.

---

## File Map

Create or modify only the following files unless a test failure demonstrates a necessary, scoped addition:

- Modify `src/portflow/streaming/state.py` — define run models, initialize `stream_runs`, and implement lifecycle reads/writes.
- Modify `tests/unit/test_streaming_state.py` — cover run persistence, success/failure transitions, invalid transitions, and reopen behavior.
- Modify `pyproject.toml` — add the optional `orchestration` dependency group.
- Modify `uv.lock` — lock the optional Dagster dependencies.
- Create `src/portflow/orchestration/__init__.py` — keep the optional package boundary small and free of eager Dagster imports.
- Create `src/portflow/orchestration/streaming.py` — define the typed run configuration, execution service, Dagster op, and `stream_consumer_job`.
- Create `tests/unit/test_streaming_orchestration.py` — test the service and Dagster job with fake clients and a temporary SQLite store.
- Modify `docs/runbooks/local-streaming.md` — document optional installation, manual execution, run inspection, and disposable cleanup.
- Modify `README.md` — link the optional orchestration capability without changing the static/public boundary statement.
- Modify `CHANGELOG.md` — add the dated PF-103 local orchestration entry after verification.
- Modify `docs/product/BACKLOG.md` — mark PF-103 complete and set PF-104 as the next post-V1 slice only after all checks pass.

The existing `src/portflow/streaming/consumer.py` and `scripts/run_stream_consumer.py` should not change unless a small shared-helper extraction is required to avoid duplicated client wiring. If they change, add a focused regression test in the same task.

---

### Task 1: Add typed stream-run state to SQLite

**Files:**
- Modify: `src/portflow/streaming/state.py`
- Test: `tests/unit/test_streaming_state.py`

**Interfaces:**
- Consumes: existing `StreamStateStore`, `_SCHEMA`, UTC timestamp helpers, and `ConsumeReport` counter attributes.
- Produces: `StreamRunStatus`, `StreamRunInputs`, `StreamRun`, `StreamStateStore.start_run()`, `StreamStateStore.record_run_success()`, `StreamStateStore.record_run_failure()`, and `StreamStateStore.get_run()` for the orchestration task.

Define these state models in `state.py`:

```python
StreamRunStatus = Literal["running", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class StreamRunInputs:
    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float
    idle_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StreamRun:
    run_id: str
    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float
    idle_timeout_seconds: float
    status: StreamRunStatus
    started_at: datetime
    finished_at: datetime | None
    consumed_count: int | None
    bronze_row_count: int | None
    committed_count: int | None
    batch_count: int | None
    duplicate_count: int | None
    late_count: int | None
    dead_letter_count: int | None
    error_type: str | None
    error_message: str | None
```

Use a type-only quoted annotation for the success method if `state.py` needs the existing `ConsumeReport` type; do not create a runtime import cycle from `state.py` to `consumer.py`.

- [ ] **Step 1: Write failing state tests for starting and reopening a run.**

Add a test that creates a `StreamStateStore`, calls `start_run()` with a complete `StreamRunInputs`, closes and reopens the database, then asserts every input, `status == "running"`, a UTC `started_at`, null terminal fields, and `get_run(run_id)` returning the same `StreamRun`.

```python
def test_stream_run_persists_inputs_and_running_status(tmp_path: Path) -> None:
    inputs = StreamRunInputs(
        topic="portflow.telemetry",
        bronze_dir=tmp_path / "bronze",
        batch_size=2,
        max_messages=12,
        allowed_lateness_seconds=300,
        poll_timeout_seconds=1.0,
        idle_timeout_seconds=30.0,
    )
    store = StreamStateStore(tmp_path / "state.sqlite3")
    store.start_run(run_id="dagster-run-1", inputs=inputs)
    store.close()

    reopened = StreamStateStore(tmp_path / "state.sqlite3")
    run = reopened.get_run("dagster-run-1")

    assert run is not None
    assert run.status == "running"
    assert run.topic == inputs.topic
    assert run.bronze_dir == inputs.bronze_dir
    assert run.started_at.tzinfo == UTC
    assert run.finished_at is None
    assert run.error_type is None
```

- [ ] **Step 2: Run the new test to verify it fails.**

Run:

```powershell
python -m uv run pytest tests/unit/test_streaming_state.py::test_stream_run_persists_inputs_and_running_status -q
```

Expected: FAIL because `StreamRunInputs`, `start_run()`, and `get_run()` do not exist yet.

- [ ] **Step 3: Add the schema and running-state implementation.**

Extend `_SCHEMA` with:

```sql
CREATE TABLE IF NOT EXISTS stream_runs (
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

Implement:

```python
def start_run(self, *, run_id: str, inputs: StreamRunInputs) -> None: ...
def get_run(self, run_id: str) -> StreamRun | None: ...
```

Validate non-empty text, positive `batch_size` and `max_messages`, non-negative lateness and timeouts, and UTC timestamps. Use `datetime.now(UTC)` internally for `started_at`. Insert the row inside `with self._connection:` and translate SQLite failures to `StreamStateError`. A duplicate `run_id` must raise `StreamStateError` without overwriting the old row.

Add `_row_to_stream_run()` alongside `_row_to_event_state()` and convert `bronze_dir` back to `Path`, status through `StreamRunStatus`, and stored timestamps through `_parse_timestamp()`.

- [ ] **Step 4: Run the state test to verify it passes.**

Run:

```powershell
python -m uv run pytest tests/unit/test_streaming_state.py::test_stream_run_persists_inputs_and_running_status -q
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for terminal success, failure, and invalid transitions.**

Add tests that:

1. start a run, call `record_run_success()` with a `ConsumeReport`, reopen it, and assert all seven counters, `status == "succeeded"`, a UTC `finished_at`, and null error fields;
2. start a run, call `record_run_failure()` with `ValueError` and `"bad config"`, and assert `status == "failed"`, terminal timestamp, and exact error fields;
3. assert success/failure on an unknown or already-terminal run raises `StreamStateError` and does not overwrite the existing row;
4. assert a duplicate `start_run()` leaves the first row unchanged.

Use a fixed `finished_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)` so terminal assertions are deterministic.

- [ ] **Step 6: Run the terminal-transition tests to verify they fail.**

Run:

```powershell
python -m uv run pytest tests/unit/test_streaming_state.py -k "stream_run" -q
```

Expected: FAIL because the terminal methods and transition checks do not exist yet.

- [ ] **Step 7: Implement terminal lifecycle updates.**

Implement:

```python
def record_run_success(
    self,
    *,
    run_id: str,
    report: "ConsumeReport",
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
```

Update only rows where `run_id = ? AND status = 'running'`. If `cursor.rowcount != 1`, query the row and raise a precise `StreamStateError` for an unknown or terminal run. Wrap each update in an explicit SQLite transaction, validate `finished_at` as UTC, and keep all counters nullable for failed rows. Do not update event or watermark tables from these methods.

- [ ] **Step 8: Run the focused state suite and commit.**

Run:

```powershell
python -m uv run pytest tests/unit/test_streaming_state.py -q
python -m uv run ruff check src/portflow/streaming/state.py tests/unit/test_streaming_state.py
python -m uv run mypy src/portflow/streaming/state.py
```

Expected: all state tests pass, Ruff passes, and mypy reports no issues.

Commit:

```powershell
git add src/portflow/streaming/state.py tests/unit/test_streaming_state.py
git commit -m "feat: persist streaming run metadata"
```

### Task 2: Add the optional Dagster package boundary

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/portflow/orchestration/__init__.py`

**Interfaces:**
- Consumes: the existing Python 3.12 project and the approved optional dependency boundary.
- Produces: an installable `orchestration` extra and a package that does not import Dagster when the base package is used.

- [ ] **Step 1: Add the optional dependency group.**

Add this group without changing the core dependency list:

```toml
[project.optional-dependencies]
orchestration = [
  "dagster>=1.11,<2",
  "dagster-webserver>=1.11,<2",
]
```

Keep the existing `dev` extra unchanged. Create `src/portflow/orchestration/__init__.py` with only a module docstring; do not import `dagster` from `portflow/__init__.py` or `portflow/orchestration/__init__.py`.

- [ ] **Step 2: Refresh and validate the lockfile.**

Run:

```powershell
python -m uv lock
python -m uv sync --extra dev --extra orchestration
python -m uv run --extra dev --extra orchestration python -c "import dagster, dagster_webserver; print('orchestration dependencies available')"
```

Expected: `uv.lock` contains the optional resolution, the sync succeeds, and the import check prints the confirmation.

- [ ] **Step 3: Commit the dependency boundary.**

```powershell
git add pyproject.toml uv.lock src/portflow/orchestration/__init__.py
git commit -m "build: add optional Dagster orchestration extra"
```

### Task 3: Implement the typed consumer execution service

**Files:**
- Create: `src/portflow/orchestration/streaming.py`
- Test: `tests/unit/test_streaming_orchestration.py`

**Interfaces:**
- Consumes: `StreamRunInputs`, `StreamStateStore` lifecycle methods, `StreamingConfig`, `ConsumerClient`, `ProducerClient`, `create_consumer()`, `create_producer()`, and `consume_telemetry_stream()`.
- Produces: `StreamConsumerJobConfig`, `execute_stream_consumer_run()`, and the internal Dagster op/job built in Task 4.

Define the pure run configuration model:

```python
@dataclass(frozen=True, slots=True)
class StreamConsumerJobConfig:
    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float = 1.0
    idle_timeout_seconds: float = 30.0
```

Define injectable factory types so the service can be tested without Redpanda:

```python
ConsumerFactory = Callable[[StreamingConfig], ConsumerClient]
ProducerFactory = Callable[[StreamingConfig], ProducerClient]
StateStoreFactory = Callable[[Path], StreamStateStore]
```

Implement:

```python
def execute_stream_consumer_run(
    *,
    run_id: str,
    job_config: StreamConsumerJobConfig,
    env_config: StreamingConfig,
    consumer_factory: ConsumerFactory = create_consumer,
    producer_factory: ProducerFactory = create_producer,
    state_store_factory: StateStoreFactory = StreamStateStore,
) -> ConsumeReport: ...
```

The service must:

1. validate `run_id` and all `StreamConsumerJobConfig` values before opening broker clients;
2. derive the state path as `job_config.bronze_dir / ".stream-state.sqlite3"`;
3. create the state store and call `start_run()` before creating broker clients;
4. create an effective immutable `StreamingConfig` with `dataclasses.replace()` so the explicit Dagster `topic`, `batch_size`, and `allowed_lateness_seconds` are used while broker/group/DLQ settings come from `env_config`;
5. create the consumer and DLQ producer through the injected factories;
6. call `consume_telemetry_stream()` with `run_id`, all job-config timeouts, the effective topic/batch/lateness values, the state store, and the DLQ producer/topic;
7. call `record_run_success()` with the returned report and a UTC finish time;
8. wrap client setup and `consume_telemetry_stream()` in a failure boundary; on an exception from those phases, attempt `record_run_failure()` with `type(exc).__name__` and `str(exc)`, preserve the original exception if failure recording itself errors, and re-raise;
9. call `record_run_success()` in the success branch only; if that terminal metadata update fails, propagate the metadata error without attempting an invalid `failed` transition from `succeeded`;
10. close the state store in `finally`; rely on `consume_telemetry_stream()` to close the consumer once it has entered the consumer call, and close a consumer created before a producer-factory failure exactly once;
11. never record run metadata for the existing CLI path.

- [ ] **Step 1: Write the service tests before implementation.**

In `tests/unit/test_streaming_orchestration.py`, call `pytest.importorskip("dagster")` at module import so the base suite skips only this optional module when the extra is absent. Use the existing `FakeConsumer`/`FakeProducer` patterns from `tests/unit/test_streaming_consumer.py`, or define smaller fakes locally.

Add these tests:

```python
def test_execute_stream_consumer_run_records_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    report = ConsumeReport(
        consumed_count=2,
        bronze_row_count=2,
        committed_count=1,
        batch_count=1,
        duplicate_count=0,
        late_count=0,
        dead_letter_count=0,
    )

    def fake_consume(consumer: object, **kwargs: object) -> ConsumeReport:
        captured.update(kwargs)
        return report

    monkeypatch.setattr("portflow.orchestration.streaming.consume_telemetry_stream", fake_consume)
    run_id = "dagster-success-1"
    result = execute_stream_consumer_run(
        run_id=run_id,
        job_config=job_config(tmp_path),
        env_config=streaming_config(),
        consumer_factory=fake_consumer_factory,
        producer_factory=fake_producer_factory,
    )

    assert result == report
    assert captured["run_id"] == run_id
    saved = StreamStateStore(tmp_path / "bronze" / ".stream-state.sqlite3").get_run(run_id)
    assert saved is not None
    assert saved.status == "succeeded"
    assert saved.committed_count == 1
```

Use local helper functions `job_config()`, `streaming_config()`, `fake_consumer_factory`, and `fake_producer_factory` with complete return types; do not use a real broker.

Add a failure test that monkeypatches the consumer function to raise `RuntimeError("consumer exploded")`, asserts `pytest.raises(RuntimeError, match="consumer exploded")`, and then asserts the reopened state row is `failed` with `error_type == "RuntimeError"` and the same message. Add a second failure test with a fake state store whose `record_run_failure()` raises `RuntimeError("metadata unavailable")` and assert the original `RuntimeError("consumer exploded")` is still the raised exception.

- [ ] **Step 2: Run the service tests to verify they fail.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest tests/unit/test_streaming_orchestration.py -q
```

Expected: FAIL because `src/portflow/orchestration/streaming.py` does not exist.

- [ ] **Step 3: Implement `StreamConsumerJobConfig` and `execute_stream_consumer_run()`.**

Use `dataclasses.replace(env_config, topic=job_config.topic, batch_size=job_config.batch_size, allowed_lateness_seconds=job_config.allowed_lateness_seconds)` and reject an effective source/DLQ topic collision before `start_run()`. Build `StreamRunInputs` from the normalized job config. Use a small `_utc_now()` helper so success/failure timestamps are generated in one place.

When the consumer factory succeeds but the producer factory fails, close the consumer in the orchestration layer because `consume_telemetry_stream()` was not entered. When the consumer function is called, let it own consumer cleanup. Wrap failure metadata recording in a nested `try/except Exception` and use bare `raise` for the original exception.

- [ ] **Step 4: Run the service tests to verify they pass.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest tests/unit/test_streaming_orchestration.py -q
python -m uv run --extra dev --extra orchestration ruff check src/portflow/orchestration tests/unit/test_streaming_orchestration.py
python -m uv run --extra dev --extra orchestration mypy src
```

Expected: all service tests pass, Ruff passes, and mypy reports no issues.

### Task 4: Add the Dagster op and manual job

**Files:**
- Modify: `src/portflow/orchestration/streaming.py`
- Modify: `tests/unit/test_streaming_orchestration.py`

**Interfaces:**
- Consumes: `execute_stream_consumer_run()` and `StreamConsumerJobConfig` from Task 3.
- Produces: `consume_stream_op` and `stream_consumer_job` importable by Dagster CLI/UI.

- [ ] **Step 1: Write failing job-wiring tests.**

Add an optional-extra test that executes the job in process with a small `run_config` and monkeypatches `execute_stream_consumer_run()` to capture `context.run_id` and the `StreamConsumerJobConfig` values. Assert the job result is successful, the generated run ID is non-empty, and all seven configured fields reach the service unchanged.

```python
def test_stream_consumer_job_passes_dagster_run_id_and_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_execute(*, run_id: str, job_config: StreamConsumerJobConfig, **_: object) -> ConsumeReport:
        captured["run_id"] = run_id
        captured["job_config"] = job_config
        return successful_report()

    monkeypatch.setattr("portflow.orchestration.streaming.execute_stream_consumer_run", fake_execute)
    result = stream_consumer_job.execute_in_process(
        run_config={
            "ops": {
                "consume_stream": {
                    "config": {
                        "topic": "portflow.telemetry",
                        "bronze_dir": str(tmp_path / "bronze"),
                        "batch_size": 2,
                        "max_messages": 2,
                        "allowed_lateness_seconds": 300,
                        "poll_timeout_seconds": 0.1,
                        "idle_timeout_seconds": 1.0,
                    }
                }
            }
        },
    )

    assert result.success
    assert isinstance(captured["run_id"], str)
    assert captured["run_id"]
    assert captured["job_config"].max_messages == 2
```

Add a config-validation test for an empty topic, zero `max_messages`, negative lateness, negative poll timeout, and negative idle timeout. Each must fail before the service factory is called.

- [ ] **Step 2: Run the job tests to verify they fail.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest tests/unit/test_streaming_orchestration.py -k "job or config" -q
```

Expected: FAIL because the Dagster op and job are not defined.

- [ ] **Step 3: Implement the Dagster op and job.**

Use the Dagster 1.x `@op(config_schema=...)` and `@job` APIs. The op must read `context.op_config`, construct `StreamConsumerJobConfig`, call `StreamingConfig.from_env()`, and invoke:

```python
execute_stream_consumer_run(
    run_id=context.run_id,
    job_config=job_config,
    env_config=StreamingConfig.from_env(),
)
```

Use a single op name, `consume_stream`, and expose:

```python
@job
def stream_consumer_job() -> None:
    consume_stream()
```

Log the report counters through `context.log.info()` after a successful return. Do not expose credentials, raw environment mappings, or internal request values in logs. Let exceptions propagate so Dagster marks the job failed after the service records the failed run.

- [ ] **Step 4: Run the optional orchestration test suite.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest tests/unit/test_streaming_orchestration.py -q
python -m uv run --extra dev --extra orchestration ruff check src/portflow/orchestration tests/unit/test_streaming_orchestration.py
python -m uv run --extra dev --extra orchestration mypy src
```

Expected: all optional orchestration tests pass, Ruff passes, and mypy reports no issues.

- [ ] **Step 5: Commit the orchestration implementation.**

```powershell
git add src/portflow/orchestration/streaming.py tests/unit/test_streaming_orchestration.py
git commit -m "feat: add Dagster stream consumer job"
```

### Task 5: Document manual execution and preserve CLI boundaries

**Files:**
- Modify: `docs/runbooks/local-streaming.md`
- Modify: `README.md`
- Modify: `scripts/run_stream_consumer.py` only if the shared-helper extraction from Task 3 requires it

**Interfaces:**
- Consumes: the installed `orchestration` extra and `stream_consumer_job` module entry point.
- Produces: a reproducible manual runbook for optional Dagster execution and clear public/static boundary language.

- [ ] **Step 1: Add the optional installation and manual run config.**

Add a runbook subsection with these commands and settings:

```powershell
Set-Location C:/Users/aliha/PortFlow
python -m uv sync --extra dev --extra orchestration
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
$env:PORTFLOW_REDPANDA_GROUP = "portflow-bronze"
$env:PORTFLOW_REDPANDA_DLQ_TOPIC = "portflow.telemetry.dlq"
docker compose --profile streaming up -d --wait redpanda
```

Document the exact Dagster op config shape:

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

Show the manual CLI command with a user-created YAML file named `pf-103-run.yaml`:

```powershell
python -m uv run --extra dev --extra orchestration dagster job execute `
  -m portflow.orchestration.streaming `
  -j stream_consumer_job `
  -c pf-103-run.yaml
```

Explain that a local Dagster UI may be used instead of the CLI, but no daemon or schedule is required. Document SQLite inspection with the existing Bronze path and a short Python/SQLite query for `run_id`, `status`, `started_at`, `finished_at`, and error fields. State that null counters on failed rows are not proof that zero messages were processed.

- [ ] **Step 2: Document cleanup and the unchanged CLI.**

Keep the existing producer/consumer command block and explicitly state:

- `scripts/run_stream_consumer.py` remains non-Dagster and does not write `stream_runs`;
- Dagster run IDs are canonical only for Dagster-managed executions;
- `docker compose --profile streaming down -v redpanda` removes disposable broker state only;
- the browser remains static and `web/public/data` remains unchanged;
- no automatic retry is configured.

- [ ] **Step 3: Update README boundary language.**

Extend the local streaming paragraph with one sentence pointing to the optional Dagster runbook while preserving the statement that PF-102/PF-103 are local and the public browser remains snapshot-driven.

- [ ] **Step 4: Run documentation and existing streaming tests.**

Run:

```powershell
python -m uv run pytest tests/unit/test_streaming_compose.py tests/unit/test_streaming_state.py tests/unit/test_streaming_consumer.py -q
python -m uv run ruff check src scripts tests
```

Expected: the Python tests pass and Ruff passes. Verify Markdown changes with `git diff --check`.

- [ ] **Step 5: Commit documentation.**

```powershell
git add docs/runbooks/local-streaming.md README.md
git commit -m "docs: document PF-103 local orchestration"
```

### Task 6: Update release records after implementation verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/product/BACKLOG.md`

**Interfaces:**
- Consumes: verified PF-103 commit IDs and test results from Tasks 1–5.
- Produces: an auditable completed checkpoint without claiming main branch protection or a hosted orchestration service.

- [ ] **Step 1: Write the dated changelog entry.**

Add a `2026-09-19` PF-103 entry describing the optional local Dagster consumer job, durable run lifecycle metadata, manual execution, and the unchanged static/public boundary. State that producer orchestration, schedules, retries, and hosted Dagster remain out of scope.

- [ ] **Step 2: Update the backlog checkpoint.**

Under completed checkpoints, add PF-103 with the final implementation commit IDs and this scope: optional local Dagster consumer orchestration, canonical Dagster run IDs, SQLite run lifecycle metadata, manual execution, and broker-optional verification. Change `Current next action` to PF-104 engineering observability only after the complete verification gate passes. Preserve the existing note that the documented pull-request and green-CI branch-protection rule for `main` remains outstanding.

- [ ] **Step 3: Commit the release records.**

```powershell
git add CHANGELOG.md docs/product/BACKLOG.md
git commit -m "docs: record PF-103 orchestration"
```

### Task 7: Run the complete verification gate

**Files:**
- Verify: all PF-103 source, test, dependency, and documentation files
- Verify unchanged: `web/public/data`

**Interfaces:**
- Consumes: the final branch after Tasks 1–6.
- Produces: fresh evidence that PF-103 works without regressing PF-102, the full Python suite, lint, typing, or the public static product.

- [ ] **Step 1: Run focused PF-103 checks with the optional extra.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest tests/unit/test_streaming_state.py tests/unit/test_streaming_orchestration.py -q
python -m uv run --extra dev --extra orchestration ruff check src scripts tests
python -m uv run --extra dev --extra orchestration mypy src
```

Expected: all focused tests pass, Ruff passes, and mypy reports no issues.

- [ ] **Step 2: Run the full Python suite and confirm public data is unchanged.**

Run:

```powershell
python -m uv run --extra dev --extra orchestration pytest -q
git diff --exit-code -- web/public/data
```

Expected: the full suite passes; the public-data diff exits with code 0.

- [ ] **Step 3: Run the real Redpanda verification when Docker is available.**

Run:

```powershell
./scripts/verify_streaming.ps1
```

Expected: the broker-optional streaming checks pass when Docker's Linux engine is available. If Docker is unavailable, preserve the clear skip/blocker output and do not claim a real broker round trip passed.

- [ ] **Step 4: Run repository hygiene checks.**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected: no whitespace errors, no generated SQLite/Parquet files tracked, no changed `web/public/data`, and only the PF-103 implementation/spec/plan/documentation changes are present.

- [ ] **Step 5: Review the final diff and report evidence.**

Review:

```powershell
git log --oneline --decorate -12
git diff origin/main...HEAD --stat
git diff origin/main...HEAD -- docs/superpowers/specs/2026-09-19-portflow-pf-103-orchestration-design.md docs/superpowers/plans/2026-09-19-portflow-pf-103-orchestration.md
```

Report the final commit IDs, focused and full test counts, Ruff/mypy results, whether the Redpanda round trip ran or was skipped, and the unchanged public/static boundary. Do not claim PF-104 complete or main branch protection configured.

---

## Plan Self-Review

### Spec coverage

- Consumer-only streaming scope: Tasks 3 and 4.
- Run-level SQLite state and exact lifecycle states: Task 1.
- Dagster run ID propagation: Tasks 3 and 4.
- Optional dependency boundary: Task 2.
- Manual CLI/UI execution with no daemon, schedule, sensor, or retry: Tasks 4 and 5.
- Failure preservation and cleanup: Tasks 3 and 4.
- Existing CLI/public product compatibility: Tasks 5 and 7.
- Unit, optional orchestration, full regression, lint, typing, and broker verification: Tasks 1, 3, 4, and 7.
- Documentation, changelog, backlog, and next-slice transition: Tasks 5 and 6.

### Placeholder scan

The plan contains no unresolved placeholder markers or instruction to fill in unspecified behavior. Every task names exact files, interfaces, tests, commands, and expected results.

### Type consistency

- `StreamRunInputs` is defined in Task 1 and consumed by `start_run()` and Task 3.
- `StreamRun` is returned by `get_run()` and used by state tests and orchestration tests.
- `StreamConsumerJobConfig` is defined in Task 3 and passed from the Dagster op in Task 4.
- `execute_stream_consumer_run()` is defined in Task 3 and called by the op in Task 4.
- `stream_consumer_job` is exported by `streaming.py` and used by the runbook in Task 5.
- `ConsumeReport` remains owned by `src/portflow/streaming/consumer.py`; state annotations must avoid a runtime circular import.
