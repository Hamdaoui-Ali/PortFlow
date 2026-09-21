# PF-109 Stream Runs Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a bounded, read-only local stream-run history view to Data Health without changing the public snapshot or navigation contract.

**Architecture:** Read the existing SQLite stream_runs table through a dedicated observability read model. Expose its fixed ten-row payload through the loopback local API, then render that payload in an isolated React component under Data Health. Missing or unreadable local state is an explicit non-critical state and never changes snapshot health.

**Tech Stack:** Python 3.12, SQLite read-only URI connections, the existing http.server local API, React 18, TypeScript, Vitest, Testing Library, CSS, pytest, Ruff, and mypy.

**Spec:** docs/superpowers/specs/2026-09-21-portflow-pf-109-stream-runs-console-design.md

## Global Constraints

- The endpoint is GET /api/stream-runs and accepts no query parameters or request body.
- The response contains at most ten runs, ordered by started_at DESC and run_id DESC.
- The SQLite reader opens the resolved file with mode=ro, never creates or mutates it, and closes the connection in finally.
- The public browser remains snapshot-driven; web/public/data and the public route list are unchanged.
- No raw SQLite errors, stack traces, database URLs, credentials, bronze_dir, or polling settings reach the browser.
- React renders run IDs, topics, and bounded error text as text; it never renders HTML from the state file.
- Existing Data Health status, rejection evidence, local workspace behavior, and navigation labels remain unchanged.
- New interactive controls, if added later, must meet the existing 44 px target rule; this slice adds no row action.

## Review Focus

- Missing state path: return absent without creating the directory or file; pin this in the observability reader test.
- More than ten stored runs and equal timestamps: return exactly ten deterministic rows in the specified order; pin this in the reader test.
- A running run with no finish time: compute a non-negative duration from the injected UTC clock and return null outcome counters; pin this in the reader test.
- Corrupt SQLite content or invalid stored status/timestamp: return bounded malformed or unavailable data without a traceback; pin this in reader and API tests.
- Local API absence or abort during Data Health rendering: show a non-critical state and avoid stale state updates; pin this in the component tests.

---

### Task 1: Add the read-only stream-run history model

**Files:**
- Create: src/portflow/observability/runs.py
- Create: tests/unit/test_observability_runs.py

**Interfaces:**
- Consumes: the existing stream_runs SQLite table defined in src/portflow/streaming/state.py.
- Produces: RunHistoryStatus, STREAM_RUN_HISTORY_LIMIT, StreamRunSummary, StreamRunHistory, read_stream_runs(), and stream_run_history_payload() for the local API task.

- [ ] **Step 1: Write the failing reader tests**

Create a temporary SQLite fixture with the exact stream_runs schema used by PF-103. Add tests named:

The test module defines FIXED_NOW as 2026-09-21T12:00:00Z, a create_state_db(path, rows)
helper that creates the full schema and inserts rows with explicit values, and a state_path
fixture created by that helper. The payload test constructs one StreamRunSummary with the
same fixed timestamps before calling stream_run_history_payload().

~~~python
def test_missing_state_is_absent_and_does_not_create_any_path(tmp_path: Path) -> None:
    history = read_stream_runs(
        tmp_path / "missing" / ".stream-state.sqlite3",
        now=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    )

    assert history.status == "absent"
    assert history.runs == ()
    assert not (tmp_path / "missing").exists()


def test_history_is_limited_and_deterministic_for_equal_start_times(tmp_path: Path) -> None:
    # Insert twelve valid rows, including two with equal started_at values.
    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "ready"
    assert len(history.runs) == STREAM_RUN_HISTORY_LIMIT == 10
    assert [(run.started_at, run.run_id) for run in history.runs] == sorted(
        ((run.started_at, run.run_id) for run in history.runs), reverse=True
    )


def test_running_run_uses_injected_now_and_keeps_missing_counters_null(tmp_path: Path) -> None:
    history = read_stream_runs(state_path, now=FIXED_NOW)

    run = history.runs[0]
    assert run.duration_seconds == 30.0
    assert run.finished_at is None
    assert run.consumed_messages is None
    assert run.dead_letters is None


