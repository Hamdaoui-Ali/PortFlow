# PF-106 Offline BigQuery Portability Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic GoogleSQL portability lab for the existing `overview_kpis` contract, with local validation and dry-run-ready artifacts but no cloud execution.

**Architecture:** Keep production analytics unchanged. Add a repository-only `labs.portflow_bigquery` package that generates a small Silver-shaped Parquet fixture, renders and parses a committed BigQuery SQL contract, runs the existing local dbt/DuckDB Gold reference, canonicalizes the expected result, and writes a verified manifest under ignored `.portability/bigquery/`.

**Tech Stack:** Python 3.12, argparse, Polars, PyArrow, DuckDB, dbt-duckdb, `sqlglot` BigQuery parsing, `jsonschema`, pytest, Ruff, mypy, and SHA-256 hashing.

**Spec:** `docs/superpowers/specs/2026-09-20-portflow-pf-106-bigquery-portability-design.md`

## Global Constraints

- The verifier is always offline: no BigQuery API, `bq` process, Google Cloud SDK, credential lookup, account, project, dataset, upload, or network access.
- Keep the production `analytics/models/` dbt project and existing Gold SQL unchanged.
- Keep portability code in `labs/portflow_bigquery/`; do not add it to `src/portflow/` or the PortFlow wheel.
- Generate artifacts only below the repository root's `.portability/bigquery/`, and reject paths outside that directory.
- Preserve the explicit `overview_kpis` output fields, UTC timestamps, stable ordering, six-decimal numeric canonicalization, and null handling.
- The committed GoogleSQL query must use explicit columns and BigQuery equivalents such as `COUNTIF`, `TIMESTAMP_DIFF`, and `SAFE_DIVIDE`; it must not contain `read_parquet`, `FILTER (...)`, `date_diff(...)`, unrendered template tokens, or implicit `SELECT *`.
- Record `cloud_execution: "not_run"` in every successful manifest.
- Do not modify `web/public/data`, the normal `data/` tree, Docker Compose state, streaming behavior, orchestration, observability, or any UI surface.
- Generated fixtures, query copies, result files, schema copies, and manifests are ignored and never committed.
- Failure output uses bounded reason codes and must not expose raw subprocess output, absolute paths, credentials, or full environment dumps.
- The compatibility fixture preserves the current model's single-terminal incident association; PF-106 does not correct business logic.

## Review Focus

- Output path traversal, an absolute custom path, or a valid-looking `.portability/bigquery` path outside the repository must fail closed; Task 1 pins this with path-containment tests.
- Repeated fixture generation and Parquet file ordering must produce the same logical hash; Task 2 pins this with repeat-run and reordered-file tests.
- Invalid identifiers, unrendered template tokens, invalid GoogleSQL, and DuckDB-only syntax must fail with stable reason codes; Task 3 pins each case.
- A failed dbt subprocess must return `dbt_reference_failed` without copying stdout/stderr into the manifest; Task 5 pins this with a mocked subprocess failure.
- Tampering with any query, schema, fixture, or expected-result artifact must fail verification with the matching hash reason; Task 6 pins each artifact class.

---

### Task 1: Create the repository-only package and safe artifact paths

**Files:**
- Create: `labs/__init__.py`
- Create: `labs/portflow_bigquery/__init__.py`
- Create: `labs/portflow_bigquery/paths.py`
- Test: `tests/unit/test_bigquery_portability_paths.py`

**Interfaces:**
- Produces `ArtifactPathError(ValueError)` for invalid output paths.
- Produces `DEFAULT_ARTIFACT_ROOT = Path(".portability/bigquery")`.
- Produces `resolve_artifact_root(candidate: Path | None = None, *, repository_root: Path | None = None) -> Path`.
- Produces `resolve_artifact_path(root: Path, relative_path: str) -> Path`.

- [ ] **Step 1: Write the failing path tests**

```python
from pathlib import Path

import pytest

from labs.portflow_bigquery.paths import (
    ArtifactPathError,
    resolve_artifact_path,
    resolve_artifact_root,
)


def test_default_root_is_below_repository_portability_directory(tmp_path: Path) -> None:
    assert resolve_artifact_root(repository_root=tmp_path) == (
        tmp_path / ".portability" / "bigquery"
    ).resolve()


def test_explicit_root_must_remain_below_repository_portability_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(ArtifactPathError, match="artifact root"):
        resolve_artifact_root(tmp_path / "outside", repository_root=tmp_path)


def test_explicit_named_root_outside_repository_is_rejected(tmp_path: Path) -> None:
    outside_repository = tmp_path.parent / "other-repository" / ".portability" / "bigquery"

    with pytest.raises(ArtifactPathError, match="artifact root"):
        resolve_artifact_root(outside_repository, repository_root=tmp_path)


def test_linked_artifact_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    artifact_root = tmp_path / ".portability" / "bigquery"
    artifact_root.parent.mkdir()
    try:
        artifact_root.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ArtifactPathError, match="artifact root"):
        resolve_artifact_root(repository_root=tmp_path)


@pytest.mark.parametrize("relative_path", ["../escape.json", "..\\escape.json", "/tmp/escape.json"])
def test_child_path_rejects_traversal_and_absolute_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)

    with pytest.raises(ArtifactPathError, match="artifact path"):
        resolve_artifact_path(root, relative_path)


def test_child_path_resolves_inside_root(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)

    assert resolve_artifact_path(root, "manifest.json") == (root / "manifest.json").resolve()
```

- [ ] **Step 2: Run the path tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_paths.py -q
```

Expected: FAIL because `labs.portflow_bigquery.paths` and its path functions do not exist yet.

- [ ] **Step 3: Implement the path boundary**

```python
DEFAULT_ARTIFACT_ROOT = Path(".portability") / "bigquery"


class ArtifactPathError(ValueError):
    """Raised when a portability artifact path escapes the allowed root."""


def resolve_artifact_root(
    candidate: Path | None = None,
    *,
    repository_root: Path | None = None,
) -> Path:
    base = (repository_root or Path.cwd()).resolve()
    allowed = (base / ".portability" / "bigquery").resolve()
    requested = (allowed if candidate is None else candidate).resolve()
    try:
        requested.relative_to(allowed)
    except ValueError as error:
        raise ArtifactPathError("artifact root must remain below .portability/bigquery") from error
    return requested


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ArtifactPathError("artifact path must remain below artifact root") from error
    return candidate
