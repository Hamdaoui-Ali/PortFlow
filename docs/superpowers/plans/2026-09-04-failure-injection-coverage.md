# PF-025 Failure-Injection Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic evidence that PortFlow isolates pipeline and snapshot failures, preserves valid state, and exposes frontend recovery states without fabricated values.

**Architecture:** Add focused Python resilience tests around the existing cursor, Bronze/Silver, and public-export seams, using temporary directories and injected failures. Add a dedicated frontend failure-state suite that renders the real `App` with an injected `loadSnapshot` fetcher, while keeping it out of the normal frontend suite unless an explicit failure-test environment is present. Production changes are limited to behavior proven missing by a failing test.

**Tech Stack:** Python 3.12, pytest, psycopg, Polars, DuckDB, React, Vitest, Testing Library, jsdom, Zod.

**Spec:** `docs/superpowers/specs/2026-09-04-failure-injection-coverage-design.md`

## Global Constraints

- Tests remain local and deterministic; no browser runner, network access, or hosted deployment.
- No new failure semantics unless a failing contract test requires the smallest production fix.
- No test may silently substitute a KPI when a required dataset is unavailable.
- Tests are written first and must be observed failing for the intended reason.
- Preserve separate commits for pipeline resilience, frontend resilience, runner/configuration, and backlog documentation.

---

### Task 1: Add Python failure-injection test fixtures

**Files:**
- Create: `tests/resilience/conftest.py`
- Create: `tests/resilience/test_cursor_recovery.py`
- Create: `tests/resilience/test_silver_recovery.py`
- Create: `tests/resilience/test_export_recovery.py`

**Interfaces:**
- Consumes: `CursorStore.save`, `extract_table`, `transform_bronze_to_silver`, `write_public_snapshot`, and existing test factories/fixtures.
- Produces: Executable evidence for cursor preservation, quarantine reconciliation, and immutable snapshot publication.

- [ ] **Step 1: Write failing cursor and staging tests**

Create tests that:

```python
def test_cursor_replacement_failure_preserves_previous_file(tmp_path):
    path = tmp_path / "state" / "cursors.json"
    store = CursorStore(path)
    previous = SourceCursor(datetime(2026, 9, 2, tzinfo=UTC), "row-001")
    store.save({"telemetry_events": previous})

    def fail_replace(*args, **kwargs):
        raise OSError("simulated cursor replacement failure")

    with pytest.raises(OSError, match="simulated cursor replacement failure"):
        store.save({"telemetry_events": SourceCursor(datetime(2026, 9, 2, 0, 5, tzinfo=UTC), "row-002")}, replace=fail_replace)

    assert store.load() == {"telemetry_events": previous}
    assert not path.with_name("cursors.json.tmp").exists()
```

Add the extraction-level assertion from `tests/integration/test_bronze_extraction.py`: seed PostgreSQL, monkeypatch `Path.replace` to raise `OSError`, call `extract_table` for `telemetry_events`, then assert `read_cursor(..., "telemetry_events") is None` and `not list((bronze_dir).rglob("*.parquet"))`.

- [ ] **Step 2: Run the focused tests and confirm the intended RED result**

Run:

```powershell
$env:Path="C:\Users\aliha\AppData\Local\Programs\Python\Python312\Scripts;" + $env:Path
py -3.12 -m pytest tests/resilience/test_cursor_recovery.py -q
```

Expected: the focused tests either pass against the existing atomic implementation or fail with a concrete assertion showing which recovery guarantee is absent. Do not continue until every RED result identifies a missing behavior or an incorrect test seam precisely.

- [ ] **Step 3: Add Silver duplicate and invalid-reference tests**

Write small Parquet inputs under `tmp_path / "bronze"` containing one valid row plus either a superseded duplicate or an equipment/terminal reference that is absent from the input set. Assert the returned `SilverRunReport` fields, stable reason codes (`DUPLICATE_KEY` or `REFERENCE_INVALID`), absence of rejected rows from Silver, and:

```python
assert report.bronze_rows == report.silver_rows + report.quarantine_rows
```

- [ ] **Step 4: Add public snapshot immutability tests**

Reuse `tests.integration.test_public_export.gold_db` and `source_metadata()`, publish `demo-v2` once, snapshot the manifest and every dataset byte, monkeypatch `portflow.export.writer._write_bytes` to raise on the next export, and assert the original bytes remain unchanged and `.staging/demo-v2` is absent after the exception.

- [ ] **Step 5: Implement only required pipeline fixes**

If a RED test proves a production gap, update the narrowest existing seam. Keep `CursorStore.save` atomic, preserve the old file on replacement failure, and ensure export staging is removed without replacing the target snapshot. Do not add a retry loop or a new resilience abstraction.

- [ ] **Step 6: Run the Python resilience tests and commit**

Run:

