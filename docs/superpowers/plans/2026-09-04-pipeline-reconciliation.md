# Pipeline Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one deterministic PortFlow input across PostgreSQL, Bronze, Silver, quarantine, Gold, public JSON, and the browser UI.

**Architecture:** The Python E2E test owns a pytest temporary directory, runs the existing pipeline stages, and verifies the generated manifest and datasets. While that directory is alive, it invokes a dedicated Vitest suite with `PORTFLOW_RECONCILIATION_DIR`; the browser suite uses the existing `loadSnapshot` contract and real `App` against those exact exported files.

**Tech Stack:** Python 3.12, pytest, psycopg, Polars, dbt-duckdb, DuckDB, React 19, TypeScript, Vitest, Testing Library, and the existing static snapshot schema.

**Spec:** `docs/superpowers/specs/2026-09-04-pipeline-reconciliation-design.md`

## Global Constraints

- Do not change production pipeline behavior, snapshot schemas, routes, public data, or the browser interaction model.
- Do not add a browser E2E framework.
- Reconcile the required datasets `overview`, `equipment`, `incidents`, `event_replay`, and `quality`.
- Use the exact generated JSON export as the browser test input; do not create a browser-only replacement fixture.
- Keep temporary artifacts under test-managed directories and remove them after the test run.
- Preserve separate commits for Python reconciliation, browser reconciliation, test-runner support, and backlog advancement.

---

### Task 1: Reconcile the Python pipeline and public export

**Files:**
- Create: `tests/e2e/test_pipeline_reconciliation.py`
- Read: `tests/integration/test_gold.py`, `tests/integration/test_public_export.py`, `src/portflow/pipeline.py`, `src/portflow/seed.py`
- Test: `tests/e2e/test_pipeline_reconciliation.py`

**Interfaces:**
- Consumes the existing `database_url` and `tmp_path` fixtures, `seed_operational`, `extract_table`, `transform_bronze_to_silver`, `run_dbt`, and `write_public_snapshot`.
- Produces a temporary export directory containing `manifest.json` and all five referenced datasets for Task 2.

- [ ] **Step 1: Write the failing reconciliation test**

Create one test that seeds `42`, extracts every table in `TABLE_SPECS` into `tmp_path / "bronze"`, transforms to `tmp_path / "silver"` and `tmp_path / "quarantine"`, builds `tmp_path / "gold" / "portflow.duckdb`, and exports to `tmp_path / "public" / "data"` with snapshot ID `demo-v2` and the existing deterministic period.

Assert the source report has the stable seed counts from `seed_operational`, the Silver report satisfies `bronze_rows == silver_rows + quarantine_rows` with zero quarantine rows, and Gold contains 288 telemetry rows, 2 incidents, 8 movements, and overview values `(throughput=4, active_incidents=1, critical_alarms=1)`.

Read `manifest.json` and assert the exact dataset set, `snapshot_id == "demo-v2"`, `quality_status == "PASS"`, `record_counts == {"telemetry": 288, "equipment": 1, "incidents": 2, "event_replay": 288, "quality": 1}`, and the expected source period `2026-09-02T00:00:00Z` through `2026-09-02T23:55:00Z`. For each manifest entry, hash the referenced bytes and compare to `sha256`.

Read the exported JSON and assert overview availability and utilization against
the deterministic `generate_telemetry(seed=42, count=288)` event totals,
equipment ID `QC-001`, incident IDs `inc-000001` and `inc-000002`, replay length
288, and quality counts with zero quarantined rows. This keeps the expected
availability and active-interval totals tied to the simulator fixture rather
than duplicating an unexplained decimal literal.

- [ ] **Step 2: Run the focused test to verify the RED signal**

Run: `pytest tests/e2e/test_pipeline_reconciliation.py -q`

Expected: the test is collected and exposes any missing assertion, helper import, or deterministic-count mismatch. If PostgreSQL is unavailable, report the existing required command `docker compose up -d --wait postgres` and do not disguise the environment failure.

- [ ] **Step 3: Implement the minimal test helpers and assertions**

Use small local helpers such as `_read_json(path: Path) -> object` and `_assert_manifest_hashes(manifest_path: Path) -> dict[str, object]`. Reuse the existing integration helper logic instead of modifying production modules. Keep failure messages naming the layer, dataset, or KPI whose expected value differs.

- [ ] **Step 4: Verify the Python reconciliation test**

Run: `pytest tests/e2e/test_pipeline_reconciliation.py -q`

Expected: PASS with one deterministic source-to-export reconciliation test and no generated files outside pytest’s temporary directory.

- [ ] **Step 5: Commit the Python slice**

```powershell
git add tests/e2e/test_pipeline_reconciliation.py
git commit -m "test: reconcile pipeline through public export"
```

### Task 2: Add the browser reconciliation bridge