```

The boundary must also reject existing symbolic-link, junction, or other
reparse-point components before resolving or mutating them. A link inside the
repository that redirects `.portability/bigquery` or a child path outside the
repository must raise `ArtifactPathError`; do not rely only on
`Path.resolve()` because resolving both the allowed root and the requested
candidate can make an external junction appear to be the allowed root. Add a
focused child-link regression test and keep the checks platform-portable; a
test may skip only when the host cannot create directory links.

Export `ArtifactPathError`, `DEFAULT_ARTIFACT_ROOT`, `resolve_artifact_root`, and
`resolve_artifact_path` from `labs/portflow_bigquery/__init__.py`. Keep both
package `__init__.py` files free of runtime side effects.

- [ ] **Step 4: Run the focused tests and lint the new package**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_paths.py -q
python -m ruff check labs/portflow_bigquery tests/unit/test_bigquery_portability_paths.py
python -m mypy labs/portflow_bigquery/paths.py
```

Expected: all path tests pass, Ruff reports no violations, and mypy reports no errors.

- [ ] **Step 5: Commit the package boundary**

```text
git add labs tests/unit/test_bigquery_portability_paths.py
git commit -m "feat: add BigQuery portability artifact boundary"
```

### Task 2: Add the BigQuery schema mapping and deterministic multi-table fixture

**Files:**
- Create: `analytics/portability/bigquery/schema.json`
- Create: `labs/portflow_bigquery/schema.py`
- Create: `labs/portflow_bigquery/fixture.py`
- Test: `tests/unit/test_bigquery_portability_schema.py`
- Test: `tests/unit/test_bigquery_portability_fixture.py`

**Interfaces:**
- Produces `SchemaField(name: str, bigquery_type: str, mode: str)`.
- Produces `FixtureSpec(seed: int = 42)`.
- Produces `FixtureMetadata(seed: int, generator_version: str, rows_by_table: dict[str, int], logical_sha256: str, schema_sha256: str, schema: dict[str, tuple[str, ...]])` with `as_json() -> dict[str, object]`.
- Produces `load_schema(path: Path) -> dict[str, tuple[SchemaField, ...]]`.
- Produces `generate_fixture(spec: FixtureSpec, output_root: Path, *, schema_path: Path, repository_root: Path | None = None) -> FixtureMetadata`.
- Produces `logical_fixture_hash(output_root: Path, schema: dict[str, tuple[SchemaField, ...]]) -> str`.

- [ ] **Step 1: Write schema and fixture contract tests**

```python
from pathlib import Path

import polars as pl
import pytest

from labs.portflow_bigquery.fixture import FixtureSpec, generate_fixture, logical_fixture_hash
from labs.portflow_bigquery.schema import load_schema

ROOT = Path(__file__).parents[2]
SCHEMA_PATH = ROOT / "analytics" / "portability" / "bigquery" / "schema.json"


def test_schema_declares_all_four_logical_tables() -> None:
    schema = load_schema(SCHEMA_PATH)

    assert set(schema) == {
        "telemetry_events",
        "container_movements",
        "incidents",
        "alarms",
    }
    assert {field.name for field in schema["telemetry_events"]} >= {
        "event_id",
        "terminal_id",
        "event_timestamp",
        "state",
        "available",
    }


def test_schema_loader_rejects_unknown_type(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(
        '{"schema_version": 1, "tables": {"alarms": [{"name": "alarm_id", "type": "BYTES", "mode": "REQUIRED"}]}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)


def test_schema_loader_rejects_boolean_schema_version(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(
        '{"schema_version": true, "tables": {}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)


def test_fixture_covers_kpi_edge_cases(tmp_path: Path) -> None:
    schema = load_schema(SCHEMA_PATH)
    fixture_root = tmp_path / ".portability" / "bigquery" / "fixture"
    metadata = generate_fixture(
        FixtureSpec(seed=42),
        fixture_root,
        schema_path=SCHEMA_PATH,
        repository_root=tmp_path,
    )

    assert metadata.rows_by_table == {
        "telemetry_events": 4,
        "container_movements": 5,
        "incidents": 2,
        "alarms": 2,
    }
    assert pl.read_parquet(fixture_root / "telemetry_events" / "part-000000.parquet").select(
        "state", "available"
    ).to_dicts() == [
        {"state": "ACTIVE", "available": True},
        {"state": "IDLE", "available": True},
        {"state": "UNAVAILABLE", "available": False},
        {"state": "ACTIVE", "available": True},
    ]
    assert schema["incidents"]


def test_fixture_hash_is_repeatable_and_independent_of_file_names(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_fixture = first / ".portability" / "bigquery" / "fixture"
    second_fixture = second / ".portability" / "bigquery" / "fixture"
    schema = load_schema(SCHEMA_PATH)

    first_metadata = generate_fixture(
        FixtureSpec(seed=42), first_fixture, schema_path=SCHEMA_PATH, repository_root=first
    )
    second_metadata = generate_fixture(
        FixtureSpec(seed=42), second_fixture, schema_path=SCHEMA_PATH, repository_root=second
    )

    assert first_metadata.logical_sha256 == second_metadata.logical_sha256

    telemetry_root = first_fixture / "telemetry_events"
    telemetry = pl.read_parquet(telemetry_root / "part-000000.parquet")
    telemetry.tail(2).write_parquet(telemetry_root / "part-000000.parquet")
    telemetry.head(2).write_parquet(telemetry_root / "part-000001.parquet")
    assert logical_fixture_hash(first_fixture, schema) == second_metadata.logical_sha256
    assert logical_fixture_hash(first_fixture, schema) == logical_fixture_hash(second_fixture, schema)


def test_fixture_writer_rejects_output_outside_artifact_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact root"):
        generate_fixture(
            FixtureSpec(seed=42),
            tmp_path / "outside" / "fixture",
            schema_path=SCHEMA_PATH,
            repository_root=tmp_path,
        )


def test_fixture_writer_rejects_linked_table_root(tmp_path: Path) -> None:
    fixture_root = tmp_path / ".portability" / "bigquery" / "fixture"
    fixture_root.mkdir(parents=True)
    outside = tmp_path / "outside-table"
    outside.mkdir()
    try:
        (fixture_root / "telemetry_events").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ValueError, match="artifact path"):
        generate_fixture(
            FixtureSpec(seed=42),
            fixture_root,
            schema_path=SCHEMA_PATH,
            repository_root=tmp_path,
        )
    assert not list(outside.iterdir())
```

