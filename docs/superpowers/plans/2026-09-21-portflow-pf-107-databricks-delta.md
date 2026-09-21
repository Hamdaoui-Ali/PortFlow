# PF-107 Databricks Free Edition Delta/PySpark Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a credential-free local CLI and importable Databricks source notebook that proves the PortFlow Parquet-to-Bronze/Silver/Gold Delta contract without contacting Databricks.

**Architecture:** Keep the lab in `labs/portflow_databricks/`. Reuse PF-106's deterministic four-table fixture, schema, and local dbt/DuckDB reference through explicit interfaces. Validate the committed notebook statically, package exact hashes and expected results into ignored `.databricks/pf107/` artifacts, and leave cloud execution as a documented manual handoff.

**Tech Stack:** Python 3.12, pytest, Ruff, mypy, DuckDB/dbt, Polars, PyArrow/Parquet, `jsonschema`, Databricks Python source notebooks, Spark DataFrame APIs, and Delta tables.

**Spec:** `docs/superpowers/specs/2026-09-21-portflow-pf-107-databricks-delta-design.md`

## Global Constraints

- Keep all PF-107 orchestration code in a repository-only `labs/portflow_databricks/` package; do not add it to `src/portflow/` or the production wheel.
- Generate only disposable local artifacts below `.databricks/pf107/`; never copy them into `web/public/data`.
- Use the existing four-table PF-106 deterministic fixture as the input contract.
- The default workflow remains offline and credential-free; it must not inspect Databricks credentials or call a workspace API.
- The notebook uses widgets, DataFrame functions, Delta writes, and fully qualified Unity Catalog names; it must not use RDD APIs, `SparkContext`, Python UDFs, DBFS mounts, Maven coordinates, or unrestricted network access.
- Mark generated manifests with `execution_mode: "offline_handoff"` and `cloud_execution: "not_run"`.
- Failure output is limited to stable reason codes; no raw subprocess output, exception text, absolute paths, credentials, or workspace URLs may enter an artifact.
- Keep public data, default Compose services, streaming, orchestration, observability, benchmark behavior, and the web UI unchanged.

## Review Focus

- Windows and POSIX traversal, links, junctions, and reparse points cannot escape `.databricks/pf107/`; pin with `tests/unit/test_databricks_paths.py::test_artifact_paths_reject_cross_platform_escape` and `::test_artifact_paths_reject_reparse_components`.
- Notebook comments and string literals cannot hide unsupported serverless APIs; pin with `tests/unit/test_databricks_notebook.py::test_notebook_rejects_forbidden_tokens_in_comments`.
- Notebook table names cannot write outside the requested catalog/schema/table-prefix contract; pin with `tests/unit/test_databricks_notebook.py::test_notebook_requires_qualified_delta_table_writes`.
- A tampered notebook, schema, fixture, or result cannot verify successfully; pin each reason in `tests/integration/test_databricks_lab.py::test_tampered_artifact_has_bounded_reason`.
- A hostile exception or engine failure cannot leak paths or secrets through the CLI; pin with `tests/unit/test_databricks_cli.py::test_cli_failure_output_is_bounded` and `::test_cli_contains_engine_failures`.

## File Map

| File | Responsibility |
| --- | --- |
| `labs/portflow_databricks/paths.py` | PF-107 artifact root/path containment and reparse-point checks. |
| `labs/portflow_databricks/notebook.py` | Static notebook contract validation and byte hashing. |
| `labs/portflow_databricks/manifest.py` | Version-1 manifest schema, safe serialization, and hash helpers. |
| `labs/portflow_databricks/runner.py` | Offline fixture/reference orchestration and bundle verification. |
| `labs/portflow_databricks/cli.py` | Bounded `run`/`verify` command line behavior. |
| `labs/portflow_databricks/__main__.py` | `python -m labs.portflow_databricks` entry point. |
| `labs/portflow_databricks/notebooks/portflow_delta_lab.py` | Importable serverless-compatible Databricks Python source notebook. |
| `tests/unit/test_databricks_paths.py` | Cross-platform artifact path tests. |
| `tests/unit/test_databricks_notebook.py` | Notebook contract and forbidden API tests. |
| `tests/unit/test_databricks_manifest.py` | Manifest schema, serialization, and safe-failure tests. |
| `tests/unit/test_databricks_cli.py` | CLI exit codes and bounded output tests. |
| `tests/integration/test_databricks_lab.py` | Local run/verify, repeatability, tamper, and public-data isolation tests. |
| `tests/unit/test_databricks_docs.py` | Runbook, README, changelog, and ignore-contract tests. |
| `docs/runbooks/databricks-free-edition.md` | Local commands and explicit manual workspace handoff. |
| `.gitignore`, `README.md`, `CHANGELOG.md`, `docs/product/BACKLOG.md` | Repository boundaries, navigation, release note, and PF-107 closure. |

