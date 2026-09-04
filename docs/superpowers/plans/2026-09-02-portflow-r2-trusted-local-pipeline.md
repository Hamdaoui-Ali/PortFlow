# PortFlow R2 Trusted Local Pipeline Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Reproduce the PortFlow public snapshot through a real local PostgreSQL source, immutable Bronze Parquet, validated Silver data, DuckDB/dbt Gold models, and a deterministic public export without changing the static frontend boundary.

Architecture: PostgreSQL is a local and CI-only OLTP source. A small Python layer owns migrations, deterministic seeding, composite incremental cursors, atomic Parquet writes, Silver validation, and export orchestration. Polars and PyArrow handle typed files; DuckDB and dbt Core calculate documented Gold models; the existing React/Vite site continues to consume only versioned JSON under public/data.

Tech Stack: Python 3.12, psycopg 3, PostgreSQL 16, Polars, PyArrow, DuckDB, dbt Core with dbt-duckdb, Pydantic, JSON Schema, pytest, Ruff, mypy, Docker Compose, GitHub Actions, React, TypeScript, Vite.

Spec: docs/superpowers/specs/2026-09-02-portflow-r2-trusted-local-pipeline-design.md

## Global Constraints

- The public product remains static HTML, CSS, JavaScript, and versioned JSON; the browser never connects to PostgreSQL or DuckDB.
- PostgreSQL runs only locally or in an ephemeral CI service container; no public database, API, account, write endpoint, payment card, or always-on server is introduced.
- Python CI and documented local commands use Python 3.12; uv.lock and web/package-lock.json are authoritative.
- All source and exported timestamps are UTC and serialize with a Z suffix.
- The extractor queries every source table with the composite cursor (updated_at, primary_key).
- A cursor advances only after the staged Parquet partition is validated and atomically committed.
- Bronze input rows equal Silver accepted rows plus quarantined rows for every run.
- Invalid, unreconciled, or oversized data cannot replace the previous public snapshot.
- Stable reason codes are SCHEMA_INVALID, RANGE_INVALID, REFERENCE_INVALID, TEMPORAL_INVALID, and DUPLICATE_KEY.
- Zero-denominator KPI values are null, never zero.
- Identical seed and pipeline inputs produce identical logical rows, counts, Gold values, and export hashes.
- Redpanda, Kafka, Dagster, Prometheus, Grafana, MinIO, PySpark, Terraform, cloud databases, and public streaming remain outside R2.
- Every task ends with a focused commit and a passing focused verification command.

## File map

Create or modify only the files listed by each task:

    compose.yaml
    db/migrations/001_operational_schema.sql
    src/portflow/db/connection.py
    src/portflow/db/migrations.py
    src/portflow/seed.py
    src/portflow/ingestion/cursor.py
    src/portflow/ingestion/postgres_to_bronze.py
    src/portflow/quality/rules.py
    src/portflow/transforms/silver.py
    src/portflow/export/models.py
    src/portflow/export/writer.py
    src/portflow/pipeline.py
    src/portflow/analytics/formulas.py
    scripts/seed_operational.py
    scripts/run_local_pipeline.py
    scripts/verify_r2.ps1
    analytics/dbt_project.yml
    analytics/profiles.yml
    analytics/models/sources.yml
    analytics/models/staging/
    analytics/models/marts/
    analytics/tests/
    schemas/public-snapshot-v1.json
    tests/integration/conftest.py
    tests/integration/test_operational_schema.py
    tests/integration/test_seed.py
    tests/integration/test_bronze_extraction.py
    tests/integration/test_silver.py
    tests/integration/test_gold.py
    tests/integration/test_public_export.py
    tests/unit/test_cursor.py
    tests/unit/test_quality_rules.py
    tests/unit/factories.py
    tests/unit/test_gold_formulas.py
    tests/fixtures/kpi_cases/
    web/src/data/schema.ts
    web/src/data/loadSnapshot.test.ts
    .github/workflows/ci.yml
    .github/workflows/pages.yml
    docs/product/BACKLOG.md
    docs/runbooks/first-deployment.md
    docs/releases/r2-trusted-local-pipeline.md

Test helper interfaces used by the snippets in this plan:

    tests/integration/conftest.py:
      database_url() -> str
      migrations_dir() -> Path
      gold_db(tmp_path) -> Path
      seed_database(database_url: str) -> SeedReport
      append_invalid_bronze_fixture(root: Path, *, missing_reference: bool, bad_range: bool) -> None
      source_metadata() -> PublicSnapshotMetadata
      corrupt_gold_db(gold_db: Path, *, overview_availability: float) -> None

    tests/unit/factories.py:
      valid_telemetry_row(**overrides: object) -> dict[str, object]
      references() -> ReferenceSet
      load_case(name: str) -> dict[str, object]

    integration helpers:
      run_seed(database_url: str, *, seed: int) -> SeedReport
      extract_table_for_test(database_url: str, root: Path, *, batch_size: int = 1000) -> ExtractionResult
      fail_once_with_os_error(path: Path, target: Path) -> None

---

### Task 1: PF-008 — Create the operational PostgreSQL schema

Files:

- Create: compose.yaml
- Create: db/migrations/001_operational_schema.sql
- Create: src/portflow/db/connection.py
- Create: src/portflow/db/migrations.py
- Create: tests/integration/conftest.py
- Create: tests/integration/test_operational_schema.py
- Modify: pyproject.toml, uv.lock, .env.example

Interfaces:

- Consumes: PORTFLOW_DATABASE_URL, defaulting to postgresql://portflow:portflow@localhost:5432/portflow.
- Produces: get_connection() -> psycopg.Connection, apply_migrations(connection, migrations_dir) -> None, and an idempotent schema for all seven source entities.

- [ ] Step 1: Add the locked R2 Python dependencies

Run:

    python -m uv add "psycopg[binary]>=3.2,<4" "polars>=1.25,<2" "pyarrow>=19,<21" "duckdb>=1.2,<2" "dbt-duckdb>=1.9,<2" "jsonschema>=4.23,<5"
    python -m uv lock

Add the database URL and local output directories to .env.example:

    PORTFLOW_DATABASE_URL=postgresql://portflow:portflow@localhost:5432/portflow
    PORTFLOW_BRONZE_DIR=data/bronze
    PORTFLOW_SILVER_DIR=data/silver
    PORTFLOW_QUARANTINE_DIR=data/quarantine
    PORTFLOW_GOLD_DB=data/gold/portflow.duckdb

Expected result: pyproject.toml and uv.lock contain the exact dependency graph, and no cloud SDK is added.

- [ ] Step 2: Write the failing schema tests

Create tests/integration/test_operational_schema.py:

~~~python
from datetime import UTC, datetime

import psycopg
import pytest

from portflow.db.migrations import apply_migrations


def test_migrations_are_idempotent(database_url: str, migrations_dir) -> None:
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        apply_migrations(connection, migrations_dir)
        count = connection.execute(
            "select count(*) from schema_migrations"
        ).fetchone()[0]
    assert count == 1