- [ ] **Step 2: Run the schema and fixture tests to confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py -q
```

Expected: FAIL because the source schema, loader, and fixture generator do not exist yet.

- [ ] **Step 3: Add the explicit BigQuery schema mapping**

Create `schema.json` with four tables and the full Silver columns consumed by the
existing staging models. Use only these BigQuery types: `STRING`, `INT64`, `BOOL`,
`FLOAT64`, and `TIMESTAMP`. Include `mode` as `REQUIRED` for identifiers and
contract keys and `NULLABLE` for optional timestamps, numeric measurements, and
metadata. The four table names and their required analytic columns must be:

```json
{
  "schema_version": 1,
  "tables": {
    "telemetry_events": ["event_id", "schema_version", "equipment_id", "terminal_id", "event_timestamp", "ingestion_timestamp", "state", "available", "load_percent", "temperature_c", "created_at", "updated_at", "source_table", "extraction_run_id", "source_updated_at", "extracted_at"],
    "container_movements": ["movement_id", "terminal_id", "equipment_id", "movement_type", "container_ref", "event_timestamp", "created_at", "updated_at", "source_table", "extraction_run_id", "source_updated_at", "extracted_at"],
    "incidents": ["incident_id", "equipment_id", "severity", "status", "opened_at", "resolved_at", "root_cause", "created_at", "updated_at", "source_table", "extraction_run_id", "source_updated_at", "extracted_at"],
    "alarms": ["alarm_id", "equipment_id", "severity", "code", "opened_at", "cleared_at", "created_at", "updated_at", "source_table", "extraction_run_id", "source_updated_at", "extracted_at"]
  }
}
```

The implementation must retain types and modes in the actual JSON rather than
reducing the committed mapping to names only. `load_schema` must reject missing
tables, duplicate field names, unknown types, and malformed modes with
`ValueError("invalid portability schema")`. Treat `schema_version` as an exact
integer contract: JSON `true`/`false` and other values must not compare equal
to version `1` through host-language coercion.

- [ ] **Step 4: Implement deterministic fixture generation**

Use a fixed UTC start of `2026-01-01T00:00:00Z`. Resolve `output_root.parent`
through `resolve_artifact_root(..., repository_root=repository_root or Path.cwd())`
and then resolve the `fixture` child through `resolve_artifact_path` before
creating or deleting any directory. Before each table directory is created or
cleaned, resolve the table child with `resolve_artifact_path`; likewise resolve
the final Parquet target before writing it. These checks must reject linked
directory/file paths that resolve outside the repository-local artifact root.
Generate exactly one terminal
`TM-001` and deterministic rows that exercise the current KPI rules:

- telemetry at 00:00, 00:05, 00:10, and 00:15 with states `ACTIVE`, `IDLE`,
  `UNAVAILABLE`, and `ACTIVE`; available is `True`, `True`, `False`, `True`;
- movements for one complete container pair (`GATE_IN` at 00:00 and `GATE_OUT`
  at 00:30 plus `LOAD` and `DISCHARGE`) and one incomplete `GATE_IN` at 00:10;
- one resolved critical incident from 00:05 to 00:15 and one open warning
  incident opened at 00:10 with a null `resolved_at`;
- one critical alarm at 00:10 and one non-critical alarm at 00:20;
- deterministic source metadata for every row: `schema_version=1`, source table,
  extraction run `portability-run-000042`, and UTC created/updated/extracted
  timestamps.

Write one `part-000000.parquet` per logical table below the supplied output root.
Use the schema mapping to order columns before writing. Hash rows after sorting by
all declared columns and serializing each table name, column name, and value with
`json.dumps(..., sort_keys=True, separators=(",", ":"), default=str)`, followed by
one newline per row. Do not include absolute paths or Parquet file bytes in the
logical hash.

- [ ] **Step 5: Run the focused fixture tests and type checks**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py -q
python -m ruff check labs/portflow_bigquery/schema.py labs/portflow_bigquery/fixture.py tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py
python -m mypy labs/portflow_bigquery/schema.py labs/portflow_bigquery/fixture.py
```

Expected: all schema and fixture tests pass, Ruff reports no violations, and mypy reports no errors.

- [ ] **Step 6: Commit the fixture contract**

```text
git add analytics/portability labs/portflow_bigquery/schema.py labs/portflow_bigquery/fixture.py tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py
git commit -m "feat: add deterministic BigQuery portability fixture"
```

### Task 3: Add and validate the committed GoogleSQL `overview_kpis` contract

**Files:**
- Modify: `pyproject.toml` (`project.optional-dependencies.dev`)
- Modify: `uv.lock`
- Create: `analytics/portability/bigquery/overview_kpis.sql`
- Create: `labs/portflow_bigquery/query.py`
- Test: `tests/unit/test_bigquery_portability_query.py`

**Interfaces:**
- Produces `QueryValidationError(ValueError)` with a stable `reason_code: str` property.
- Produces `render_query(template: str, *, project_id: str, dataset: str) -> str`.
- Produces `validate_google_sql(sql: str) -> None`.
- Produces `query_sha256(sql: str) -> str`.

- [ ] **Step 1: Add the local parser dependency and write query tests**

Add `sqlglot>=26,<30` to the existing `dev` optional dependency list and run
`uv lock` after the source change. Do not add `sqlglot` to `[project].dependencies`.

Write tests that pin the renderer and validator:

```python
from pathlib import Path

import pytest

from labs.portflow_bigquery.query import QueryValidationError, render_query, validate_google_sql

ROOT = Path(__file__).parents[2]
TEMPLATE = (ROOT / "analytics" / "portability" / "bigquery" / "overview_kpis.sql").read_text(
    encoding="utf-8"
)


def test_rendered_contract_uses_bigquery_functions_and_no_tokens() -> None:
    sql = render_query(TEMPLATE, project_id="demo-project", dataset="portflow")

    assert "`demo-project.portflow.fct_equipment_telemetry`" in sql
    assert "COUNTIF" in sql
    assert "TIMESTAMP_DIFF" in sql
    assert "SAFE_DIVIDE" in sql
    assert "{{" not in sql
    assert "}}" not in sql
    validate_google_sql(sql)


@pytest.mark.parametrize(
    ("project_id", "dataset", "reason_code"),
    [("", "portflow", "invalid_project_id"), ("demo-project", "bad.dataset", "invalid_dataset")],
)
def test_render_rejects_invalid_identifiers(
    project_id: str,
    dataset: str,
    reason_code: str,
) -> None:
    with pytest.raises(QueryValidationError) as error:
        render_query(TEMPLATE, project_id=project_id, dataset=dataset)

    assert error.value.reason_code == reason_code


@pytest.mark.parametrize(
    ("fragment", "reason_code"),
    [("read_parquet('x')", "forbidden_duckdb_construct"), ("date_diff('second', a, b)", "forbidden_duckdb_construct"), ("COUNT(*) FILTER (WHERE ok)", "forbidden_duckdb_construct"), ("SELECT * FROM t", "implicit_select_star")],
)
def test_validator_rejects_nonportable_sql(fragment: str, reason_code: str) -> None:
    with pytest.raises(QueryValidationError) as error:
        validate_google_sql(fragment)

    assert error.value.reason_code == reason_code


def test_validator_reports_invalid_google_sql() -> None:
    with pytest.raises(QueryValidationError) as error:
        validate_google_sql("SELECT FROM")

    assert error.value.reason_code == "invalid_google_sql"
```