---

## Task 1: Add Safe PF-107 Paths and Notebook Contract Validator

**Files:**
- Create: `labs/portflow_databricks/__init__.py`
- Create: `labs/portflow_databricks/paths.py`
- Create: `labs/portflow_databricks/notebook.py`
- Create: `tests/unit/test_databricks_paths.py`
- Create: `tests/unit/test_databricks_notebook.py`

**Interfaces:**
- Produces `DEFAULT_ARTIFACT_ROOT`, `ArtifactPathError`, `resolve_artifact_root(candidate, repository_root=...)`, and `resolve_artifact_path(root, relative_path)`.
- Produces `NotebookValidationError(reason_code)`, `validate_notebook_source(source)`, `validate_notebook_file(path)`, and `notebook_sha256(source)`.

- [ ] **Step 1: Write failing path tests.**

```python
def test_artifact_paths_reject_cross_platform_escape(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)
    for value in ("../escape.json", r"..\escape.json", "/tmp/escape.json", r"C:\tmp\escape.json"):
        with pytest.raises(ArtifactPathError, match="artifact path"):
            resolve_artifact_path(root, value)

def test_artifact_paths_reject_reparse_components(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)
    target = tmp_path / "outside"
    target.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")
    with pytest.raises(ArtifactPathError, match="reparse"):
        resolve_artifact_path(root, "linked/result.json")
```

- [ ] **Step 2: Run path tests and verify the expected red failure.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_paths.py`

Expected: FAIL because the PF-107 path module does not exist.

- [ ] **Step 3: Implement the minimal cross-platform path guard.**

Use `PureWindowsPath` and `PurePosixPath` to reject absolute paths, drives,
backslashes, `.`/`..` components, and traversal on either host. Inspect every
existing component with `lstat()` before resolving it, treating symlinks,
junctions, and Windows reparse attributes as unsafe. Resolve only after those
checks and require `candidate.relative_to(root)`.

- [ ] **Step 4: Run path tests and verify green.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_paths.py`

Expected: all path tests pass.

- [ ] **Step 5: Write failing notebook validator tests.**

```python
SAFE_NOTEBOOK = """# Databricks notebook source
# COMMAND ----------
dbutils.widgets.text("input_root", "/Volumes/demo/default/portflow")
input_root = dbutils.widgets.get("input_root")
bronze = spark.read.parquet(f"{input_root}/telemetry_events")
bronze.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_bronze_telemetry_events")
# COMMAND ----------
silver = bronze.select("event_id", "terminal_id", "event_timestamp")
silver.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_silver_telemetry_events")
# COMMAND ----------
gold.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_gold_overview_kpis")
# COMMAND ----------
"""

def test_notebook_contract_accepts_serverless_shape() -> None:
    validate_notebook_source(SAFE_NOTEBOOK)

@pytest.mark.parametrize("forbidden", ["spark.sparkContext", "frame.rdd", "dbutils.fs", "udf(", "dbfs:/"])
def test_notebook_rejects_forbidden_tokens_in_comments(forbidden: str) -> None:
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n# {forbidden}\n")

def test_notebook_requires_qualified_delta_table_writes() -> None:
    with pytest.raises(NotebookValidationError, match="table_contract"):
        validate_notebook_source(SAFE_NOTEBOOK.replace('f"{catalog}.{schema}.{prefix}_', '"unqualified_'))
```

- [ ] **Step 6: Run notebook tests and verify the expected red failure.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_notebook.py`

Expected: FAIL because the validator does not exist.

- [ ] **Step 7: Implement the static validator and byte hash.**

Require the Databricks source marker, at least five command separators, widget
access, Parquet reads, Delta formatting, `saveAsTable`, fully qualified
`catalog.schema.prefix` expressions, and the Gold table suffix. Scan the full
source text—including comments and string literals—for RDD, SparkContext,
UDF, DBFS, Maven, network, wildcard projection, and unrendered-template
patterns. Raise only bounded reason codes `notebook_contract_invalid`,
`unsupported_api`, or `table_contract`.

- [ ] **Step 8: Run notebook tests and verify green.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_notebook.py`

Expected: all notebook contract tests pass.

- [ ] **Step 9: Commit the safe-boundary slice.**

```powershell
git add labs/portflow_databricks tests/unit/test_databricks_paths.py tests/unit/test_databricks_notebook.py
git commit -m "feat: add PF-107 artifact and notebook guards"
```