```powershell
$env:Path="C:\Users\aliha\AppData\Local\Programs\Python\Python312\Scripts;" + $env:Path
py -3.12 -m pytest tests/resilience -q
```

Expected: all focused resilience tests pass.

Commit:

```powershell
git add tests/resilience src/portflow
git commit -m "test: cover pipeline failure recovery"
```

### Task 2: Add frontend failure-state fixture harness

**Files:**
- Create: `web/e2e/failure-states.spec.tsx`
- Modify: `web/vite.config.ts`

**Interfaces:**
- Consumes: `App`, `loadSnapshot`, `SnapshotLoadError`, `snapshotCache`, and the existing jsdom setup.
- Produces: A dedicated suite that can construct manifest/data responses and verify visible error, stale, empty, unavailable, and malformed states.

- [ ] **Step 1: Write the failing frontend cases**

Create an in-memory fetcher keyed by URL suffix, plus valid snapshot fixtures. Add cases for:

```typescript
it("shows an unavailable state when the manifest cannot be fetched", async () => {
  render(<App loadData={() => loadSnapshot(async () => new Response(null, { status: 503 }), "/PortFlow/")} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Operational snapshot unavailable");
  expect(screen.queryByText(/moves$/)).not.toBeInTheDocument();
});
```

Add one test per case: malformed manifest (`{}`), empty overview (`scheduled_intervals: 0`), missing optional equipment (manifest without `equipment`), malformed incidents (an unexpected field), malformed replay (invalid event schema), stale manifest (`generated_at` older than the health threshold), stale-cache recovery after `snapshotCache.set(validSnapshot)`, and a valid follow-up load that replaces the cached snapshot. Assert the exact `SnapshotFailureKind` or dataset state and visible labels, plus preservation of the Overview KPI when only an optional dataset fails.

- [ ] **Step 2: Run the dedicated cases and confirm RED behavior**

Run with the explicit mode enabled:

```powershell
$env:PORTFLOW_FAILURE_TESTS="1"
npm.cmd test -- --run e2e/failure-states.spec.tsx --pool=forks --maxWorkers=1
```

Expected: the suite reports the exact missing label/state for any unsupported behavior; existing PF-016 cases may pass. Record the failures before changing production code.

- [ ] **Step 3: Implement the minimum frontend recovery fixes**

Use the existing `SnapshotState` and `SnapshotCache` boundaries. Preserve the last valid snapshot on a later `SnapshotLoadError`, keep malformed optional datasets isolated to their dataset state, and retain the existing no-fabrication behavior for required overview failures. Do not change copy or route layout beyond the labels needed by the contract tests.

- [ ] **Step 4: Gate the dedicated suite without hiding explicit runs**

Update `web/vite.config.ts` so `e2e/failure-states.spec.tsx` is excluded when neither `PORTFLOW_FAILURE_TESTS` nor `PORTFLOW_RECONCILIATION_DIR` is set. When either variable is set, remove only the matching dedicated suite from the exclusion list; keep PF-024’s explicit reconciliation mode behavior intact and keep the normal suite independent of fixture data.

- [ ] **Step 5: Run frontend verification and commit**

Run:

```powershell
npm.cmd test -- --run e2e/failure-states.spec.tsx --pool=forks --maxWorkers=1
npm.cmd test -- --run --pool=forks --maxWorkers=1
```

Expected: the dedicated failure suite and the normal frontend suite both pass.

Commit:

```powershell
git add web/e2e/failure-states.spec.tsx web/src web/vite.config.ts
git commit -m "test: cover frontend failure states"
```

### Task 3: Run the PF-025 completion gate

**Files:**
- Modify: `docs/product/BACKLOG.md`

**Interfaces:**
- Consumes: the committed Python and frontend resilience suites.
- Produces: Green verification evidence and backlog advancement to PF-026.

- [ ] **Step 1: Run all Python tests**

```powershell
$env:Path="C:\Users\aliha\AppData\Local\Programs\Python\Python312\Scripts;" + $env:Path
py -3.12 -m pytest -q
```

Expected: all Python tests pass.

- [ ] **Step 2: Run frontend tests, typecheck, build, and Pages verification**

```powershell
npm.cmd test -- --run --pool=forks --maxWorkers=1
npm.cmd run typecheck
$env:VITE_BASE_PATH="/PortFlow/"
npm.cmd run build
npm.cmd run verify:pages
```

Expected: normal frontend tests pass, TypeScript passes, the production build succeeds, and Pages assets/data paths are verified.

- [ ] **Step 3: Update the backlog**

Change `docs/product/BACKLOG.md` so Current next action names PF-026, and add the PF-025 implementation commit hashes to Completed checkpoints. Do not mark PF-026 complete.

- [ ] **Step 4: Commit documentation and inspect the diff**

```powershell
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog to performance budgets"
git status --short
git diff main...HEAD --check
```

Expected: clean working tree and no whitespace errors.