- [ ] **Step 2: Run the query tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_query.py -q
```

Expected: FAIL because the SQL contract and query module do not exist yet.

- [ ] **Step 3: Add the GoogleSQL contract**

Create `analytics/portability/bigquery/overview_kpis.sql` from the current
`analytics/models/marts/overview_kpis.sql`, keeping the same CTE and output
semantics but making the target dialect explicit:

- replace dbt `ref(...)` references with these rendered table names:
  `fct_equipment_telemetry`, `fct_movements`, `fct_incidents`, and `stg_alarms`;
- wrap each rendered table name as `` `{{ project_id }}.{{ dataset }}.<table>` ``;
- replace `count(*) filter (where condition)` with `COUNTIF(condition)`;
- replace `avg(expression) filter (where condition)` with
  `AVG(IF(condition, expression, NULL))`;
- replace `date_diff('second', start, end)` with
  `TIMESTAMP_DIFF(end, start, SECOND)`;
- use `SAFE_DIVIDE` for availability, utilization, MTTR, and MTBF zero
  denominators;
- preserve the current single-terminal incident join and all 19 explicit output
  fields in the order documented by the spec;
- use `MIN(IF(...))` and `MAX(IF(...))` for conditional movement timestamps;
- leave no `SELECT *`, local Parquet reader, dbt `ref`, `FILTER`, or `date_diff`
  expression in the committed file.

The query's final projection must be exactly:

```sql
SELECT
  p.terminal_id,
  p.source_period_start,
  p.source_period_end,
  p.available_intervals,
  p.scheduled_intervals,
  p.active_intervals,
  p.available_time_minutes,
  COALESCE(i.resolved_incident_count, 0) AS resolved_incident_count,
  COALESCE(i.repair_minutes, 0) AS repair_minutes,
  COALESCE(i.qualifying_failure_count, 0) AS qualifying_failure_count,
  p.scheduled_intervals * 5.0 / 60.0 AS operating_hours,
  COALESCE(m.throughput, 0) AS throughput,
  m.average_dwell_minutes,
  SAFE_DIVIDE(p.available_intervals, p.scheduled_intervals) AS availability,
  SAFE_DIVIDE(p.active_intervals, p.available_intervals) AS utilization,
  SAFE_DIVIDE(i.repair_minutes, i.resolved_incident_count) AS mttr_minutes,
  SAFE_DIVIDE(
    p.scheduled_intervals * 5.0 / 60.0,
    i.qualifying_failure_count
  ) AS mtbf_hours,
  COALESCE(i.active_incidents, 0) AS active_incidents,
  COALESCE(a.critical_alarms, 0) AS critical_alarms
FROM telemetry_period AS p
LEFT JOIN movement_metrics AS m ON m.terminal_id = p.terminal_id
LEFT JOIN incident_metrics AS i ON i.terminal_id = p.terminal_id
LEFT JOIN alarm_metrics AS a ON a.terminal_id = p.terminal_id
ORDER BY p.terminal_id;
```

- [ ] **Step 4: Implement rendering and offline validation**

Define the validation exception with a bounded reason code:

```python
class QueryValidationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)
```

Use identifier validation before replacement:

```python
_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_DATASET = re.compile(r"^[A-Za-z0-9_]+$")
_TOKENS = ("{{ project_id }}", "{{ dataset }}")


def render_query(template: str, *, project_id: str, dataset: str) -> str:
    if not _PROJECT_ID.fullmatch(project_id):
        raise QueryValidationError("invalid_project_id")
    if not _DATASET.fullmatch(dataset):
        raise QueryValidationError("invalid_dataset")
    return template.replace(_TOKENS[0], project_id).replace(_TOKENS[1], dataset)