def test_error_text_is_normalized_and_bounded(tmp_path: Path) -> None:
    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.runs[0].error_message == "one two" + "x" * 280


def test_invalid_row_returns_malformed_without_leaking_storage_details(tmp_path: Path) -> None:
    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "malformed"
    assert history.runs == ()


def test_reader_preserves_state_file_bytes(tmp_path: Path) -> None:
    before = state_path.read_bytes()

    read_stream_runs(state_path, now=FIXED_NOW)

    assert state_path.read_bytes() == before


def test_payload_serializes_utc_timestamps_and_nulls() -> None:
    payload = stream_run_history_payload(history)

    assert payload["limit"] == 10
    assert payload["runs"][0]["started_at"].endswith("Z")
    assert payload["runs"][0]["finished_at"] is None
~~~

Use a real SQLite file rather than mocks. Keep fixture helpers local to this test file.

- [ ] **Step 2: Run the reader tests to verify they fail for the missing implementation**

Run:

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_observability_runs.py -q
~~~

Expected: collection fails because portflow.observability.runs and its public symbols do not exist yet.

- [ ] **Step 3: Implement the minimal read model**

Create immutable dataclasses with these exact fields:

~~~python
RunHistoryStatus = Literal["ready", "absent", "malformed", "unavailable"]
STREAM_RUN_HISTORY_LIMIT = 10

@dataclass(frozen=True, slots=True)
class StreamRunSummary:
    run_id: str
    topic: str
    status: StreamRunStatus
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float
    consumed_messages: int | None
    bronze_rows: int | None
    committed_batches: int | None
    duplicate_messages: int | None
    late_messages: int | None
    dead_letters: int | None
    error_type: str | None
    error_message: str | None

@dataclass(frozen=True, slots=True)
class StreamRunHistory:
    status: RunHistoryStatus
    limit: int
    runs: tuple[StreamRunSummary, ...]

read_stream_runs(state_path: Path, *, now: datetime) -> StreamRunHistory
stream_run_history_payload(history: StreamRunHistory) -> dict[str, object]
~~~

Implementation requirements:

1. Return absent before opening SQLite when state_path.is_file() is false.
2. Resolve the path and open f"{resolved.as_uri()}?mode=ro" with uri=True.
3. Select only the declared fields from stream_runs, ordered by started_at DESC, run_id DESC, with LIMIT 10 bound as a SQL parameter.
4. Validate status against running, succeeded, and failed, and parse every timestamp as UTC.
5. Compute max(0.0, (finished_at or now_utc - started_at).total_seconds()) with clear intermediate variables so running rows use the injected clock.
6. Preserve null counters and convert non-null counters to integers.
7. Normalize error_message with whitespace collapsing and slice the result to 280 characters; return None for empty text.
8. Return malformed for SQLite/schema/row contract errors and unavailable for filesystem/open errors. Both states contain no rows.
9. Close the read-only connection in finally.
10. Serialize datetimes with UTC Z suffixes and leave nullable fields as JSON nulls.

- [ ] **Step 4: Run the reader tests to verify they pass**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_observability_runs.py -q
~~~

Expected: all reader tests pass.

- [ ] **Step 5: Commit the read model**

~~~powershell
git add src/portflow/observability/runs.py tests/unit/test_observability_runs.py
git commit -m "feat: add read-only stream run history"
~~~

### Task 2: Expose stream history through the loopback API

**Files:**
- Modify: src/portflow/local_api.py: LocalApiConfig, LocalDataService, PostgresLocalDataService, dispatch_request
- Modify: scripts/run_local_api.py: LocalApiConfig construction
- Modify: tests/unit/test_local_api.py

**Interfaces:**
- Consumes: read_stream_runs() and stream_run_history_payload() from Task 1.
- Produces: LocalDataService.stream_runs() -> dict[str, object] and GET /api/stream-runs.

- [ ] **Step 1: Write failing API contract tests**

Extend the fake service used by tests/unit/test_local_api.py with stream_runs() and add tests for:

~~~python
def test_stream_runs_route_returns_read_model() -> None:
    response = dispatch_request(service, method="GET", path="/api/stream-runs")

    assert response.status == 200
    assert response.body == {
        "status": "ready",
        "limit": 10,
        "runs": [],
    }