---

## Task 2: Add the Databricks Source Notebook and Schema Contract

**Files:**
- Create: `labs/portflow_databricks/notebooks/portflow_delta_lab.py`
- Create: `tests/unit/test_databricks_notebook.py` (extend)

**Interfaces:**
- Consumes `validate_notebook_source` from Task 1.
- Produces the committed notebook text consumed by `runner.run_bundle`.

- [ ] **Step 1: Add failing assertions for the complete notebook contract.**

```python
def test_committed_notebook_has_bronze_silver_gold_cells() -> None:
    source = (ROOT / "labs/portflow_databricks/notebooks/portflow_delta_lab.py").read_text(
        encoding="utf-8"
    )
    validate_notebook_source(source)
    for token in (
        "bronze_telemetry_events",
        "silver_telemetry_events",
        "gold_overview_kpis",
        "available_intervals",
        "average_dwell_minutes",
        "mttr_minutes",
        "mtbf_hours",
        "# MAGIC SELECT * FROM",
    ):
        assert token in source

def test_notebook_uses_widgets_for_workspace_inputs() -> None:
    source = (ROOT / "labs/portflow_databricks/notebooks/portflow_delta_lab.py").read_text(
        encoding="utf-8"
    )
    for widget in ("input_root", "catalog", "schema", "table_prefix"):
        assert f'dbutils.widgets.text("{widget}"' in source
        assert f'dbutils.widgets.get("{widget}")' in source
```

- [ ] **Step 2: Run the new notebook tests and verify the expected red failure.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_notebook.py`

Expected: FAIL because the source notebook is not present.

- [ ] **Step 3: Implement the importable Databricks source notebook.**

Create six `# COMMAND ----------` sections. Use widgets with safe demo defaults;
read four Parquet directories below `input_root`; write each Bronze and Silver
DataFrame with `format("delta").mode("overwrite").saveAsTable(...)`; compute
the same `overview_kpis` fields with `pyspark.sql.functions`; write the Gold
table with a fully qualified name; and add a `# MAGIC %sql` inspection cell.
Use `count(when(...))`, `unix_timestamp` differences, `coalesce`, `when`, and
explicit column lists so the notebook does not require RDDs or Python UDFs.

- [ ] **Step 4: Run the notebook tests and verify green.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_notebook.py`

Expected: all notebook tests pass.

- [ ] **Step 5: Commit the notebook slice.**

```powershell
git add labs/portflow_databricks/notebooks/portflow_delta_lab.py tests/unit/test_databricks_notebook.py
git commit -m "feat: add serverless Databricks Delta notebook"
```

---

## Task 3: Add Manifest Contracts and Offline Run/Verify Orchestration

**Files:**
- Create: `labs/portflow_databricks/manifest.py`
- Create: `labs/portflow_databricks/runner.py`
- Create: `tests/unit/test_databricks_manifest.py`
- Create: `tests/integration/test_databricks_lab.py`

**Interfaces:**
- Consumes `RunSpec` from `runner.py`, the Task 2 notebook, and PF-106
  `FixtureSpec`, `generate_fixture`, `logical_fixture_hash`, `run_local_reference`,
  `ReferenceResult`, and canonical result helpers.
- Produces `build_manifest`, `build_error_manifest`, `write_manifest`,
  `validate_manifest`, `run_bundle(spec: RunSpec)`, and
  `verify_bundle(manifest_path, repository_root=...)`.

- [ ] **Step 1: Write failing manifest tests.**

```python
def test_success_manifest_has_offline_pf107_contract(tmp_path: Path) -> None:
    manifest = build_manifest(
        notebook_sha256="a" * 64,
        schema_sha256="b" * 64,
        fixture_rows={"alarms": 2, "container_movements": 5, "incidents": 2, "telemetry_events": 4},
        fixture_sha256="c" * 64,
        expected_rows=1,
        expected_sha256="d" * 64,
        result_sha256="e" * 64,
    )
    assert manifest["task"] == "PF-107"
    assert manifest["execution_mode"] == "offline_handoff"
    assert manifest["cloud_execution"] == "not_run"
    assert manifest["compute"] == "serverless"

def test_error_manifest_allows_only_safe_reason_codes() -> None:
    manifest = build_error_manifest("notebook_hash_mismatch")
    assert manifest["verification"] == {
        "status": "error",
        "reason_code": "notebook_hash_mismatch",
        "verifier_version": "1",
    }
```

- [ ] **Step 2: Run manifest tests and verify the expected red failure.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_manifest.py`

Expected: FAIL because PF-107 manifest functions do not exist.