```

`validate_google_sql` must first reject unrendered tokens, `read_parquet`,
`date_diff(`, `FILTER (`, and any `SELECT *` with the stable reason codes
`unrendered_template`, `forbidden_duckdb_construct`, and
`implicit_select_star`. Then call `sqlglot.parse_one(sql, read="bigquery")` and
translate `sqlglot.errors.ParseError` into `QueryValidationError("invalid_google_sql")`.
The function must also require the 19 output aliases and raise
`missing_output_field` if any alias is absent. `query_sha256` hashes UTF-8 SQL
bytes with `hashlib.sha256`.

- [ ] **Step 5: Run parser, lint, and type checks**

Run:

```text
uv lock
python -m pytest tests/unit/test_bigquery_portability_query.py -q
python -m ruff check labs/portflow_bigquery/query.py tests/unit/test_bigquery_portability_query.py
python -m mypy labs/portflow_bigquery/query.py
```

Expected: all query tests pass, the lockfile includes the dev-only parser, Ruff reports no violations, and mypy reports no errors.

- [ ] **Step 6: Commit the GoogleSQL contract**

```text
git add pyproject.toml uv.lock analytics/portability/bigquery/overview_kpis.sql labs/portflow_bigquery/query.py tests/unit/test_bigquery_portability_query.py
git commit -m "feat: add offline BigQuery SQL contract"
```

### Task 4: Add canonical result normalization and hashing

**Files:**
- Create: `labs/portflow_bigquery/canonical.py`
- Test: `tests/unit/test_bigquery_portability_canonical.py`

**Interfaces:**
- Produces `RESULT_FIELDS: tuple[str, ...]` containing the 19 `overview_kpis` fields in contract order.
- Produces `canonicalize_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]`.
- Produces `result_sha256(rows: Iterable[Mapping[str, object]]) -> str`.

- [ ] **Step 1: Write canonicalization tests**

```python
from datetime import UTC, datetime

import pytest

from labs.portflow_bigquery.canonical import canonicalize_rows, result_sha256


def _row(terminal_id: str = "TM-001") -> dict[str, object]:
    return {
        "terminal_id": terminal_id,
        "source_period_start": datetime(2026, 1, 1, tzinfo=UTC),
        "source_period_end": datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        "available_intervals": 3,
        "scheduled_intervals": 4,
        "active_intervals": 2,
        "available_time_minutes": 15,
        "resolved_incident_count": 1,
        "repair_minutes": 10.0,
        "qualifying_failure_count": 1,
        "operating_hours": 1 / 3,
        "throughput": 1,
        "average_dwell_minutes": 30.0,
        "availability": 0.75,
        "utilization": 2 / 3,
        "mttr_minutes": 10.0,
        "mtbf_hours": 1 / 3,
        "active_incidents": 1,
        "critical_alarms": 1,
    }


def test_canonicalizer_normalizes_timestamps_and_float_precision() -> None:
    result = canonicalize_rows([_row()])

    assert result[0]["source_period_start"] == "2026-01-01T00:00:00Z"
    assert result[0]["operating_hours"] == 0.333333


def test_canonicalizer_preserves_allowed_null_metrics() -> None:
    row = _row()
    row["average_dwell_minutes"] = None
    row["mttr_minutes"] = None

    assert canonicalize_rows([row])[0]["average_dwell_minutes"] is None


def test_result_hash_is_independent_of_input_order() -> None:
    first = [_row("TM-002"), _row("TM-001")]
    second = list(reversed(first))

    assert result_sha256(first) == result_sha256(second)


def test_canonicalizer_rejects_missing_fields_and_non_finite_numbers() -> None:
    row = _row()
    del row["throughput"]
    with pytest.raises(ValueError, match="missing result fields"):
        canonicalize_rows([row])

    invalid = _row()
    invalid["availability"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        canonicalize_rows([invalid])

    unexpected = _row()
    unexpected["unexpected"] = 1
    with pytest.raises(ValueError, match="unexpected result fields"):
        canonicalize_rows([unexpected])
```

- [ ] **Step 2: Run the canonicalization tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_canonical.py -q
```

Expected: FAIL because the canonicalization module does not exist yet.

- [ ] **Step 3: Implement explicit result normalization**

Use these field groups:

```python
RESULT_FIELDS = (
    "terminal_id", "source_period_start", "source_period_end",
    "available_intervals", "scheduled_intervals", "active_intervals",
    "available_time_minutes", "resolved_incident_count", "repair_minutes",
    "qualifying_failure_count", "operating_hours", "throughput",
    "average_dwell_minutes", "availability", "utilization", "mttr_minutes",
    "mtbf_hours", "active_incidents", "critical_alarms",
)
INTEGER_FIELDS = {
    "available_intervals", "scheduled_intervals", "active_intervals",
    "available_time_minutes", "resolved_incident_count",
    "qualifying_failure_count", "throughput", "active_incidents",
    "critical_alarms",
}
NULLABLE_FIELDS = {
    "average_dwell_minutes", "availability", "utilization", "mttr_minutes", "mtbf_hours",
}
```

Reject missing or extra fields, booleans in integer fields, naive datetimes,
non-finite floats, and nulls outside `NULLABLE_FIELDS`. Convert aware datetimes
to UTC ISO-8601 with a trailing `Z`; round numeric metrics to six decimals;
sort rows by `terminal_id`; serialize with sorted JSON keys and a final newline
before hashing.

- [ ] **Step 4: Run focused checks and commit**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_canonical.py -q
python -m ruff check labs/portflow_bigquery/canonical.py tests/unit/test_bigquery_portability_canonical.py
python -m mypy labs/portflow_bigquery/canonical.py
```

Expected: all tests pass with no Ruff or mypy errors.

```text
git add labs/portflow_bigquery/canonical.py tests/unit/test_bigquery_portability_canonical.py
git commit -m "feat: add BigQuery portability result hashing"
```

### Task 5: Run the existing local dbt/DuckDB reference safely

**Files:**
- Create: `labs/portflow_bigquery/reference.py`
- Test: `tests/unit/test_bigquery_portability_reference.py`

**Interfaces:**
- Produces `ReferenceExecutionError(ValueError)` with a stable `reason_code: str` property.
- Produces `ReferenceResult(rows: tuple[dict[str, object], ...], result_sha256: str)`.
- Produces `run_local_reference(*, repository_root: Path, fixture_root: Path, gold_db: Path) -> ReferenceResult`.

- [ ] **Step 1: Write reference-runner tests**

```python
from pathlib import Path

import pytest

from labs.portflow_bigquery.reference import ReferenceExecutionError, run_local_reference


def test_failed_dbt_reference_has_bounded_reason(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FailedProcess:
        returncode = 1
        stdout = "secret-looking stdout"
        stderr = "secret-looking stderr"

    monkeypatch.setattr("labs.portflow_bigquery.reference.subprocess.run", lambda *args, **kwargs: FailedProcess())
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=tmp_path / "fixture",
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "dbt_reference_failed"
    assert "secret-looking" not in str(error.value)


def test_reference_requires_fixture_directory(tmp_path: Path) -> None:
    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=tmp_path / "missing",
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "fixture_missing"
```

- [ ] **Step 2: Run the reference tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_reference.py -q
```

Expected: FAIL because the reference module and error type do not exist yet.

- [ ] **Step 3: Implement the local reference runner**

Run the existing dbt project exactly as the integration Gold test does:

```python
subprocess.run(
    [
        "dbt", "build",
        "--project-dir", str(repository_root / "analytics"),
        "--profiles-dir", str(repository_root / "analytics"),
    ],
    check=False,
    capture_output=True,
    text=True,
    cwd=repository_root,
    env={**os.environ, "PORTFLOW_SILVER_DIR": fixture_root.as_posix(), "PORTFLOW_GOLD_DB": gold_db.as_posix()},
)
```

Raise `ReferenceExecutionError("dbt_reference_failed")` for a non-zero return
code and never include stdout or stderr in the exception message. Raise
`ReferenceExecutionError("fixture_missing")` before launching dbt when the
fixture root is absent, and `ReferenceExecutionError("gold_output_missing")`
when dbt succeeds without creating the expected DuckDB file. Open the Gold file
read-only and select the 19 `RESULT_FIELDS` from `overview_kpis` ordered by
`terminal_id`; pass those rows to `canonicalize_rows` and `result_sha256`.

- [ ] **Step 4: Run unit tests and a real reference smoke test**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_reference.py -q
python -m pytest tests/integration/test_gold.py::test_dbt_builds_gold_models_and_reconciles_counts -q
python -m ruff check labs/portflow_bigquery/reference.py tests/unit/test_bigquery_portability_reference.py
python -m mypy labs/portflow_bigquery/reference.py
```

Expected: the mocked failure tests pass, the existing Gold integration test passes, and Ruff/mypy report no errors.

- [ ] **Step 5: Commit the reference runner**

```text
git add labs/portflow_bigquery/reference.py tests/unit/test_bigquery_portability_reference.py
git commit -m "feat: add local BigQuery portability reference runner"
```

### Task 6: Add manifest generation, tamper-proof verification, and bundle orchestration

**Files:**
- Create: `labs/portflow_bigquery/manifest.py`
- Create: `labs/portflow_bigquery/runner.py`
- Test: `tests/unit/test_bigquery_portability_manifest.py`
- Test: `tests/integration/test_bigquery_portability.py`

**Interfaces:**
- Produces `ManifestVerificationError(ValueError)` with a stable `reason_code: str` property.
- Produces `build_manifest(*, query_sha256: str, schema_sha256: str, fixture: FixtureMetadata, reference: ReferenceResult, dry_run_command: str) -> dict[str, object]`.
- Produces `build_error_manifest(reason_code: str) -> dict[str, object]`.
- Produces `write_manifest(path: Path, manifest: Mapping[str, object]) -> None`.
- Produces `validate_manifest(path: Path, *, artifact_root: Path) -> dict[str, object]`.
- Produces `file_sha256(path: Path) -> str`, `write_text(path: Path, content: str) -> None`, and `write_json(path: Path, value: object) -> None`.
- Produces `RunSpec(repository_root: Path, output_root: Path, project_id: str = "demo-project", dataset: str = "portflow", seed: int = 42)`.
- Produces `run_bundle(spec: RunSpec) -> dict[str, object]`.
- Produces `verify_bundle(manifest_path: Path, *, repository_root: Path) -> None`.

- [ ] **Step 1: Write manifest schema and tamper tests**

Write tests that build a valid bundle through `run_bundle` and then modify one
artifact at a time:

```python
from pathlib import Path

import json
import pytest

from labs.portflow_bigquery.manifest import ManifestVerificationError
from labs.portflow_bigquery.runner import RunSpec, run_bundle, verify_bundle

ROOT = Path(__file__).parents[2]


def _output_root() -> Path:
    return ROOT / ".portability" / "test-bigquery"


def test_run_bundle_writes_offline_manifest(tmp_path: Path) -> None:
    output = _output_root()
    manifest = run_bundle(RunSpec(repository_root=ROOT, output_root=output))

    assert manifest["task"] == "PF-106"
    assert manifest["cloud_execution"] == "not_run"
    assert manifest["verification"]["status"] == "ok"
    verify_bundle(output / "manifest.json", repository_root=ROOT)


@pytest.mark.parametrize("relative_path", ["overview_kpis.sql", "schema.json"])
def test_verify_rejects_tampered_text_artifacts(tmp_path: Path, relative_path: str) -> None:
    output = _output_root()
    run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    artifact = output / relative_path
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ManifestVerificationError, match="hash_mismatch"):
        verify_bundle(output / "manifest.json", repository_root=ROOT)


def test_verify_rejects_tampered_expected_result(tmp_path: Path) -> None:
    output = _output_root()
    run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    expected_path = output / "expected-result.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected[0]["critical_alarms"] = 999
    expected_path.write_text(json.dumps(expected), encoding="utf-8")

    with pytest.raises(ManifestVerificationError, match="result_hash_mismatch"):
        verify_bundle(output / "manifest.json", repository_root=ROOT)


def test_verify_rejects_tampered_fixture(tmp_path: Path) -> None:
    import polars as pl

    output = _output_root()
    run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    fixture_path = output / "fixture" / "telemetry_events" / "part-000000.parquet"
    frame = pl.read_parquet(fixture_path).with_columns(pl.lit(False).alias("available"))
    frame.write_parquet(fixture_path)

    with pytest.raises(ManifestVerificationError, match="fixture_hash_mismatch"):
        verify_bundle(output / "manifest.json", repository_root=ROOT)


def test_manifest_contains_no_absolute_paths_or_raw_errors(tmp_path: Path) -> None:
    output = _output_root()
    run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    manifest_text = (output / "manifest.json").read_text(encoding="utf-8")

    assert str(ROOT) not in manifest_text
    assert "traceback" not in manifest_text.lower()
    json.loads(manifest_text)


def test_failed_run_writes_bounded_error_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = _output_root()

    def fail(*args, **kwargs):
        raise ValueError("dbt_reference_failed")

    monkeypatch.setattr("labs.portflow_bigquery.runner.run_local_reference", fail)
    with pytest.raises(ValueError):
        run_bundle(RunSpec(repository_root=ROOT, output_root=output))

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["verification"] == {
        "status": "error",
        "reason_code": "run_failed",
        "verifier_version": "1",
    }
    assert "dbt_reference_failed" not in (output / "manifest.json").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the manifest tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_manifest.py tests/integration/test_bigquery_portability.py -q
```

Expected: FAIL because manifest, runner, and integration modules do not exist yet.

- [ ] **Step 3: Implement the versioned manifest contract**

Use `jsonschema.validate` against an in-module schema with two valid forms:

- a successful manifest requires all artifact, fixture, reference, and
  verification fields below and has `verification.status="ok"`;
- an error manifest contains only the common version/dialect/offline fields and
  `verification.status="error"` with a bounded reason code.

The successful form requires:

```text
schema_version=1
task="PF-106"
dialect="bigquery_google_sql"
execution_mode="offline"
cloud_execution="not_run"
query.path/query.sha256/query.parser/query.dry_run_command
schema.path/schema.sha256
fixture.generator_version/fixture.tables/fixture.rows/fixture.sha256
reference.engine/reference.result_rows/reference.result_sha256
verification.status/verification.reason_code/verification.verifier_version
```

Write JSON with `indent=2`, `sort_keys=True`, and one final newline. Use only
relative artifact paths. The future command string must be exactly:

```text
bq query --use_legacy_sql=false --dry_run --project_id=demo-project < .portability/bigquery/overview_kpis.sql
```

This string is metadata only and must never be passed to a subprocess.

- [ ] **Step 4: Implement bundle orchestration**

`run_bundle` must perform these calls in order:

```python
root = resolve_artifact_root(spec.output_root, repository_root=spec.repository_root)
schema_path = spec.repository_root / "analytics" / "portability" / "bigquery" / "schema.json"
query_path = spec.repository_root / "analytics" / "portability" / "bigquery" / "overview_kpis.sql"
fixture = generate_fixture(
    FixtureSpec(seed=spec.seed),
    root / "fixture",
    schema_path=schema_path,
    repository_root=spec.repository_root,
)
template = query_path.read_text(encoding="utf-8")
query = render_query(template, project_id=spec.project_id, dataset=spec.dataset)
validate_google_sql(query)
write_text(root / "overview_kpis.sql", query)
write_text(root / "schema.json", schema_path.read_text(encoding="utf-8"))
with TemporaryDirectory(prefix="portflow-pf106-") as reference_root:
    reference = run_local_reference(
        repository_root=spec.repository_root,
        fixture_root=root / "fixture",
        gold_db=Path(reference_root) / "portflow.duckdb",
    )
write_json(root / "expected-result.json", list(reference.rows))
write_json(root / "input-fingerprint.json", fixture.as_json())
manifest = build_manifest(
    query_sha256=query_sha256(query),
    schema_sha256=file_sha256(root / "schema.json"),
    fixture=fixture,
    reference=reference,
    dry_run_command="bq query --use_legacy_sql=false --dry_run --project_id=demo-project < .portability/bigquery/overview_kpis.sql",
)
write_manifest(root / "manifest.json", manifest)
verify_bundle(root / "manifest.json", repository_root=spec.repository_root)
return manifest
```

Use `TemporaryDirectory` or a disposable `reference` child for dbt output and
never include that absolute path in the manifest. `verify_bundle` must resolve
the manifest's artifact root, validate the JSON schema, re-run the BigQuery SQL
parser, recompute query/schema/fixture/result hashes, require
`cloud_execution == "not_run"`, and raise one of these stable reason codes:
`manifest_invalid`, `artifact_path_invalid`, `query_hash_mismatch`,
`schema_hash_mismatch`, `fixture_hash_mismatch`, `result_hash_mismatch`, or
`cloud_execution_not_offline`.

Catch known failures after resolving the artifact root and write
`build_error_manifest("run_failed")` to `manifest.json` before re-raising. Do
not write an error manifest when path resolution itself fails. The error
manifest must not include the exception string; the CLI may expose only the
stable reason code.

- [ ] **Step 5: Run integration and failure tests**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_manifest.py tests/integration/test_bigquery_portability.py -q
python -m ruff check labs/portflow_bigquery/manifest.py labs/portflow_bigquery/runner.py tests/unit/test_bigquery_portability_manifest.py tests/integration/test_bigquery_portability.py
python -m mypy labs/portflow_bigquery/manifest.py labs/portflow_bigquery/runner.py
```

Expected: the real local bundle is generated and verified, every tamper test fails for the expected reason, and Ruff/mypy report no errors.

- [ ] **Step 6: Commit the verified bundle engine**

```text
git add labs/portflow_bigquery/manifest.py labs/portflow_bigquery/runner.py tests/unit/test_bigquery_portability_manifest.py tests/integration/test_bigquery_portability.py
git commit -m "feat: add BigQuery portability manifest verification"
```

### Task 7: Add the safe CLI entry point

**Files:**
- Create: `labs/portflow_bigquery/cli.py`
- Create: `labs/portflow_bigquery/__main__.py`
- Test: `tests/unit/test_bigquery_portability_cli.py`

**Interfaces:**
- Produces `main(argv: Sequence[str] | None = None) -> int`.
- Provides subcommands `run` and `verify` only; there is no cloud or network subcommand.

- [ ] **Step 1: Write CLI tests**

```python
from pathlib import Path

from labs.portflow_bigquery.cli import main


def test_help_is_successful() -> None:
    assert main(["--help"]) == 0


def test_run_and_verify_use_local_artifact_defaults(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(spec):
        calls.append(f"run:{spec.project_id}:{spec.dataset}")
        return {"verification": {"status": "ok"}}

    def fake_verify(manifest_path, *, repository_root):
        calls.append(f"verify:{manifest_path.name}")

    monkeypatch.setattr("labs.portflow_bigquery.cli.run_bundle", fake_run)
    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fake_verify)

    assert main(["run", "--output", str(tmp_path / ".portability" / "bigquery")]) == 0
    assert main(["verify", "--manifest", str(tmp_path / ".portability" / "bigquery" / "manifest.json")]) == 0
    assert calls == ["run:demo-project:portflow", "verify:manifest.json"]


def test_cli_failure_does_not_print_exception_text(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "query_hash_mismatch"

    def fail(*args, **kwargs):
        raise Failure("raw secret text")

    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fail)

    assert main(["verify", "--manifest", ".portability/bigquery/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert "query_hash_mismatch" in output
    assert "raw secret text" not in output
```

- [ ] **Step 2: Run CLI tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_cli.py -q
```

Expected: FAIL because the CLI module and module entry point do not exist yet.

- [ ] **Step 3: Implement argparse commands and module entry point**

Create `cli.py` with:

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    if args.command == "run":
        try:
            run_bundle(RunSpec(
                repository_root=Path.cwd(),
                output_root=args.output,
                project_id=args.project_id,
                dataset=args.dataset,
                seed=args.seed,
            ))
        except (OSError, ValueError) as error:
            reason_code = getattr(error, "reason_code", "run_failed")
            print(f"portability run failed: {reason_code}")
            return 1
        print("portability bundle verified")
        return 0
    if args.command == "verify":
        try:
            verify_bundle(args.manifest, repository_root=Path.cwd())
        except (OSError, ValueError, json.JSONDecodeError) as error:
            reason_code = getattr(error, "reason_code", "verification_failed")
            print(f"portability verification failed: {reason_code}")
            return 1
        print("portability bundle verified")
        return 0
    parser.print_help()
    return 2
```

The implementation must print only the bounded success/failure message and, on
known `reason_code` exceptions, the reason code. It must never print the
exception string, subprocess output, environment, or absolute paths. Use these
defaults:

```text
run --output .portability/bigquery --project-id demo-project --dataset portflow --seed 42
verify --manifest .portability/bigquery/manifest.json
```

`__main__.py` must contain only `raise SystemExit(main())` after importing `main`.

- [ ] **Step 4: Run CLI tests and command help**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_cli.py -q
python -m labs.portflow_bigquery --help
python -m ruff check labs/portflow_bigquery/cli.py labs/portflow_bigquery/__main__.py tests/unit/test_bigquery_portability_cli.py
python -m mypy labs/portflow_bigquery/cli.py labs/portflow_bigquery/__main__.py
```

Expected: all CLI tests pass, help lists only `run` and `verify`, and Ruff/mypy report no errors.

- [ ] **Step 5: Commit the CLI**

```text
git add labs/portflow_bigquery/cli.py labs/portflow_bigquery/__main__.py tests/unit/test_bigquery_portability_cli.py
git commit -m "feat: add offline BigQuery portability CLI"
```

### Task 8: Document the runbook, ignore generated artifacts, and close PF-106 evidence

**Files:**
- Modify: `.gitignore`
- Create: `docs/runbooks/bigquery-portability.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Test: `tests/unit/test_bigquery_portability_docs.py`

**Interfaces:**
- The runbook exposes the exact offline commands, artifact boundary, compatibility constraint, and future dry-run handoff.
- The backlog records PF-106 as complete only after all verification evidence passes.

- [ ] **Step 1: Write documentation contract tests**

```python
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_portability_artifacts_are_ignored() -> None:
    assert ".portability/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_runbook_contains_offline_commands_and_boundaries() -> None:
    runbook = (ROOT / "docs" / "runbooks" / "bigquery-portability.md").read_text(encoding="utf-8").lower()

    for phrase in (
        "python -m labs.portflow_bigquery run",
        "python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json",
        "cloud_execution",
        "not_run",
        "countif",
        "timestamp_diff",
        "dry_run",
        "credentials",
        "not public data",
        "remove-item .portability -recurse -force",
    ):
        assert phrase in runbook


def test_readme_and_changelog_link_pf106_evidence() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()

    assert "docs/runbooks/bigquery-portability.md" in readme
    assert "pf-106" in changelog
```

- [ ] **Step 2: Run documentation tests and confirm the intended failure**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_docs.py -q
```

Expected: FAIL because the ignore rule, runbook, README link, and PF-106 changelog entry do not exist yet.

- [ ] **Step 3: Add the artifact ignore rule and runbook**

Append `.portability/` to `.gitignore`. Create the runbook with these exact
sections:

```text
# Offline BigQuery portability runbook
## Scope and artifact boundary
## Prerequisites
## Generate and verify the local bundle
## Inspect the manifest
## Future BigQuery dry-run handoff
## Compatibility limitation
## Cleanup
```

Document these commands exactly:

```text
python -m labs.portflow_bigquery run
python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json
Remove-Item .portability -Recurse -Force
```

Explain that the generated SQL is GoogleSQL-ready but was not sent to BigQuery,
that `cloud_execution` must remain `not_run`, that credentials are neither
required nor inspected, that the fixture is synthetic engineering data and not
public product data, and that the current single-terminal incident association
is preserved for compatibility. Include the exact future command template:

```text
bq query --use_legacy_sql=false --dry_run --project_id=demo-project < .portability/bigquery/overview_kpis.sql
```

Label that command as a future authenticated handoff and do not instruct the
default workflow to run it.

- [ ] **Step 4: Link the runbook and record PF-106 evidence**

Add a paragraph to the existing README local-engine evidence section linking
`docs/runbooks/bigquery-portability.md` and stating that PF-106 is offline and
separate from public data. Add a dated `PF-106` entry to `CHANGELOG.md` with the
same boundary. Update `docs/product/BACKLOG.md` only after the final checks to
mark PF-106 complete, record the spec/plan/implementation commit identifiers,
and set the current next action to PF-107.

- [ ] **Step 5: Run documentation checks and commit**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_docs.py -q
python -m ruff check tests/unit/test_bigquery_portability_docs.py
```

Expected: all documentation contract tests pass.

```text
git add .gitignore docs/runbooks/bigquery-portability.md README.md CHANGELOG.md tests/unit/test_bigquery_portability_docs.py
git commit -m "docs: document PF-106 portability lab"
```

### Task 9: Run the complete verification gate and close the implementation

**Files:**
- Modify: `docs/product/BACKLOG.md` if the evidence entry was not completed in Task 8
- No other source changes are allowed in this task unless a preceding verification command exposes a documented PF-106 defect.

- [ ] **Step 1: Run the focused PF-106 suite**

Run:

```text
python -m pytest tests/unit/test_bigquery_portability_paths.py tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py tests/unit/test_bigquery_portability_query.py tests/unit/test_bigquery_portability_canonical.py tests/unit/test_bigquery_portability_reference.py tests/unit/test_bigquery_portability_manifest.py tests/unit/test_bigquery_portability_cli.py tests/unit/test_bigquery_portability_docs.py tests/integration/test_bigquery_portability.py -q
```

Expected: all focused portability tests pass, including a real local dbt/DuckDB bundle generation and verification.

- [ ] **Step 2: Run static checks and the existing Python suite**

Run:

```text
python -m ruff check labs tests/unit/test_bigquery_portability_paths.py tests/unit/test_bigquery_portability_schema.py tests/unit/test_bigquery_portability_fixture.py tests/unit/test_bigquery_portability_query.py tests/unit/test_bigquery_portability_canonical.py tests/unit/test_bigquery_portability_reference.py tests/unit/test_bigquery_portability_manifest.py tests/unit/test_bigquery_portability_cli.py tests/unit/test_bigquery_portability_docs.py tests/integration/test_bigquery_portability.py
python -m mypy labs/portflow_bigquery
python -m pytest -q
```

Expected: Ruff, mypy, and the full Python suite pass. Any existing environment-only skip remains explicit and bounded.

- [ ] **Step 3: Verify repository boundaries and reproducibility**

Run:

```text
python -m labs.portflow_bigquery run
python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json
git diff --no-index -- .portability/bigquery/manifest.json .portability/bigquery/manifest.json
git status --short
```

Expected: both CLI commands exit zero; the self-comparison produces no diff;
`git status --short` shows only intended committed files; `.portability/` is
ignored; and `git diff -- web/public/data` is empty. Repeat `run` after removing
`.portability/` and confirm the query, schema, fixture, expected-result, and
manifest hashes are identical.

- [ ] **Step 4: Commit final evidence and report completion**

```text
git add docs/product/BACKLOG.md
git commit -m "docs: close PF-106 portability evidence"
```

Report the focused test count, full Python test count, Ruff/mypy results, the
manifest verification result, the final commit identifiers, and the explicit
fact that no BigQuery request or credential lookup occurred.