def test_stream_runs_route_rejects_non_get_methods() -> None:
    response = dispatch_request(service, method="POST", path="/api/stream-runs", body=b"{}")

    assert response.status == 405
    assert response.body["error"] == "method_not_allowed"


def test_postgres_service_stream_runs_uses_configured_state_path(tmp_path: Path) -> None:
    service = PostgresLocalDataService(
        LocalApiConfig(
            database_url="postgresql://unused",
            output_dir=tmp_path / "public",
            stream_state_path=tmp_path / ".stream-state.sqlite3",
        )
    )

    response = service.stream_runs()

    assert response["status"] == "absent"
~~~

Add a dispatch test for an unavailable result and assert that its body contains only status, limit, and runs.

- [ ] **Step 2: Run the API tests to verify they fail**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_api.py -q
~~~

Expected: the fake service/configuration lacks the new method/field and the route returns 404 or 405.

- [ ] **Step 3: Implement the API wiring**

Make these exact changes:

1. Add stream_state_path: Path | None = None to LocalApiConfig.
2. Add stream_runs() to LocalDataService.
3. In PostgresLocalDataService.stream_runs(), choose config.stream_state_path or _repository_root() / data / bronze-stream / .stream-state.sqlite3, call read_stream_runs(state_path, now=datetime.now(UTC)), and return stream_run_history_payload(history).
4. Add /api/stream-runs: service.stream_runs to get_routes.
5. Add /api/stream-runs to known_paths so unsupported methods return 405.
6. Pass repository_root / data / bronze-stream / .stream-state.sqlite3 in scripts/run_local_api.py.
7. Do not call PostgreSQL from stream_runs(); missing database availability must not hide local stream history.

- [ ] **Step 4: Run the API tests to verify they pass**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_api.py -q
~~~

Expected: all local API tests pass.

- [ ] **Step 5: Commit the API contract**

~~~powershell
git add src/portflow/local_api.py scripts/run_local_api.py tests/unit/test_local_api.py
git commit -m "feat: expose stream runs through local api"
~~~

### Task 3: Add typed frontend API access

**Files:**
- Modify: web/src/data/localApi.ts
- Modify: web/src/data/localApi.test.ts

**Interfaces:**
- Consumes: JSON response from GET /api/stream-runs.
- Produces: StreamRunsStatus, StreamRunSummary, StreamRunsResponse, and LocalApiClient.getStreamRuns(signal?).

- [ ] **Step 1: Write failing client tests**

Add a fetcher test that returns the exact ready payload and asserts:

~~~typescript
expect(fetcher).toHaveBeenCalledWith("/api/stream-runs", {
  method: "GET",
  signal: expect.any(AbortSignal),
});
await expect(client.getStreamRuns(signal)).resolves.toEqual(payload);
~~~

Add an error test using the existing LocalApiError contract to prove non-2xx responses remain errors.

- [ ] **Step 2: Run the client tests to verify they fail**

Run from web:

~~~powershell
npm test -- --run src/data/localApi.test.ts
~~~

Expected: TypeScript/runtime failure because getStreamRuns is not on the client.

- [ ] **Step 3: Implement the typed endpoint**

Add these exact types:

~~~typescript
export type StreamRunsStatus = "ready" | "absent" | "malformed" | "unavailable";

export interface StreamRunSummary {
  run_id: string;
  topic: string;
  status: "running" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
  consumed_messages: number | null;
  bronze_rows: number | null;
  committed_batches: number | null;
  duplicate_messages: number | null;
  late_messages: number | null;
  dead_letters: number | null;
  error_type: string | null;
  error_message: string | null;
}

export interface StreamRunsResponse {
  status: StreamRunsStatus;
  limit: number;
  runs: StreamRunSummary[];
}
~~~

Add getStreamRuns(signal?: AbortSignal): Promise<StreamRunsResponse> to LocalApiClient and implement it with request("/stream-runs", { method: "GET", signal }).

- [ ] **Step 4: Run the client tests to verify they pass**

~~~powershell
npm test -- --run src/data/localApi.test.ts
~~~

Expected: all client tests pass with no type errors.

- [ ] **Step 5: Commit the frontend client contract**