- [ ] **Step 3: Implement the version-1 manifest and safe serialization.**

Use `jsonschema` with `additionalProperties: false`. Validate the exact fields
from the PF-107 spec, SHA-256 patterns, relative artifact names, four fixture
tables, and bounded reason-code enums. Reuse the PF-106 timestamp decoding
approach for `expected-result.json`; do not place raw rows in the manifest.

- [ ] **Step 4: Run manifest tests and verify green.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_manifest.py`

Expected: all manifest tests pass.

- [ ] **Step 5: Write failing offline integration tests.**

```python
def test_run_verify_and_repeat_have_identical_contract_hashes(tmp_path: Path) -> None:
    first = run_bundle(RunSpec(repository_root=ROOT, output_root=tmp_path / "first"))
    second = run_bundle(RunSpec(repository_root=ROOT, output_root=tmp_path / "second"))
    assert first["cloud_execution"] == "not_run"
    assert first["notebook"] == second["notebook"]
    assert first["schema"] == second["schema"]
    assert first["fixture"] == second["fixture"]
    assert first["expected_result"] == second["expected_result"]
    verify_bundle(tmp_path / "first" / "manifest.json", repository_root=ROOT)

@pytest.mark.parametrize("relative_path,reason", [
    ("portflow_delta_lab.py", "notebook_hash_mismatch"),
    ("schema.json", "schema_hash_mismatch"),
    ("expected-result.json", "result_hash_mismatch"),
])
def test_tampered_artifact_has_bounded_reason(tmp_path: Path, relative_path: str, reason: str) -> None:
    output = tmp_path / "bundle"
    run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    target = output / relative_path
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match=reason):
        verify_bundle(output / "manifest.json", repository_root=ROOT)