**Files:**
- Create: `web/e2e/reconciliation.spec.tsx`
- Modify: `tests/e2e/test_pipeline_reconciliation.py`
- Test: `web/e2e/reconciliation.spec.tsx`

**Interfaces:**
- Consumes `process.env.PORTFLOW_RECONCILIATION_DIR` and the exported `manifest.json` paths from Task 1.
- Produces a Vitest suite that calls `loadSnapshot(fetcher, baseUrl)` and renders the real `App` with the resulting `SnapshotV1`.

- [ ] **Step 1: Write the failing browser contract test**

Create a fetcher that maps requests under `data/` to files below `PORTFLOW_RECONCILIATION_DIR`, returns `Response` objects with status 200/404, and reads the manifest’s relative dataset paths rather than hard-coding public data.

Render the real `App` with `loadData={() => loadSnapshot(fetcher, "http://reconciliation/")}`. Derive the expected formatted availability and throughput from the loaded `SnapshotV1`, then assert the app reaches each hash route and displays those values, plus Equipment `QC-001`, Incidents `inc-000001`, Live Demo’s replay activity, and Data Health’s layer/rejection evidence.

Fail clearly when `PORTFLOW_RECONCILIATION_DIR` is absent or `manifest.json` is missing; do not silently substitute a checked-in fixture.

- [ ] **Step 2: Run the dedicated browser test to verify the RED signal**

Run from `web`: `$env:PORTFLOW_RECONCILIATION_DIR='<temporary export>'; npm test -- --run e2e/reconciliation.spec.tsx --pool=forks --maxWorkers=1`

Expected: the suite identifies the missing temporary export or any display/loader mismatch before the Python bridge is connected.

- [ ] **Step 3: Connect pytest to the browser suite**

After Python finishes export assertions, invoke Vitest with `subprocess.run` from the repository’s `web` directory, pass `PORTFLOW_RECONCILIATION_DIR=output_dir`, and use `--run e2e/reconciliation.spec.tsx --pool=forks --maxWorkers=1`. Assert return code zero and include stdout/stderr in the failure message. Keep the subprocess inside the pytest test so `tmp_path` remains alive.

- [ ] **Step 4: Verify the cross-language test**

Run: `pytest tests/e2e/test_pipeline_reconciliation.py -q`

Expected: the Python test passes its pipeline assertions and the invoked browser suite passes against the same temporary export.

- [ ] **Step 5: Commit the browser slice**

```powershell
git add tests/e2e/test_pipeline_reconciliation.py web/e2e/reconciliation.spec.tsx
git commit -m "test: reconcile exported snapshot in browser"
```

### Task 3: Make normal test commands deterministic

**Files:**
- Modify: `web/vite.config.ts`
- Test: full Python and frontend suites

**Interfaces:**
- Consumes the environment-dependent `web/e2e/reconciliation.spec.tsx` runner from Task 2.
- Produces a default Vitest configuration that excludes only the dedicated reconciliation suite; Task 1 explicitly invokes it with its temporary export.

- [ ] **Step 1: Add the focused configuration assertion**

Confirm the default frontend command does not require a Python-created temporary directory, while the explicit file command still discovers `e2e/reconciliation.spec.tsx`.

- [ ] **Step 2: Implement the narrow Vitest exclusion**

Add `e2e/reconciliation.spec.tsx` to the Vitest `exclude` list only. Do not exclude route accessibility checks or any `src` tests.

- [ ] **Step 3: Verify both modes**

Run from `web`: `npm test -- --run --pool=forks --maxWorkers=1` and separately run the Python reconciliation test, which invokes the excluded suite explicitly.

Expected: the normal frontend suite passes without environment coupling, and the full PF-024 test still executes through the Python bridge.

- [ ] **Step 4: Commit test-runner support**

```powershell
git add web/vite.config.ts
git commit -m "test: isolate generated snapshot reconciliation runner"
```

### Task 4: Run the complete PF-024 verification gate

**Files:**
- Modify: `docs/product/BACKLOG.md`

- [ ] **Step 1: Run Python tests**

Run: `pytest -q`

Expected: all Python unit, integration, and E2E tests pass. PostgreSQL must be running; if not, stop and report the exact Docker command.

- [ ] **Step 2: Run frontend tests and build checks**

Run from `web`: `npm test -- --run --pool=forks --maxWorkers=1`, `npm run typecheck`, `$env:VITE_BASE_PATH='/PortFlow/'; npm run build`, and `npm run verify:pages`.

- [ ] **Step 3: Run repository hygiene checks**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors and only the intended backlog change remains uncommitted.

- [ ] **Step 4: Advance the backlog**

Update `docs/product/BACKLOG.md` so the current next action is PF-025 and add the PF-024 test commits to Completed checkpoints. Do not mark PF-025 complete.

- [ ] **Step 5: Commit backlog advancement**

```powershell
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog after reconciliation"
```