~~~powershell
git add web/src/data/localApi.ts web/src/data/localApi.test.ts
git commit -m "feat: add stream runs api client"
~~~

### Task 4: Build the Stream Runs component with TDD

**Files:**
- Create: web/src/features/health/LocalStreamRuns.tsx
- Create: web/src/features/health/LocalStreamRuns.test.tsx

**Interfaces:**
- Consumes: LocalApiClient.getStreamRuns() from Task 3.
- Produces: LocalStreamRuns({ api?: LocalApiClient }) for DataHealthPage.

- [ ] **Step 1: Write failing component tests**

Use an injected fake LocalApiClient so tests exercise the component boundary without depending on a live server. Cover these exact behaviors:

Define resolvedApi(payload) in the test file as a LocalApiClient whose existing methods are
vi.fn() and whose getStreamRuns is vi.fn().mockResolvedValue(payload). Define
readyRunPayload as a StreamRunsResponse with run_id dagster-run-001, topic
portflow.telemetry, status succeeded, duration_seconds 10, consumed_messages 2,
bronze_rows 1, dead_letters null, and fixed UTC timestamps; all other counters are
explicitly 0 or null. For the abort test, use a deferred Promise<StreamRunsResponse>
whose resolver is called after unmount, and pass it through a second helper named
deferredApi. Both helpers must implement every method required by LocalApiClient.

~~~typescript
it("shows a checking message while the request is pending", () => {
  const api = { getStreamRuns: () => new Promise<StreamRunsResponse>(() => {}) } as LocalApiClient;
  render(<LocalStreamRuns api={api} />);

  expect(screen.getByRole("status", { name: "Checking local stream runs" })).toBeInTheDocument();
});

it("explains an absent state without marking Data Health invalid", async () => {
  render(<LocalStreamRuns api={resolvedApi({ status: "absent", limit: 10, runs: [] })} />);

  expect(await screen.findByText("No local stream runs yet.")).toBeInTheDocument();
  expect(screen.queryByText("Invalid")).not.toBeInTheDocument();
});

it("renders a ready table with accessible status and nullable counters", async () => {
  render(<LocalStreamRuns api={resolvedApi(readyRunPayload)} />);

  const table = await screen.findByRole("table", { name: "Latest stream runs" });
  expect(within(table).getByRole("row", { name: /Succeeded.*dagster-run-001/ })).toBeInTheDocument();
  expect(within(table).getByText("Unavailable")).toBeInTheDocument();
  expect(within(table).getByText("2")).toBeInTheDocument();
});

it.each(["malformed", "unavailable"] as const)("shows a bounded %s state", async (status) => {
  render(<LocalStreamRuns api={resolvedApi({ status, limit: 10, runs: [] })} />);

  expect(await screen.findByRole("status")).toHaveTextContent("local stream run history");
});

it("does not update state after an aborted request", async () => {
  const api = abortAwareApi();
  const { unmount } = render(<LocalStreamRuns api={api} />);

  unmount();
  await api.resolveAfterAbort();
  expect(screen.queryByText("No local stream runs yet.")).not.toBeInTheDocument();
});
~~~

Use fixed ISO timestamps and set the test timezone if visible date text is asserted. Prefer semantic roles, run IDs, counters, and time[datetime] attributes over locale-specific formatting.

- [ ] **Step 2: Run the component tests to verify they fail**

~~~powershell
npm test -- --run src/features/health/LocalStreamRuns.test.tsx
~~~

Expected: module/component import failure because LocalStreamRuns does not exist.

- [ ] **Step 3: Implement the minimal accessible component**

Implement LocalStreamRuns({ api = createLocalApi() }) with:

1. one useEffect and AbortController that calls api.getStreamRuns(controller.signal) once;
2. no state update for AbortError, with cleanup calling controller.abort();
3. a section labelled Local stream observability with heading Stream runs;
4. status messages for checking, absent, malformed, and unavailable;
5. a semantic table with caption/name Latest stream runs and headers Status, Started, Duration, Messages, Bronze rows, and Dead letters;
6. a status cell containing human-readable status, run ID, and topic as text;
7. null counters rendered as Unavailable;
8. bounded error detail rendered as escaped text below a failed row;
9. no aria-live on the page or table and no change to DataHealthPage health model.