```

- [ ] **Step 6: Run integration tests and verify the expected red failure.**

Run: `$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH; & C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/integration/test_databricks_lab.py`

Expected: FAIL because `run_bundle` and `verify_bundle` are not implemented.

- [ ] **Step 7: Implement offline orchestration.**

Define `RunSpec(repository_root: Path, output_root: Path, seed: int = 42)`.
Generate the PF-106 fixture using the checked-in schema, copy the notebook and
schema into the bundle, run the existing disposable dbt/DuckDB reference,
serialize expected rows and fingerprint JSON, build the manifest, and verify
the bundle before returning. On known local failures, write a bounded error
manifest and re-raise a typed error. `verify_bundle` must hash every declared
file, validate the notebook, recompute the fixture logical hash, and decode and
re-hash the expected result without invoking dbt or a cloud client.

- [ ] **Step 8: Run integration tests and verify green.**

Run: `$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH; & C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/integration/test_databricks_lab.py`

Expected: all local run/verify and tamper tests pass.

- [ ] **Step 9: Commit the artifact contract slice.**

```powershell
git add labs/portflow_databricks/manifest.py labs/portflow_databricks/runner.py tests/unit/test_databricks_manifest.py tests/integration/test_databricks_lab.py
git commit -m "feat: add PF-107 offline handoff manifest"
```

---

## Task 4: Add the Bounded CLI and Documentation Contract

**Files:**
- Create: `labs/portflow_databricks/cli.py`
- Create: `labs/portflow_databricks/__main__.py`
- Create: `tests/unit/test_databricks_cli.py`
- Create: `tests/unit/test_databricks_docs.py`
- Create: `docs/runbooks/databricks-free-edition.md`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes `RunSpec`, `run_bundle`, `verify_bundle`, and `ManifestVerificationError` from Task 3.
- Produces `main(argv: Sequence[str] | None = None) -> int` and the user-facing
  local/manual workflow.

- [ ] **Step 1: Write failing CLI and documentation tests.**

```python
def test_cli_run_and_verify_print_bounded_success(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(ROOT)
    output = tmp_path / ".databricks" / "pf107"
    assert main(["run", "--output", str(output)]) == 0
    assert capsys.readouterr().out == "databricks handoff bundle verified\n"
    assert main(["verify", "--manifest", str(output / "manifest.json")]) == 0
    assert capsys.readouterr().out == "databricks handoff bundle verified\n"

def test_cli_failure_output_is_bounded(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "notebook_hash_mismatch"
    monkeypatch.setattr("labs.portflow_databricks.cli.verify_bundle", lambda *args, **kwargs: (_ for _ in ()).throw(Failure("C:\\Users\\alice\\secret")))
    assert main(["verify", "--manifest", ".databricks/pf107/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert output == "databricks verification failed: notebook_hash_mismatch\n"
    assert "alice" not in output
    assert "secret" not in output
```

Add documentation assertions for the two CLI commands, `cloud_execution`,
serverless, Unity Catalog volumes, no credentials, cleanup, and the PF-107
runbook links in `README.md` and `CHANGELOG.md`.

- [ ] **Step 2: Run CLI/docs tests and verify the expected red failure.**

Run: `& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py`

Expected: FAIL because the CLI, runbook, and navigation links do not exist.

- [ ] **Step 3: Implement the bounded CLI entry point.**

Add `run --output --seed` and `verify --manifest` subcommands. Catch only
expected `OSError`, `ValueError`, `json.JSONDecodeError`, `duckdb.Error`, and
`polars.exceptions.PolarsError` at the command boundary. Map exception reason
codes through an immutable allowlist and print exactly one stable line per
failure. Return `0` only after `run_bundle`/`verify_bundle` succeeds, `1` for
bounded workflow failures, and `2` for invalid command-line arguments.

- [ ] **Step 4: Implement the runbook and repository navigation.**

Document local setup using the repository venv, the exact `run`/`verify`
commands, the generated artifact layout, repeatability checks, the manual
notebook import, Unity Catalog volume upload, Serverless compute selection,
expected-result comparison, Free Edition quota/non-commercial/SLA boundary,
and cleanup. Add `.databricks/` to `.gitignore`, add one README runbook link,
add a PF-107 changelog entry, and do not touch public-data files.

- [ ] **Step 5: Run CLI/docs tests and verify green.**

Run: `$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH; & C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py`

Expected: all CLI and documentation tests pass.

- [ ] **Step 6: Commit the CLI/docs slice.**

```powershell
git add labs/portflow_databricks/cli.py labs/portflow_databricks/__main__.py tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py docs/runbooks/databricks-free-edition.md .gitignore README.md CHANGELOG.md
git commit -m "feat: document PF-107 Databricks handoff"
```

---

## Task 5: Close PF-107 and Run the Full Verification Gate

**Files:**
- Modify: `docs/product/BACKLOG.md`
- Create or update: `docs/superpowers/sdd/` ledger artifacts for this plan

- [ ] **Step 1: Run the focused PF-107 suite.**

Run: `$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH; & C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q tests/unit/test_databricks_paths.py tests/unit/test_databricks_notebook.py tests/unit/test_databricks_manifest.py tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py tests/integration/test_databricks_lab.py`

Expected: all PF-107 tests pass with no skipped PF-107 cases.

- [ ] **Step 2: Run the generated CLI twice and compare exact hashes.**

Run:

```powershell
$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH
& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m labs.portflow_databricks run
& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m labs.portflow_databricks verify --manifest .databricks/pf107/manifest.json
```

Expected: both commands print `databricks handoff bundle verified`; the manifest
contains `execution_mode: offline_handoff` and `cloud_execution: not_run`.

- [ ] **Step 3: Update the backlog only after evidence is green.**

Mark PF-107 complete with the design, plan, implementation range, focused-test
count, full-suite count, and the next action PF-108. State explicitly that no
Databricks workspace execution or credential lookup was performed.

- [ ] **Step 4: Run the repository quality gates.**

Run:

```powershell
$env:PATH = 'C:\Users\aliha\PortFlow\.venv\Scripts;' + $env:PATH
& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m ruff check labs/portflow_databricks tests/unit/test_databricks_paths.py tests/unit/test_databricks_notebook.py tests/unit/test_databricks_manifest.py tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py tests/integration/test_databricks_lab.py
& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m mypy labs/portflow_databricks
& C:\Users\aliha\PortFlow\.venv\Scripts\python.exe -m pytest -q
```

Expected: Ruff clean, mypy clean, and the full suite passes with the known
environment setup (`dbt` on `PATH` and `web/node_modules` installed).

- [ ] **Step 5: Verify generated/public boundaries and clean ignored output.**

Run `git diff -- web/public/data`, verify `.databricks/` is ignored, inspect
the manifest for `not_run`, and run `git status --short`. Remove only the
PF-107 disposable `.databricks/` directory after collecting verification
evidence; leave every unrelated user file and worktree untouched.

- [ ] **Step 6: Commit the backlog closure.**

```powershell
git add docs/product/BACKLOG.md
git commit -m "docs: close PF-107 Databricks lab"
```

## Final Handoff

After the final review and verification, push `codex/pf-107-databricks-lab`,
create a PR against `main`, wait for CI/Sonar checks, fix any reported issue
on the same branch with a focused commit and rerun the gates, then merge the PR
using the current head SHA. Confirm the merge by refetching `origin/main` and
report the PR URL, merge commit, tests, and the fact that Databricks cloud
execution remained `not_run`.