def test_foreign_key_and_value_checks_reject_invalid_rows(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            connection.execute(
                """
                insert into equipment
                    (equipment_id, terminal_id, equipment_type, commissioning_date,
                     created_at, updated_at)
                values ('QC-999', 'TM-999', 'QUAY_CRANE', %s, %s, %s)
                """,
                (datetime(2026, 1, 1, tzinfo=UTC),) * 3,
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                """
                insert into terminals
                    (terminal_id, name, timezone_name, created_at, updated_at)
                values ('TM-999', 'Bad terminal', 'UTC', %s, %s)
                """,
                (datetime(2026, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
            )
~~~

Run:

    docker compose up -d --wait postgres
    $env:PORTFLOW_DATABASE_URL = "postgresql://portflow:portflow@localhost:5432/portflow"
    python -m uv run pytest tests/integration/test_operational_schema.py -v

Expected result: FAIL because the connection helper, fixture, and migration do not exist.

- [ ] Step 3: Define the migration SQL

Create db/migrations/001_operational_schema.sql. The migration must create schema_migrations, then the seven tables below in dependency order. Use timestamptz for every timestamp, text primary keys, and explicit checks:

~~~sql
create table if not exists schema_migrations (
    filename text primary key,
    checksum_sha256 char(64) not null,
    applied_at timestamptz not null
);

create table if not exists terminals (
    terminal_id text primary key check (terminal_id ~ '^TM-[0-9]{3}$'),
    name text not null check (length(trim(name)) > 0),
    timezone_name text not null default 'UTC',
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create table if not exists equipment (
    equipment_id text primary key check (equipment_id ~ '^[A-Z]{2,4}-[0-9]{3}$'),
    terminal_id text not null references terminals(terminal_id),
    equipment_type text not null check (equipment_type in ('QUAY_CRANE', 'RTG', 'REACH_STACKER')),
    commissioning_date date not null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create table if not exists telemetry_events (
    event_id text primary key check (event_id ~ '^evt-[0-9]{6}-[0-9]{6}$'),
    schema_version smallint not null default 1 check (schema_version = 1),
    equipment_id text not null references equipment(equipment_id),
    terminal_id text not null references terminals(terminal_id),
    event_timestamp timestamptz not null,
    ingestion_timestamp timestamptz not null,
    state text not null check (state in ('IDLE', 'ACTIVE', 'WARNING', 'UNAVAILABLE', 'MAINTENANCE')),
    available boolean not null,
    load_percent numeric(5,2) not null check (load_percent between 0 and 100),
    temperature_c numeric(6,2) not null check (temperature_c between -20 and 150),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (ingestion_timestamp >= event_timestamp),
    check (updated_at >= created_at),
    check ((state in ('UNAVAILABLE', 'MAINTENANCE')) = (not available))
);

create table if not exists alarms (
    alarm_id text primary key check (alarm_id ~ '^alm-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    severity text not null check (severity in ('INFO', 'WARNING', 'CRITICAL')),
    code text not null check (length(trim(code)) > 0),
    opened_at timestamptz not null,
    cleared_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (cleared_at is null or cleared_at >= opened_at),
    check (updated_at >= created_at)
);

create table if not exists incidents (
    incident_id text primary key check (incident_id ~ '^inc-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    severity text not null check (severity in ('MINOR', 'MAJOR', 'CRITICAL')),
    status text not null check (status in ('OPEN', 'RESOLVED')),
    opened_at timestamptz not null,
    resolved_at timestamptz,
    root_cause text not null check (length(trim(root_cause)) > 0),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (resolved_at is null or resolved_at >= opened_at),
    check ((status = 'RESOLVED') = (resolved_at is not null)),
    check (updated_at >= created_at)
);

create table if not exists maintenance_orders (
    maintenance_order_id text primary key check (maintenance_order_id ~ '^mnt-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    status text not null check (status in ('PLANNED', 'IN_PROGRESS', 'COMPLETED')),
    started_at timestamptz not null,
    completed_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (completed_at is null or completed_at >= started_at),
    check ((status = 'COMPLETED') = (completed_at is not null)),
    check (updated_at >= created_at)
);

create table if not exists container_movements (
    movement_id text primary key check (movement_id ~ '^mov-[0-9]{6}$'),
    terminal_id text not null references terminals(terminal_id),
    equipment_id text not null references equipment(equipment_id),
    movement_type text not null check (movement_type in ('GATE_IN', 'GATE_OUT', 'LOAD', 'DISCHARGE')),
    container_ref text not null check (length(trim(container_ref)) > 0),
    event_timestamp timestamptz not null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create index if not exists idx_equipment_updated_cursor
    on equipment (updated_at, equipment_id);
create index if not exists idx_telemetry_updated_cursor
    on telemetry_events (updated_at, event_id);
create index if not exists idx_alarms_updated_cursor
    on alarms (updated_at, alarm_id);
create index if not exists idx_incidents_updated_cursor
    on incidents (updated_at, incident_id);
create index if not exists idx_maintenance_updated_cursor
    on maintenance_orders (updated_at, maintenance_order_id);
create index if not exists idx_movements_updated_cursor
    on container_movements (updated_at, movement_id);
~~~

The migration must be safe to run more than once. The migration runner computes the file SHA-256, inserts the filename and checksum in one transaction, and raises a clear error if an applied filename has a different checksum.

- [ ] Step 4: Implement the connection, migration runner, and integration fixture

Implement these exact signatures:

~~~python
# src/portflow/db/connection.py
def get_connection(database_url: str | None = None) -> psycopg.Connection:
    raise NotImplementedError("implement in PF-008")

# src/portflow/db/migrations.py
def apply_migrations(connection: psycopg.Connection, migrations_dir: Path) -> None:
    raise NotImplementedError("implement in PF-008")
~~~

The fixture reads PORTFLOW_DATABASE_URL, calls apply_migrations before each test, truncates child tables in reverse dependency order after each test, and raises a message containing docker compose up -d --wait postgres when the URL is unavailable. Use psycopg.sql.Identifier for identifiers and parameters for values.

- [ ] Step 5: Run the schema tests and static checks

Run:

    python -m uv run pytest tests/integration/test_operational_schema.py -v
    python -m uv run ruff check src/portflow/db tests/integration
    python -m uv run mypy src/portflow/db

Expected result: both integration tests and static checks pass.

- [ ] Step 6: Commit PF-008

    git add compose.yaml db/migrations src/portflow/db tests/integration/conftest.py tests/integration/test_operational_schema.py pyproject.toml uv.lock .env.example scripts/verify.ps1
    git commit -m "feat: add operational PostgreSQL schema"

---

### Task 2: PF-009 — Seed deterministic connected source data

Files:

- Create: src/portflow/seed.py
- Create: scripts/seed_operational.py
- Create: tests/integration/test_seed.py
- Modify: src/portflow/domain/models.py, tests/integration/conftest.py

Interfaces:

- Consumes: an open psycopg connection and seed integer.
- Produces: seed_operational(connection, seed=42) -> SeedReport and a stable digest over connected source rows.

- [ ] Step 1: Write the failing seed tests

Create tests/integration/test_seed.py:

~~~python
def test_seed_is_idempotent(database_url: str) -> None:
    first = run_seed(database_url, seed=42)
    second = run_seed(database_url, seed=42)

    assert first.row_counts == second.row_counts
    assert first.digest_sha256 == second.digest_sha256
    assert first.row_counts == {
        "terminals": 1,
        "equipment": 1,
        "telemetry_events": 288,
        "alarms": 3,
        "incidents": 2,
        "maintenance_orders": 2,
        "container_movements": 8,
    }


def test_seed_creates_connected_references(database_url: str) -> None:
    run_seed(database_url, seed=42)
    with psycopg.connect(database_url) as connection:
        orphan_count = connection.execute(
            """
            select count(*)
            from telemetry_events t
            left join equipment e on e.equipment_id = t.equipment_id
            left join terminals m on m.terminal_id = t.terminal_id
            where e.equipment_id is null or m.terminal_id is null
            """
        ).fetchone()[0]
    assert orphan_count == 0
~~~

Run:

    python -m uv run pytest tests/integration/test_seed.py -v

Expected result: FAIL because run_seed and seed_operational do not exist.

- [ ] Step 2: Define deterministic fixture data

Use the existing simulator with seed 42, QC-001, TM-001, 288 five-minute events, and 2026-09-02T00:00:00Z. Derive created_at and updated_at from each event's ingestion_timestamp; never call datetime.now() in seed.py.

Add stable rows with these exact identifiers and relationships:

    terminals: TM-001
    equipment: QC-001
    alarms: alm-000001, alm-000002, alm-000003
    incidents: inc-000001, inc-000002
    maintenance_orders: mnt-000001, mnt-000002
    container_movements: mov-000001 through mov-000008

Use deterministic timestamps within the source period. Include one open incident, one resolved incident, one cleared alarm, one uncleared critical alarm, one completed maintenance order, one in-progress maintenance order, and both completed movement pairs needed for dwell time.

- [ ] Step 3: Implement upsert seed and canonical digest

Implement:

~~~python
@dataclass(frozen=True, slots=True)
class SeedReport:
    seed: int
    row_counts: dict[str, int]
    digest_sha256: str


def seed_operational(
    connection: psycopg.Connection,
    *,
    seed: int,
) -> SeedReport:
    raise NotImplementedError("implement in PF-009")
~~~

Insert parent rows before children with PostgreSQL upsert syntax using ON CONFLICT on each primary key and DO UPDATE with the same values. Serialize digest rows in table-name and primary-key order using JSON sort_keys=True, separators=(',', ':'), and a terminal newline, then hash UTF-8 bytes with SHA-256. Commit once after all tables succeed; roll back on any exception.

Add scripts/seed_operational.py that reads PORTFLOW_DATABASE_URL, applies migrations, calls seed_operational(seed=42), and prints the JSON SeedReport.

- [ ] Step 4: Run seed tests and verify no duplicates

Run:

    python -m uv run pytest tests/integration/test_seed.py -v
    python -m uv run python scripts/seed_operational.py
    python -m uv run python scripts/seed_operational.py

Expected result: tests pass, both command outputs have the same digest, and each primary-key count is unchanged.

- [ ] Step 5: Commit PF-009

    git add src/portflow/seed.py scripts/seed_operational.py tests/integration/test_seed.py tests/integration/conftest.py
    git commit -m "feat: seed deterministic operational fixture"

---

### Task 3: PF-010 — Extract incremental Bronze Parquet

Files:

- Create: src/portflow/ingestion/__init__.py
- Create: src/portflow/ingestion/cursor.py
- Create: src/portflow/ingestion/postgres_to_bronze.py
- Create: tests/unit/test_cursor.py
- Create: tests/integration/test_bronze_extraction.py
- Modify: pyproject.toml, uv.lock

Interfaces:

- Consumes: a PostgreSQL connection, table specification, cursor state path, Bronze output path, run ID, and batch size.
- Produces: SourceCursor, CursorStore, ExtractionResult, read_cursor(), write_cursor(), and extract_table().

- [ ] Step 1: Write cursor and failure tests

Create tests/unit/test_cursor.py:

~~~python
def test_equal_timestamps_are_ordered_by_primary_key() -> None:
    cursor = SourceCursor(datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000010")
    candidates = [
        (datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000011"),
        (datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000009"),
    ]
    assert max(candidates) > (cursor.updated_at, cursor.primary_key)


def test_failed_cursor_write_keeps_previous_state(tmp_path: Path) -> None:
    store = CursorStore(tmp_path / "cursors.json")
    original = SourceCursor(datetime(2026, 9, 2, tzinfo=UTC), "evt-000042-000001")
    store.save({"telemetry_events": original})
    with pytest.raises(OSError):
        store.save({"telemetry_events": SourceCursor(datetime(2026, 9, 2, tzinfo=UTC), "evt-000042-000002")}, replace=lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    assert store.load()["telemetry_events"] == original
~~~

Create tests/integration/test_bronze_extraction.py:

~~~python
def test_extraction_handles_ties_and_is_logically_idempotent(database_url, tmp_path) -> None:
    seed_database(database_url)
    first = extract_table_for_test(database_url, tmp_path, batch_size=37)
    second = extract_table_for_test(database_url, tmp_path, batch_size=37)
    assert first.logical_row_count == 288
    assert second.logical_row_count == 288
    assert first.content_sha256 == second.content_sha256


def test_failed_partition_does_not_advance_cursor(database_url, tmp_path, monkeypatch) -> None:
    seed_database(database_url)
    monkeypatch.setattr(Path, "replace", fail_once_with_os_error)
    with pytest.raises(OSError):
        extract_table_for_test(database_url, tmp_path)
    assert read_cursor(tmp_path / "state/cursors.json", "telemetry_events") is None
    assert not list((tmp_path / "bronze").rglob("*.parquet"))
~~~

Run the focused tests. They must fail before implementation:

    python -m uv run pytest tests/unit/test_cursor.py tests/integration/test_bronze_extraction.py -v

- [ ] Step 2: Implement the typed cursor and atomic state file

Use:

~~~python
@dataclass(frozen=True, order=True, slots=True)
class SourceCursor:
    updated_at: datetime
    primary_key: str


class CursorStore:
    def load(self) -> dict[str, SourceCursor]:
        raise NotImplementedError("implement in PF-010")
    def save(self, cursors: Mapping[str, SourceCursor | None], replace=os.replace) -> None:
        raise NotImplementedError("implement in PF-010")


def read_cursor(path: Path, table_name: str) -> SourceCursor | None:
    raise NotImplementedError("implement in PF-010")


def write_cursor(path: Path, table_name: str, cursor: SourceCursor) -> None:
    raise NotImplementedError("implement in PF-010")
~~~

Validate UTC timestamps, serialize the state file canonically, write a sibling .tmp file, flush and fsync it, then use os.replace. A failed replace leaves the existing state file byte-for-byte unchanged.

- [ ] Step 3: Implement table specifications and extraction

Define a table specification mapping each table to its primary-key column and ordered source columns. For telemetry_events, query exactly:

~~~sql
select event_id, schema_version, equipment_id, terminal_id, event_timestamp,
       ingestion_timestamp, state, available, load_percent, temperature_c,
       created_at, updated_at
from telemetry_events
where (updated_at, event_id) > (%s, %s)
order by updated_at, event_id
limit %s
~~~

Use the same query shape for each table, substituting only the allow-listed table specification and its primary-key column. Implement:

~~~python
@dataclass(frozen=True, slots=True)
class ExtractionResult:
    table_name: str
    row_count: int
    logical_row_count: int
    partition_path: Path | None
    content_sha256: str | None
    next_cursor: SourceCursor | None


def extract_table(
    connection: psycopg.Connection,
    *,
    table_name: str,
    cursor_store: CursorStore,
    bronze_dir: Path,
    run_id: str,
    batch_size: int = 1000,
) -> ExtractionResult:
    raise NotImplementedError("implement in PF-010")
~~~

Write each batch as Polars data with source_table, extraction_run_id, source_updated_at, and extracted_at metadata. Use an extracted_at value derived from the batch maximum ingestion timestamp plus a fixed two-second offset; do not use wall-clock time. Write to bronze/.staging, validate the row count and schema, compute SHA-256, and atomically move to a partition path shaped like data/bronze/{table_name}/date={UTC-date}/part-{cursor-updated-at}-{cursor-primary-key}.parquet. Only after the move succeeds, update the cursor. If the target path already exists, verify its hash and reuse it.

- [ ] Step 4: Run extraction tests and static checks

Run:

    python -m uv run pytest tests/unit/test_cursor.py tests/integration/test_bronze_extraction.py -v
    python -m uv run ruff check src/portflow/ingestion tests/unit/test_cursor.py tests/integration/test_bronze_extraction.py
    python -m uv run mypy src/portflow/ingestion

Expected result: equal timestamps are not skipped, retries do not add logical duplicates, and failed writes leave the cursor unchanged.

- [ ] Step 5: Commit PF-010

    git add src/portflow/ingestion tests/unit/test_cursor.py tests/integration/test_bronze_extraction.py pyproject.toml uv.lock
    git commit -m "feat: add cursor-safe Bronze extraction"

---

### Task 4: PF-011 — Validate Silver rows and quarantine failures

Files:

- Create: src/portflow/quality/__init__.py
- Create: src/portflow/quality/rules.py
- Create: src/portflow/transforms/__init__.py
- Create: src/portflow/transforms/silver.py
- Create: tests/unit/test_quality_rules.py
- Create: tests/integration/test_silver.py

Interfaces:

- Consumes: Bronze Parquet partitions and validated reference sets.
- Produces: ValidationIssue, validate_row(), SilverRunReport, and transform_bronze_to_silver().

Define the reference type in src/portflow/quality/rules.py before the validator:

~~~python
@dataclass(frozen=True, slots=True)
class ReferenceSet:
    terminal_ids: frozenset[str]
    equipment_ids: frozenset[str]
~~~

- [ ] Step 1: Write the failing rule tests

Create tests/unit/test_quality_rules.py:

~~~python
def test_bad_load_gets_range_invalid() -> None:
    row = valid_telemetry_row(load_percent=101)
    issues = validate_row("telemetry_events", row, references())
    assert [issue.code for issue in issues] == ["RANGE_INVALID"]


def test_unknown_equipment_gets_reference_invalid() -> None:
    row = valid_telemetry_row(equipment_id="QC-999")
    issues = validate_row("telemetry_events", row, references())
    assert [issue.code for issue in issues] == ["REFERENCE_INVALID"]


def test_duplicate_identifier_gets_duplicate_key() -> None:
    row = valid_telemetry_row(event_id="evt-000042-000001")
    issues = validate_row("telemetry_events", row, references(), seen_keys={"evt-000042-000001"})
    assert [issue.code for issue in issues] == ["DUPLICATE_KEY"]
~~~

Create tests/integration/test_silver.py:

~~~python
def test_silver_reconciles_accepted_and_quarantined_rows(database_url, tmp_path) -> None:
    seed_database(database_url)
    append_invalid_bronze_fixture(tmp_path, missing_reference=True, bad_range=True)
    report = transform_bronze_to_silver(
        bronze_dir=tmp_path / "bronze",
        silver_dir=tmp_path / "silver",
        quarantine_dir=tmp_path / "quarantine",
    )
    assert report.bronze_rows == report.silver_rows + report.quarantine_rows
    assert report.quarantine_reason_counts == {"RANGE_INVALID": 1, "REFERENCE_INVALID": 1}
~~~

Run:

    python -m uv run pytest tests/unit/test_quality_rules.py tests/integration/test_silver.py -v

Expected result: FAIL because rule and transform functions do not exist.

- [ ] Step 2: Implement reason-coded validation

Implement:

~~~python
VALID_REASON_CODES = (
    "SCHEMA_INVALID",
    "RANGE_INVALID",
    "REFERENCE_INVALID",
    "TEMPORAL_INVALID",
    "DUPLICATE_KEY",
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: Literal[
        "SCHEMA_INVALID",
        "RANGE_INVALID",
        "REFERENCE_INVALID",
        "TEMPORAL_INVALID",
        "DUPLICATE_KEY",
    ]
    detail: str


def validate_row(
    table_name: str,
    row: Mapping[str, object],
    reference_set: ReferenceSet,
    *,
    seen_keys: set[str] | None = None,
) -> list[ValidationIssue]:
    raise NotImplementedError("implement in PF-011")
~~~

Return reason codes in the fixed order SCHEMA_INVALID, RANGE_INVALID, REFERENCE_INVALID, TEMPORAL_INVALID, DUPLICATE_KEY. Validate required columns and types, ranges from the domain models, foreign-key membership, event/ingestion ordering, opened/resolved ordering, and duplicate primary keys.

- [ ] Step 3: Implement Silver and quarantine writers

Implement:

~~~python
@dataclass(frozen=True, slots=True)
class SilverRunReport:
    bronze_rows: int
    silver_rows: int
    quarantine_rows: int
    quarantine_reason_counts: dict[str, int]


def transform_bronze_to_silver(
    *,
    bronze_dir: Path,
    silver_dir: Path,
    quarantine_dir: Path,
) -> SilverRunReport:
    raise NotImplementedError("implement in PF-011")
~~~

Read every Bronze partition in deterministic path order. Normalize timestamps to UTC, keep accepted rows in typed Silver Parquet, and write quarantine rows with raw_payload, source_table, primary_key, reason_codes, and reason_details. Use one row per Bronze input and never silently drop a row. Deduplicate using the stable primary key and keep the row with the greatest (source_updated_at, extraction_run_id); emit discarded duplicates as DUPLICATE_KEY quarantine rows.

- [ ] Step 4: Run Silver tests, reconciliation, and static checks

Run:

    python -m uv run pytest tests/unit/test_quality_rules.py tests/integration/test_silver.py -v
    python -m uv run ruff check src/portflow/quality src/portflow/transforms tests
    python -m uv run mypy src/portflow/quality src/portflow/transforms

Expected result: all five reason-code paths pass and Bronze equals Silver plus quarantine.

- [ ] Step 5: Commit PF-011

    git add src/portflow/quality src/portflow/transforms tests/unit/test_quality_rules.py tests/integration/test_silver.py
    git commit -m "feat: validate Silver data and quarantine rejects"

---

### Task 5: PF-012 — Build DuckDB/dbt Gold models and KPI tests

Files:

- Create: analytics/dbt_project.yml
- Create: analytics/profiles.yml
- Create: analytics/models/sources.yml
- Create: analytics/models/staging/stg_telemetry_events.sql
- Create: analytics/models/staging/stg_alarms.sql
- Create: analytics/models/staging/stg_incidents.sql
- Create: analytics/models/staging/stg_maintenance_orders.sql
- Create: analytics/models/staging/stg_container_movements.sql
- Create: analytics/models/marts/fct_equipment_telemetry.sql
- Create: analytics/models/marts/fct_incidents.sql
- Create: analytics/models/marts/fct_movements.sql
- Create: analytics/models/marts/overview_kpis.sql
- Create: analytics/models/schema.yml
- Create: analytics/tests/assert_overview_kpis_reconcile.sql
- Create: tests/fixtures/kpi_cases/normal.json
- Create: tests/fixtures/kpi_cases/empty_denominators.json
- Create: tests/fixtures/kpi_cases/boundary_timestamps.json
- Create: tests/unit/test_gold_formulas.py
- Create: tests/integration/test_gold.py

Interfaces:

- Consumes: Silver Parquet under PORTFLOW_SILVER_DIR.
- Produces: a DuckDB file at PORTFLOW_GOLD_DB, dbt models overview_kpis, fct_equipment_telemetry, fct_incidents, and fct_movements, plus dbt build success.

Define src/portflow/analytics/formulas.py for hand-calculated fixture expectations:

~~~python
def calculate_fixture_case(case: Mapping[str, object]) -> dict[str, float | int | None]:
    raise NotImplementedError("implement in PF-012")
~~~

- [ ] Step 1: Write hand-calculated KPI fixtures and failing tests

Create tests/unit/test_gold_formulas.py with exact expected behavior:

~~~python
@pytest.mark.parametrize(
    ("case_name", "expected"),
    [
        ("normal", {"availability": 0.75, "utilization": 2 / 3, "mttr_minutes": 30.0, "mtbf_hours": 4.0}),
        ("empty_denominators", {"availability": None, "utilization": None, "mttr_minutes": None, "mtbf_hours": None}),
        ("boundary_timestamps", {"throughput": 2, "average_dwell_minutes": 45.0}),
    ],
)
def test_kpi_fixture(case_name: str, expected: dict[str, float | int | None]) -> None:
    assert calculate_fixture_case(load_case(case_name)) == expected
~~~

The fixture definitions must use these formulas:

    throughput = count(completed movements)
    average_dwell_minutes = mean(exit_timestamp - entry_timestamp) for completed pairs
    availability = available_intervals / scheduled_intervals, or null if scheduled_intervals = 0
    utilization = active_intervals / available_intervals, or null if available_intervals = 0
    mttr_minutes = sum(resolved incident durations) / resolved incident count, or null if count = 0
    mtbf_hours = operating_hours / qualifying failure count, or null if failure count = 0
    active_incidents = incidents open at source_period_end
    critical_alarms = critical alarms whose opened_at is in the selected period

Run the tests and confirm they fail because the Gold calculation helper and models do not exist.

- [ ] Step 2: Define the dbt project and external Parquet profile

analytics/profiles.yml must use DuckDB and an environment-controlled file:

~~~yaml
portflow:
  target: local
  outputs:
    local:
      type: duckdb
      path: "{{ env_var('PORTFLOW_GOLD_DB', 'data/gold/portflow.duckdb') }}"
      schema: main
      threads: 1
~~~

The model SQL uses read_parquet against POSIX-normalized PORTFLOW_SILVER_DIR paths. No absolute developer path is committed. Add dbt generic tests for not_null, unique, accepted values, relationships, and source row counts.

- [ ] Step 3: Implement staging, facts, and overview SQL

Each staging model selects only the typed Silver columns and casts numeric fields. Facts preserve their declared grain:

    fct_equipment_telemetry: one row per telemetry event_id
    fct_incidents: one row per incident_id
    fct_movements: one row per movement_id
    overview_kpis: one row per terminal_id and source-period boundary

Use DuckDB date/time functions and explicit casts. Put all KPI formulas in overview_kpis.sql; the React application does not calculate business metrics. Include available_intervals, scheduled_intervals, active_intervals, available_time_minutes, resolved_incident_count, repair_minutes, qualifying_failure_count, operating_hours, throughput, average_dwell_minutes, availability, utilization, mttr_minutes, mtbf_hours, active_incidents, and critical_alarms.

- [ ] Step 4: Run dbt and integration tests

Run with an extracted Silver fixture:

    $env:PORTFLOW_SILVER_DIR = (Resolve-Path data/silver).Path.Replace('\', '/')
    $env:PORTFLOW_GOLD_DB = (Resolve-Path data/gold).Path + "/portflow.duckdb"
    python -m uv run dbt build --project-dir analytics --profiles-dir analytics --vars "{silver_root: '$env:PORTFLOW_SILVER_DIR'}"
    python -m uv run pytest tests/unit/test_gold_formulas.py tests/integration/test_gold.py -v

Expected result: dbt tests pass, every hand-calculated fixture matches, and every model has a declared grain.

- [ ] Step 5: Commit PF-012

    git add analytics tests/fixtures/kpi_cases tests/unit/test_gold_formulas.py tests/integration/test_gold.py pyproject.toml uv.lock
    git commit -m "feat: add tested DuckDB dbt Gold models"

---

### Task 6: PF-013 — Export the complete versioned public snapshot

Files:

- Create: src/portflow/export/models.py
- Create: src/portflow/export/writer.py
- Create: schemas/public-snapshot-v1.json
- Create: tests/integration/test_public_export.py
- Create: scripts/run_local_pipeline.py
- Create: src/portflow/pipeline.py
- Modify: src/portflow/export/snapshot.py, web/src/data/schema.ts, web/src/data/loadSnapshot.test.ts, docs/adr/0002-snapshot-contract.md

Interfaces:

- Consumes: Gold DuckDB tables and the existing demo-v1 overview contract.
- Produces: write_public_snapshot(output_dir, gold_db, source_metadata) -> Path, full dataset files, verified hashes, and an end-to-end pipeline command.

- [ ] Step 1: Write export contract tests before implementation

Create tests/integration/test_public_export.py:

~~~python
def test_export_contains_all_datasets_and_verified_hashes(tmp_path, gold_db) -> None:
    manifest_path = write_public_snapshot(
        output_dir=tmp_path / "public/data",
        gold_db=gold_db,
        source_metadata=source_metadata(),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"overview", "equipment", "incidents", "event_replay", "quality"}
    assert set(manifest["datasets"]) == required
    for entry in manifest["datasets"].values():
        dataset = (manifest_path.parent / entry["path"]).read_bytes()
        assert hashlib.sha256(dataset).hexdigest() == entry["sha256"]
    assert manifest["quality_status"] == "PASS"


def test_export_rejects_gold_export_mismatch(tmp_path, gold_db) -> None:
    corrupt_gold_db(gold_db, overview_availability=0.1)
    with pytest.raises(ExportValidationError, match="Gold-to-export reconciliation"):
        write_public_snapshot(tmp_path / "public/data", gold_db, source_metadata())
    assert not (tmp_path / "public/data/manifest.json").exists()
~~~

Run:

    python -m uv run pytest tests/integration/test_public_export.py -v

Expected result: FAIL because the full writer, schema, and reconciliation do not exist.

- [ ] Step 2: Define the JSON Schema

Create schemas/public-snapshot-v1.json. Require schema_version 1, snapshot_id, generated_at, source_period_start, source_period_end, quality_status PASS, record_counts, and five dataset entries. Each dataset entry requires a safe relative .json path and a lowercase 64-character SHA-256. Define:

    overview: terminal_id and availability counts/value
    equipment: equipment_id, terminal_id, current state, availability, utilization, alarm count, downtime minutes, MTTR, MTBF
    incidents: incident_id, equipment_id, severity, status, opened_at, resolved_at, root_cause
    event_replay: event_id, equipment_id, terminal_id, event_timestamp, state, available
    quality: bronze_rows, silver_rows, quarantine_rows, reason_counts, dbt_test_status

The schema must reject absolute paths, parent traversal, unsupported schema versions, values outside their documented ranges, and a non-null value when its denominator is zero.

- [ ] Step 3: Implement canonical models and atomic writer

Implement:

~~~python
@dataclass(frozen=True, slots=True)
class PublicSnapshotMetadata:
    snapshot_id: str
    generated_at: datetime
    source_period_start: datetime
    source_period_end: datetime


def write_public_snapshot(
    output_dir: Path,
    gold_db: Path,
    source_metadata: PublicSnapshotMetadata,
) -> Path:
    raise NotImplementedError("implement in PF-013")
~~~

Read Gold rows in deterministic key order. Serialize every dataset as UTF-8 JSON using sort_keys=True, separators=(',', ':'), and a terminal newline. Write to output_dir/.staging/{snapshot_id}, validate against JSON Schema, verify Gold-to-export counts and KPI values, compute SHA-256, then atomically move the immutable snapshot directory and replace manifest.json last. Never delete the previous manifest or snapshot when validation fails. Keep write_first_snapshot available as the R1 compatibility wrapper.

- [ ] Step 4: Add the full pipeline command

Implement:

~~~python
def run_local_pipeline(
    *,
    database_url: str,
    output_dir: Path,
    seed: int = 42,
) -> Path:
    raise NotImplementedError("implement in R2 pipeline wiring")
~~~

The stages are migrations, seed, extraction for all seven tables, Silver transform, dbt build, Gold reconciliation, and public export. Use one deterministic run ID derived from the seed and source period. Print one JSON report with stage names, row counts, hashes, and quality status. Return non-zero on any failed stage.

scripts/run_local_pipeline.py reads PORTFLOW_DATABASE_URL and invokes run_local_pipeline(output_dir=Path('web/public/data')). It must not alter web/public/data when a stage fails.

- [ ] Step 5: Extend the frontend manifest validator without breaking R1

Update web/src/data/schema.ts so overview remains required while equipment, incidents, event_replay, and quality dataset entries and their record counts are accepted. Keep safe relative paths, schema version 1, UTC timestamps, lowercase SHA-256, and availability consistency checks. Add a fixture containing all five datasets to web/src/data/loadSnapshot.test.ts; keep the old overview-only fixture as a backward-compatibility test.

- [ ] Step 6: Run export, frontend, and idempotency tests

Run:

    python -m uv run python scripts/run_local_pipeline.py
    git diff --exit-code -- web/public/data
    python -m uv run python scripts/run_local_pipeline.py
    git diff --exit-code -- web/public/data
    python -m uv run pytest tests/integration/test_public_export.py -v
    npm --prefix web test -- --run
    npm --prefix web run typecheck

Expected result: the first run creates overview.json, equipment.json, incidents.json, event-replay.json, quality.json, and manifest.json; the second run creates no diff; all hashes and frontend contracts pass.

- [ ] Step 7: Commit PF-013

    git add src/portflow/export src/portflow/pipeline.py scripts/run_local_pipeline.py schemas tests/integration/test_public_export.py web/src/data/schema.ts web/src/data/loadSnapshot.test.ts docs/adr/0002-snapshot-contract.md web/public/data
    git commit -m "feat: export complete validated public snapshot"

---

### Task 7: R2 release gate — CI, local commands, and evidence

Files:

- Create: scripts/verify_r2.ps1
- Create: docs/releases/r2-trusted-local-pipeline.md
- Modify: .github/workflows/ci.yml, .github/workflows/pages.yml, docs/product/BACKLOG.md, docs/runbooks/first-deployment.md, scripts/verify.ps1

Interfaces:

- Consumes: compose.yaml, run_local_pipeline.py, all unit/integration tests, and the existing Pages build.
- Produces: a clean-clone R2 command, CI service database, deterministic public data, and an auditable release record.

- [ ] Step 1: Add the R2 verification entry point

Create scripts/verify_r2.ps1:

~~~powershell
$ErrorActionPreference = "Stop"
docker compose up -d --wait postgres
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:PORTFLOW_DATABASE_URL = "postgresql://portflow:portflow@localhost:5432/portflow"
try {
    python -m uv run python scripts/run_local_pipeline.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    git diff --exit-code -- web/public/data
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run mypy src
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web test -- --run
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Remove-Item Env:PORTFLOW_DATABASE_URL -ErrorAction SilentlyContinue
}
~~~

Keep scripts/verify.ps1 as the fast non-container gate and make its Python test command include all unit tests. Use verify_r2.ps1 for the complete release gate.

- [ ] Step 2: Add PostgreSQL services to both workflows

Add this service to .github/workflows/ci.yml and .github/workflows/pages.yml:

~~~yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: portflow
      POSTGRES_PASSWORD: portflow
      POSTGRES_DB: portflow
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U portflow -d portflow"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 20
~~~

Set PORTFLOW_DATABASE_URL to postgresql://portflow:portflow@localhost:5432/portflow. Replace the old first-snapshot command with python -m uv run python scripts/run_local_pipeline.py, then assert git diff --exit-code -- web/public/data. Pages must continue to set VITE_BASE_PATH=/PortFlow/, run the quality gate, run web/scripts/verify-pages-build.mjs, and upload only web/dist.

- [ ] Step 3: Document the local and Pages release workflow

Update docs/runbooks/first-deployment.md with:

    docker compose up -d --wait postgres
    python -m uv sync --extra dev --frozen
    npm --prefix web ci
    ./scripts/verify_r2.ps1
    docker compose down

Document that the public website remains static, PostgreSQL is disposable local/CI state, and a failed pipeline leaves the prior manifest and snapshot untouched.

- [ ] Step 4: Record the R2 evidence and move the backlog checkpoint

Create docs/releases/r2-trusted-local-pipeline.md with the commit, commands, exit codes, database image, seed, row counts, Bronze/Silver/quarantine reconciliation, dbt test result, export hashes, and known exclusions. Update docs/product/BACKLOG.md current next action from PF-001 to PF-008 and add a completed R1 checkpoint pointing to the six existing commits and the R1 design/plan.

- [ ] Step 5: Run the complete release gate

Run:

    python -m uv lock --check
    npm --prefix web ci
    ./scripts/verify_r2.ps1
    python -c "import pathlib, yaml; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
    git diff --check
    git diff --exit-code

Expected result: the Compose database is healthy, all Python and frontend tests pass, dbt reports PASS, the generated public data is deterministic, both workflows parse, and the worktree is clean.

- [ ] Step 6: Commit the R2 release gate

    git add scripts/verify_r2.ps1 .github/workflows docs/releases docs/runbooks/first-deployment.md docs/product/BACKLOG.md scripts/verify.ps1
    git commit -m "ci: verify complete trusted local pipeline"

## Completion checkpoint

Stop after the R2 release gate. Review the generated public datasets and evidence record before starting R3 PF-014. R3 may consume Gold/export interfaces established here, but it must not make the frontend connect to PostgreSQL or DuckDB.