Use small pure helpers for status labels, count formatting, duration formatting, and timestamp formatting so the render function stays below the project complexity threshold.

- [ ] **Step 4: Run the component tests to verify they pass**

~~~powershell
npm test -- --run src/features/health/LocalStreamRuns.test.tsx
~~~

Expected: all component tests pass.

- [ ] **Step 5: Commit the component**

~~~powershell
git add web/src/features/health/LocalStreamRuns.tsx web/src/features/health/LocalStreamRuns.test.tsx
git commit -m "feat: add local stream runs view"
~~~

### Task 5: Integrate Data Health and responsive styling

**Files:**
- Modify: web/src/features/health/DataHealthPage.tsx
- Modify: web/src/features/health/DataHealthPage.test.tsx
- Modify: web/src/styles.css

**Interfaces:**
- Consumes: LocalStreamRuns from Task 4.
- Produces: Stream Runs visible below existing Data Health sections without changing HealthViewModel or navigation.

- [ ] **Step 1: Write the failing integration assertion**

Add a Data Health test that renders the existing healthy fixture and asserts the new section
heading is present while Healthy, Pipeline status, the rejection table, and the local
workspace contract remain present. The heading is static and must be asserted synchronously;
the component's failed fetch state is covered by LocalStreamRuns.test.tsx, so the page test
does not need a second network mock.

- [ ] **Step 2: Run the integration test to verify it fails**

~~~powershell
npm test -- --run src/features/health/DataHealthPage.test.tsx
~~~

Expected: the new Stream runs heading is not found.

- [ ] **Step 3: Integrate and style the section**

Render LocalStreamRuns after LocalDataWorkspace in DataHealthPage. Add styles using existing tokens:

~~~css
.stream-runs { max-width: 1180px; margin-top: 44px; padding-top: 28px; border-top: 1px solid var(--border); }
.stream-runs-header { max-width: 720px; }
.stream-runs-table-scroll { overflow-x: auto; margin-top: 18px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.stream-runs-table { width: 100%; min-width: 720px; border-collapse: collapse; font-size: 13px; }
~~~

Continue the existing table, divider, status-color, focus, and mobile overflow patterns. Add responsive rules so the page has no viewport overflow and status/counter text remains readable below 900 px. Do not add a new navigation link or a card-grid transformation.

- [ ] **Step 4: Run focused frontend tests and typecheck**

~~~powershell
npm test -- --run src/features/health/DataHealthPage.test.tsx src/features/health/LocalStreamRuns.test.tsx
npm run typecheck
~~~

Expected: focused tests and TypeScript checks pass.

- [ ] **Step 5: Commit the integration**

~~~powershell
git add web/src/features/health/DataHealthPage.tsx web/src/features/health/DataHealthPage.test.tsx web/src/styles.css
git commit -m "feat: integrate stream runs into data health"
~~~

### Task 6: Document the local-only workflow

**Files:**
- Modify: docs/runbooks/local-streaming.md
- Modify: README.md
- Modify: tests/unit/test_observability_docs.py

**Interfaces:**
- Consumes: the shipped endpoint and Data Health UI from Tasks 2 and 5.
- Produces: operator documentation that keeps PF-109 local, optional, and distinct from Grafana.

- [ ] **Step 1: Write failing documentation assertions**

Add assertions that the runbook and README contain:

~~~python
assert "/api/stream-runs" in local_streaming
assert "Stream runs" in local_streaming
assert "does not change the published snapshot" in local_streaming
assert "Data Health" in readme
assert "PF-109" in readme
~~~

- [ ] **Step 2: Run documentation tests to verify they fail**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_observability_docs.py -q
~~~

Expected: the new endpoint and PF-109 text are absent.

- [ ] **Step 3: Update the runbook and README**

Add a PF-109 Stream Runs console section to docs/runbooks/local-streaming.md that states:

1. start the existing local API and open Data Health;
2. the page reads GET /api/stream-runs from the loopback API;
3. an absent state is expected before the first Dagster-managed run;
4. malformed/unavailable state does not invalidate the published snapshot;
5. the view is limited to ten recent runs and Grafana remains the detailed metrics surface;
6. the public browser remains static and no credentials are used.

Update the README local streaming paragraph with a one-sentence PF-109 pointer. Keep existing scope and credential language intact.

- [ ] **Step 4: Run documentation tests to verify they pass**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_observability_docs.py -q
~~~

Expected: all documentation assertions pass.

- [ ] **Step 5: Commit the documentation**

~~~powershell
git add docs/runbooks/local-streaming.md README.md tests/unit/test_observability_docs.py
git commit -m "docs: document PF-109 stream runs console"
~~~

### Task 7: Record the completed post-V1 slice

**Files:**
- Modify: docs/product/BACKLOG.md

**Interfaces:**
- Consumes: completed implementation and verification evidence from Tasks 1–6.
- Produces: a truthful completed PF-109 checkpoint with commit IDs and explicit non-goals.

- [ ] **Step 1: Update the backlog**

Add PF-109 to the post-V1 list as complete only after the implementation commits are known. Record the final implementation commit IDs, the fixed ten-row read-only endpoint, the Data Health section, and the fact that no public snapshot, hosted API, or new route changed. Update Current next action to state that PF-109 is complete and no subsequent post-V1 spec is currently approved rather than inventing another feature.

- [ ] **Step 2: Run the owning documentation tests**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_ci_quality_gate.py tests/unit/test_observability_docs.py -q
~~~

Expected: all tests pass.

- [ ] **Step 3: Commit the backlog checkpoint**

~~~powershell
git add docs/product/BACKLOG.md
git commit -m "docs: close PF-109 stream runs console"
~~~

### Task 8: Run the complete verification gate

**Files:**
- No intended product changes; only fix issues discovered by verification in the owning task commit.

- [ ] **Step 1: Run focused Python verification**

~~~powershell
$envLines = docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' portflow-postgres-1
$databasePassword = ($envLines | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' } | Select-Object -First 1) -replace '^POSTGRES_PASSWORD=', ''
$env:PORTFLOW_POSTGRES_PASSWORD = $databasePassword
$env:PORTFLOW_DATABASE_URL = "postgresql://portflow:$databasePassword@localhost:5433/portflow"
$env:PATH = "$((Get-Location).Path)\\.venv\\Scripts;$env:PATH"
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_observability_runs.py tests/unit/test_local_api.py tests/unit/test_observability_docs.py -q
~~~

Expected: focused Python tests pass.

- [ ] **Step 2: Run focused frontend verification**

~~~powershell
Set-Location web
npm test -- --run src/data/localApi.test.ts src/features/health/LocalStreamRuns.test.tsx src/features/health/DataHealthPage.test.tsx
npm run typecheck
Set-Location ..
~~~

Expected: focused frontend tests and typecheck pass.

- [ ] **Step 3: Run the full Python suite with the existing disposable PostgreSQL service**

~~~powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
~~~

Expected: all available Python tests pass with only the repository explicit environment skips.

- [ ] **Step 4: Run Ruff, mypy, frontend tests, and build**

~~~powershell
ruff check src tests scripts labs benchmarks
mypy src
Set-Location web
npm test -- --run
npm run typecheck
npm run build
Set-Location ..
~~~

Expected: all commands exit zero.

- [ ] **Step 5: Confirm the public snapshot boundary**

~~~powershell
git diff --exit-code -- web/public/data
git diff --check origin/main...HEAD
~~~

Expected: no public data diff and no whitespace errors.

- [ ] **Step 6: Run the repository verification script**

~~~powershell
./scripts/verify_r2.ps1
~~~

Expected: deterministic snapshot verification, Python tests, Ruff, mypy, frontend tests, typecheck, build, and budgets all pass. If the local Lighthouse metric is noisy, record the exact measurement and rely on the authoritative GitHub run only after PR checks pass; do not alter budgets to hide variance.

- [ ] **Step 7: Commit only verification-driven fixes**

If a verification command identifies an implementation defect, add a failing regression test first, fix the smallest owning unit, rerun the affected command, and commit the exact test and source files that changed with a specific message such as fix: bound stream run history error state. Do not amend earlier commits; preserve the feature's reviewable commit sequence.
