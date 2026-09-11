# PortFlow Local Data Workspace and Navigation Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make PortFlow navigation deterministic and expose a safe local workflow for checking PostgreSQL, seeding or importing operational records, refreshing the static snapshot, and viewing the result in the existing application.

**Architecture:** Keep the public application static and snapshot-driven. Add a loopback-only Python HTTP service that reuses the current migrations, seed routine, table allowlist, validation rules, and pipeline; add a typed client and a Data Health workspace that talks to that service only during local development. Eagerly load the five route pages and preserve the active hash when global filters update the URL.

**Tech Stack:** Python 3.12 standard-library http.server, psycopg 3, Pydantic/Polars existing project dependencies, React 19, TypeScript 7, Vite 8, Vitest 4, Testing Library, PostgreSQL 16, Docker Compose.

**Spec:** docs/superpowers/specs/2026-09-11-local-data-workspace-design.md

## Global Constraints

- Keep the approved navigation labels and visual system in docs/design/PORTFLOW_UI_SPEC.md.
- Keep the five existing destinations: Overview, Equipment, Incidents, Live Demo, and Data Health.
- The browser must never connect directly to PostgreSQL, DuckDB, or a production database.
- The local service binds to 127.0.0.1 only and does not allow hosted origins.
- Reuse the existing TABLE_SPECS, migration runner, seed routine, validation rules, and local pipeline.
- Do not add a public account flow, public write API, authentication system, hosted database, or arbitrary SQL access.
- Do not add a Python web-framework dependency or a browser runtime dependency for this feature.
- Import payloads are JSON in this first slice; CSV and per-entity forms are explicitly out of scope.
- Use the existing typography, colors, borders, spacing, focus treatment, and minimum target sizes.
- Do not invoke Sites build or hosting; preview and verify locally.

## File Map

| File | Responsibility |
| --- | --- |
| web/src/app/App.tsx | Deterministic route-page imports and route rendering. |
| web/src/app/AppShell.tsx | Preserve the route hash while writing global filters. |
| web/src/data/localApi.ts | Typed browser client for /api/status, /api/schema, /api/seed, /api/import, and /api/refresh. |
| web/src/features/health/LocalDataWorkspace.tsx | Local connection, JSON import, seed, and snapshot refresh UI inside Data Health. |
| web/src/features/health/DataHealthPage.tsx | Compose the workspace with the existing health metrics. |
| web/src/styles.css | Workspace layout and control states using existing tokens. |
| web/vite.config.ts | Development proxy from /api to the loopback service. |
| src/portflow/local_data.py | Schema metadata, JSON normalization, validation, and transactional upserts. |
| src/portflow/local_api.py | Loopback HTTP server, request routing, response contracts, and safe error mapping. |
| scripts/run_local_api.py | Local API launcher using project environment variables. |
| tests/unit/test_local_data.py | Pure import schema and validation tests. |
| tests/unit/test_local_api.py | HTTP dispatch, origin, body-size, and error-contract tests without a live database. |
| tests/integration/test_local_data.py | PostgreSQL upsert, rollback, references, and idempotency tests. |
| tests/integration/test_local_api.py | Real loopback HTTP checks against PostgreSQL when Docker is available. |
| web/src/app/App.test.tsx | Route cold-click and filter/hash regression tests. |
| web/src/data/localApi.test.ts | Typed client request and error parsing tests. |
| web/src/features/health/LocalDataWorkspace.test.tsx | Workspace loading, unavailable, validation, success, and refresh states. |
| docs/runbooks/local-development.md | Complete database, API, import, refresh, and frontend startup workflow. |
| README.md | Link the local workspace workflow and clarify the static/public boundary. |
| .env.example | Document the local API port alongside the existing database URL. |
| docs/product/BACKLOG.md | Record PF-029 completion after the documented workflow and checks pass. |

---

### Task 1: Make route navigation deterministic and preserve filter routes (DYX-001)

**Goal:** A cold click on any existing menu destination renders its page without the route-level loading replacement, and global filters never remove the current hash route.

**Files:**
- Modify: web/src/app/App.tsx
- Modify: web/src/app/AppShell.tsx
- Test: web/src/app/App.test.tsx

**Interfaces:**
- Preserve App's existing loadData?: () => Promise<SnapshotV1> prop.
- Preserve AppShell's existing filter values and navigation labels.
- updateFilters(nextTerminal: string, nextRange: string) must write pathname, query string, and the current window.location.hash in that order.

- [ ] **Step 1: Write the failing cold-navigation test.**

Add a test that renders a ready snapshot, clicks the desktop Equipment link, and immediately asserts the page heading and absence of Loading selected view:

~~~
it("renders the selected page in the same navigation interaction", async () => {
  render(<App loadData={() => Promise.resolve(snapshot)} />);

  expect(await screen.findByText("Terminal throughput (moves)")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("link", { name: "Equipment" })[0]);

  expect(screen.getByRole("heading", { name: "Equipment fleet" })).toBeInTheDocument();
  expect(screen.queryByText("Loading selected view")).not.toBeInTheDocument();
});
~~~

- [ ] **Step 2: Run the focused test and verify the current lazy route fails.**

Run from the repository root:

~~~
Set-Location web
npx vitest run src/app/App.test.tsx -t "renders the selected page in the same navigation interaction"
~~~

Expected: FAIL because the current implementation still shows the route-level Suspense fallback during the first page-chunk import.

- [ ] **Step 3: Write the failing hash-preservation test.**

Add this regression test to web/src/app/App.test.tsx:

~~~
it("preserves the active route when global filters change", () => {
  window.history.replaceState({}, "", "/?terminal=TM-001#equipment");
  render(<App loadData={() => new Promise(() => undefined)} />);

  fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "7d" } });

  expect(window.location.search).toBe("?terminal=TM-001&range=7d");
  expect(window.location.hash).toBe("#equipment");
});
~~~

- [ ] **Step 4: Run the hash test and verify the current URL writer drops the hash.**

~~~
npx vitest run src/app/App.test.tsx -t "preserves the active route when global filters change"
~~~

Expected: FAIL because AppShell currently calls replaceState without window.location.hash.

- [ ] **Step 5: Replace route-level lazy imports with direct imports.**

In web/src/app/App.tsx, import EquipmentPage, IncidentPage, LiveDemoPage, DataHealthPage, and OverviewPage directly. Remove lazy and Suspense from the React import and remove the Loading selected view boundary. Keep snapshot loading asynchronous so Loading operational snapshot, stale-cache notices, and explicit error states continue to work.

- [ ] **Step 6: Preserve the hash in updateFilters.**

In web/src/app/AppShell.tsx, construct the URL with the existing pathname, optional query, and window.location.hash:

~~~
const hash = window.location.hash;
window.history.replaceState(
  {},
  "",
  window.location.pathname + (query ? "?" + query : "") + hash,
);
~~~

- [ ] **Step 7: Run the focused route and URL tests.**

~~~
npx vitest run src/app/App.test.tsx -t "selected page|active route|global filters"
~~~

Expected: PASS, with no Loading selected view element after the click and the active hash retained.

- [ ] **Step 8: Run the full frontend test file and commit.**

~~~
npx vitest run src/app/App.test.tsx
git add web/src/app/App.tsx web/src/app/AppShell.tsx web/src/app/App.test.tsx
git commit -m "fix: make route navigation deterministic"
~~~

Expected: all App tests pass and the commit contains only the navigation change.

---

### Task 2: Define and test the local import contract (DYX-002)

**Goal:** Convert JSON values into the types expected by the existing quality rules and produce row/field-specific validation issues for every supported source table.

**Files:**
- Create: src/portflow/local_data.py
- Create: tests/unit/test_local_data.py
- Read/Reuse: src/portflow/ingestion/postgres_to_bronze.py, src/portflow/quality/rules.py

**Interfaces:**

Implement these public types and functions in src/portflow/local_data.py:

~~~
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

ColumnKind = Literal["string", "integer", "number", "boolean", "date", "datetime"]

@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    kind: ColumnKind
    required: bool
    nullable: bool
    description: str

@dataclass(frozen=True, slots=True)
class TableSchema:
    table_name: str
    primary_key: str
    columns: tuple[ColumnSchema, ...]

@dataclass(frozen=True, slots=True)
class ImportIssue:
    row_index: int
    field: str | None
    code: str
    detail: str

@dataclass(frozen=True, slots=True)
class ImportReport:
    table_name: str
    received_count: int
    inserted_count: int
    updated_count: int

class UnsupportedTableError(ValueError):
    """Raised when a local import names a table outside TABLE_SPECS."""

class ImportValidationError(ValueError):
    """Raised when one or more imported records fail normalization or validation."""
    issues: tuple[ImportIssue, ...]

def get_local_schema() -> tuple[TableSchema, ...]:
    raise NotImplementedError
def normalize_records(
    table_name: str,
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    raise NotImplementedError
~~~

The implementation must derive table names, primary keys, and canonical column order from TABLE_SPECS. The schema metadata must describe these exact tables and fields:

- terminals: terminal_id string, name string, timezone_name string, created_at datetime, updated_at datetime.
- equipment: equipment_id string, terminal_id string, equipment_type string, commissioning_date date, created_at datetime, updated_at datetime.
- telemetry_events: event_id string, schema_version integer, equipment_id string, terminal_id string, event_timestamp datetime, ingestion_timestamp datetime, state string, available boolean, load_percent number, temperature_c number, created_at datetime, updated_at datetime.
- alarms: alarm_id string, equipment_id string, severity string, code string, opened_at datetime, cleared_at nullable datetime, created_at datetime, updated_at datetime.
- incidents: incident_id string, equipment_id string, severity string, status string, opened_at datetime, resolved_at nullable datetime, root_cause string, created_at datetime, updated_at datetime.
- maintenance_orders: maintenance_order_id string, equipment_id string, status string, started_at datetime, completed_at nullable datetime, created_at datetime, updated_at datetime.
- container_movements: movement_id string, terminal_id string, equipment_id string, movement_type string, container_ref string, event_timestamp datetime, created_at datetime, updated_at datetime.

All fields are required except the three nullable timestamp fields. A JSON timestamp ending in Z must become a UTC-aware datetime; a JSON date must become a date; booleans must not be accepted as numbers; and unknown fields must produce a SCHEMA_INVALID issue.

- [ ] **Step 1: Write unit tests for supported schemas and normalization.**

Create tests named test_exposes_all_operational_tables, test_normalizes_utc_datetime_and_date, and test_rejects_unknown_table_and_unknown_field. Assert that get_local_schema() contains seven tables in TABLE_SPECS order, "2026-09-02T00:00:00Z" becomes a UTC-aware datetime, and an unknown field is reported rather than silently discarded.

- [ ] **Step 2: Write unit tests for validation issues.**

Add tests named test_reports_row_and_field_for_bad_telemetry_range, test_reports_duplicate_primary_key_within_payload, test_reports_missing_required_field, and test_accepts_nullable_cleared_at. Use tests/unit/factories.py and ReferenceSet from portflow.quality.rules. Assert the stable reason codes from validate_row (SCHEMA_INVALID, RANGE_INVALID, REFERENCE_INVALID, TEMPORAL_INVALID, DUPLICATE_KEY) and the correct zero-based row index.

- [ ] **Step 3: Run the new unit tests before implementation.**

~~~
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_data.py -q
~~~

Expected: FAIL because local_data.py does not exist yet.

- [ ] **Step 4: Implement the schema registry and JSON normalizer.**

Use a literal ColumnSchema mapping for the seven tables, assert its field names equal TABLE_SPECS[table_name].columns at module load, parse ISO dates/timestamps with date.fromisoformat and datetime.fromisoformat, convert a trailing Z to +00:00, and raise ImportValidationError containing row/field issues for conversion failures.

- [ ] **Step 5: Implement validation over the existing quality rules.**

Normalize every record, reject missing and extra fields against the local schema, load ReferenceSet supplied by the caller, call validate_row for each record with a seen_keys set, and map each ValidationIssue to ImportIssue(row_index, field, code, detail). Use the primary key as the field for duplicate-key issues and None for cross-field temporal issues.

- [ ] **Step 6: Run the unit tests and commit the contract.**

~~~
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_data.py -q
.\\.venv\\Scripts\\python.exe -m ruff check src/portflow/local_data.py tests/unit/test_local_data.py
git add src/portflow/local_data.py tests/unit/test_local_data.py
git commit -m "feat: define local import contract"
~~~

Expected: all local-data unit tests and Ruff checks pass.

---

### Task 3: Add transactional PostgreSQL upserts (DYX-003)

**Goal:** Write validated records to the existing source tables with safe identifiers, foreign-key checks, primary-key upserts, and accurate inserted/updated counts.

**Files:**
- Modify: src/portflow/local_data.py
- Create: tests/integration/test_local_data.py
- Read/Reuse: src/portflow/db/connection.py, src/portflow/db/migrations.py, tests/integration/conftest.py

**Interfaces:**

Add these functions to src/portflow/local_data.py:

~~~
import psycopg
from portflow.quality.rules import ReferenceSet

def load_reference_set(connection: psycopg.Connection[object]) -> ReferenceSet:
    raise NotImplementedError

def import_records(
    connection: psycopg.Connection[object],
    *,
    table_name: str,
    records: Sequence[Mapping[str, object]],
) -> ImportReport:
    raise NotImplementedError
~~~

import_records must normalize and validate before opening the write transaction. It must query current terminal and equipment IDs, use psycopg.sql.Identifier only with names from TABLE_SPECS, use %s parameters for values, and generate an ON CONFLICT (primary_key) DO UPDATE statement that updates every non-primary-key column in canonical order. Before the upsert, query existing primary keys and use those keys to compute inserted_count and updated_count.

- [ ] **Step 1: Add integration fixtures for complete valid rows.**

In tests/integration/test_local_data.py, add constants for a terminal TM-101, equipment QC-101, and a valid incident inc-000101 with UTC timestamps and the schema's required fields. Keep the fixture timestamps ordered so it satisfies the current SQL checks and validate_row rules.

- [ ] **Step 2: Write the failing insert/update/rollback tests.**

Add these tests using the existing database_url and clean_database fixtures. The constants TERMINAL_ROW, EQUIPMENT_ROW, and INCIDENT_ROW are the complete rows defined in the preceding fixture step:

~~~
def test_import_inserts_then_updates_by_primary_key(database_url, clean_database):
    with get_connection(database_url) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
        first = import_records(connection, table_name="terminals", records=[TERMINAL_ROW])
        assert first.inserted_count == 1
        changed_terminal = {**TERMINAL_ROW, "name": "Updated local terminal"}
        second = import_records(
            connection,
            table_name="terminals",
            records=[changed_terminal],
        )
        assert second.updated_count == 1

def test_import_rejects_missing_foreign_reference_without_writing(database_url, clean_database):
    with get_connection(database_url) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
        with pytest.raises(ImportValidationError) as error:
            import_records(
                connection,
                table_name="equipment",
                records=[{**EQUIPMENT_ROW, "terminal_id": "TM-999"}],
            )
        assert error.value.issues[0].code == "REFERENCE_INVALID"

def test_import_rejects_an_invalid_batch_without_partial_write(database_url, clean_database):
    with get_connection(database_url) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
        import_records(connection, table_name="terminals", records=[TERMINAL_ROW])
        with pytest.raises(ImportValidationError):
            import_records(
                connection,
                table_name="equipment",
                records=[EQUIPMENT_ROW, {**EQUIPMENT_ROW, "equipment_id": "QC-102", "terminal_id": "TM-999"}],
            )
        with connection.cursor() as cursor:
            cursor.execute("select count(*) from equipment where equipment_id in (%s, %s)", ("QC-101", "QC-102"))
            assert cursor.fetchone()[0] == 0
~~~

The first asserts one insert followed by one update. The second asserts ImportValidationError with REFERENCE_INVALID before any dependent row is written. The third proves that a batch containing one valid and one invalid dependent row writes neither row.

- [ ] **Step 3: Run the integration tests before implementation.**

~~~
docker compose up -d --wait postgres
.\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_local_data.py -q
~~~

Expected: FAIL because import_records does not exist yet. If Docker Desktop is unavailable, record the exact engine error and continue with unit tests; do not substitute a fake database for these integration checks.

- [ ] **Step 4: Implement reference loading and safe upserts.**

Load reference identifiers with two fixed SELECT statements. Run validation before connection.transaction(). Inside one transaction, count existing primary keys, execute the generated parameterized upsert with executemany, and return an ImportReport. On every exception, let the transaction context roll back and re-raise the typed import/database error so the HTTP layer can map it.

- [ ] **Step 5: Run integration and static checks, then commit.**

~~~
.\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_local_data.py -q
.\\.venv\\Scripts\\python.exe -m ruff check src/portflow/local_data.py tests/integration/test_local_data.py
.\\.venv\\Scripts\\python.exe -m mypy src
git add src/portflow/local_data.py tests/integration/test_local_data.py
git commit -m "feat: add transactional local imports"
~~~

Expected: insert/update counts, reference rejection, rollback, Ruff, and mypy checks pass when PostgreSQL is running.

---

### Task 4: Expose the loopback-only local API (DYX-004)

**Goal:** Provide a small, testable HTTP boundary for status, schema, seed, import, and snapshot refresh without exposing credentials or database access to the browser.

**Files:**
- Create: src/portflow/local_api.py
- Create: scripts/run_local_api.py
- Create: tests/unit/test_local_api.py

**Interfaces:**

Define these public interfaces:

~~~
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

@dataclass(frozen=True, slots=True)
class LocalApiConfig:
    database_url: str
    output_dir: Path
    port: int = 8000
    max_body_bytes: int = 2_000_000
    allowed_origins: frozenset[str] = frozenset({
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    })

class LocalDataService(Protocol):
    def status(self) -> dict[str, object]:
        raise NotImplementedError
    def schema(self) -> dict[str, object]:
        raise NotImplementedError
    def seed(self) -> dict[str, object]:
        raise NotImplementedError
    def import_payload(self, payload: Mapping[str, object]) -> dict[str, object]:
        raise NotImplementedError
    def refresh(self) -> dict[str, object]:
        raise NotImplementedError

@dataclass(frozen=True, slots=True)
class LocalApiResponse:
    status: int
    body: Mapping[str, object]

def dispatch_request(
    service: LocalDataService,
    *,
    method: str,
    path: str,
    body: bytes = b"",
    origin: str | None = None,
    max_body_bytes: int = 2_000_000,
) -> LocalApiResponse:
    raise NotImplementedError

def create_server(config: LocalApiConfig, *, service: LocalDataService | None = None) -> ThreadingHTTPServer:
    raise NotImplementedError
~~~

PostgresLocalDataService implements the protocol. GET /api/status returns api, database, schema, and pipeline states without the database URL. GET /api/schema serializes get_local_schema(). POST /api/seed applies migrations and calls seed_operational(connection, seed=42). POST /api/import accepts exactly { "table": string, "records": object[] }. POST /api/refresh calls the existing run_local_pipeline with database_url and output_dir; a non-blocking lock returns 409 for a concurrent refresh. OPTIONS /api/* returns CORS headers only for the two configured local origins.

- [ ] **Step 1: Write a fake service and failing dispatch tests.**

In tests/unit/test_local_api.py, define a FakeLocalDataService with counters and fixed return values. Add tests named test_dispatches_status_and_schema, test_dispatches_seed_import_and_refresh, test_rejects_unknown_path_and_method, test_rejects_malformed_json, test_rejects_oversized_body, and test_rejects_non_local_origin. Assert exact status codes: 200 for valid GET/POST, 400 for malformed or wrong payloads, 404 for unknown paths, 405 for unsupported methods, 413 for oversized bodies, and 403 for a hosted origin.

- [ ] **Step 2: Run the API unit tests before implementation.**

~~~
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_api.py -q
~~~

Expected: FAIL because local_api.py does not exist yet.

- [ ] **Step 3: Implement typed JSON dispatch.**

Parse only UTF-8 JSON for POST requests, require a JSON object at the top level, route only the five documented paths, and serialize every response through json.dumps. Map ImportValidationError to 400 with { "error": "validation", "issues": [{ "row_index": 0, "field": "event_id", "code": "SCHEMA_INVALID", "detail": "event_id is invalid" }] }, database connection failures to 503 with { "error": "database_unavailable", "message": "Local database unavailable" }, and pipeline failures to 500 with { "error": "pipeline_failed", "message": "Snapshot refresh failed" }. Log the original exception server-side without returning its text.

- [ ] **Step 4: Implement the PostgreSQL service and loopback server.**

Use get_connection, apply_migrations, seed_operational, import_records, and run_local_pipeline. Track pipeline as idle, running, or failed under a threading.Lock. Build a BaseHTTPRequestHandler that delegates to dispatch_request, writes Content-Type: application/json, adds Access-Control-Allow-Origin only for accepted origins, and never binds beyond 127.0.0.1.

- [ ] **Step 5: Add the launcher.**

Create scripts/run_local_api.py with a main() that reads PORTFLOW_DATABASE_URL (defaulting to the existing localhost:5433 URL), reads PORTFLOW_LOCAL_API_PORT as an integer defaulting to 8000, sets output_dir to web/public/data, calls create_server, prints PortFlow local API listening on 127.0.0.1:<port>, and calls serve_forever() with clean KeyboardInterrupt shutdown.

- [ ] **Step 6: Run API tests and static checks, then commit.**

~~~
.\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_local_api.py -q
.\\.venv\\Scripts\\python.exe -m ruff check src/portflow/local_api.py scripts/run_local_api.py tests/unit/test_local_api.py
.\\.venv\\Scripts\\python.exe -m mypy src
git add src/portflow/local_api.py scripts/run_local_api.py tests/unit/test_local_api.py
git commit -m "feat: add loopback local data API"
~~~

Expected: all dispatch/security tests, Ruff, and mypy pass.

---

### Task 5: Add the Data Health local workspace UI (DYX-005)

**Goal:** Give the user a visible place to check the local connection, seed demo data, import JSON records, and refresh the snapshot without blocking the existing health metrics.

**Files:**
- Create: web/src/data/localApi.ts
- Create: web/src/data/localApi.test.ts
- Create: web/src/features/health/LocalDataWorkspace.tsx
- Create: web/src/features/health/LocalDataWorkspace.test.tsx
- Modify: web/src/features/health/DataHealthPage.tsx
- Modify: web/src/styles.css

**Interfaces:**

Export these client types and methods from web/src/data/localApi.ts:

~~~
export interface LocalStatus {
  api: "ready";
  database: "connected" | "unavailable";
  schema: "ready" | "missing";
  pipeline: "idle" | "running" | "failed";
  message?: string;
}

export interface LocalApiClient {
  getStatus(signal?: AbortSignal): Promise<LocalStatus>;
  getSchema(signal?: AbortSignal): Promise<LocalSchemaResponse>;
  seed(): Promise<SeedResponse>;
  importRecords(payload: ImportPayload): Promise<ImportResponse>;
  refresh(): Promise<RefreshResponse>;
}

export function createLocalApi(baseUrl?: string): LocalApiClient;
~~~

The default base URL is /api, allowing the Vite proxy to serve local development and causing a clear unavailable state on the public static deployment. LocalApiError must retain the HTTP status and parsed safe response body.

LocalDataWorkspace accepts api?: LocalApiClient and onSnapshotRefresh?: () => void props for tests. Its default refresh callback calls window.location.reload(). The UI must include a table selector, schema guidance, example JSON, a JSON textarea, a JSON file picker, Seed demo data, Validate and import, and Refresh snapshot controls. It must not run any API request that blocks the Data Health metrics from rendering.

- [ ] **Step 1: Write client tests for requests and errors.**

Use a deterministic fetcher function that records Request arguments and returns Response objects. Add tests named test_client_reads_status, test_client_posts_import_payload, and test_client_surfaces_safe_error_body. Assert /api/status is requested with GET, /api/import is requested with POST and Content-Type: application/json, and a 422/400 response becomes LocalApiError with its status and issues body.

- [ ] **Step 2: Run the client tests before implementation.**

~~~
Set-Location web
npx vitest run src/data/localApi.test.ts
~~~

Expected: FAIL because localApi.ts does not exist yet.

- [ ] **Step 3: Implement the typed API client.**

Create one request helper that prefixes the supplied base URL, sets JSON headers only when a body exists, parses JSON responses, throws LocalApiError for non-2xx responses, and forwards AbortSignal for status/schema checks. Keep response shapes aligned with the Python API contract.

- [ ] **Step 4: Write workspace state tests before the component.**

Use a fake LocalApiClient with explicit resolved/rejected promises. Add tests named test_shows_local_api_unavailable, test_shows_connected_actions, test_imports_json_and_reports_counts, test_shows_validation_issues, and test_refresh_calls_snapshot_callback. Assert accessible names Local database connected, Local API unavailable, Seed demo data, Validate and import, and Refresh snapshot; assert validation errors appear with role="alert" and busy operations with role="status".

- [ ] **Step 5: Run the workspace tests before implementation.**

~~~
npx vitest run src/features/health/LocalDataWorkspace.test.tsx
~~~

Expected: FAIL because the workspace component does not exist yet.

- [ ] **Step 6: Implement the workspace and compose it into Data Health.**

On mount, request status and then schema only if the API reports a connected/ready database. Render the four explicit states from the spec: checking, connected, unavailable, and operation error. Parse pasted or uploaded JSON as either an array of records or an object with a records array; send the selected table and records to importRecords. Keep the existing metrics and evidence before the workspace so status requests cannot replace them. After a successful refresh, call onSnapshotRefresh.

- [ ] **Step 7: Add styles using the existing design tokens.**

Add focused styles for .local-workspace, .local-workspace-editor, .local-workspace-actions, .local-workspace-status, .local-workspace-error, and .local-workspace-success in web/src/styles.css. Use existing border, muted text, accent, surface, and spacing variables; set button, select, file input, and textarea hit areas to at least 44px; ensure the editor stacks within the existing mobile breakpoint without changing the fixed bottom navigation.

- [ ] **Step 8: Run frontend tests, typecheck, and commit.**

~~~
npx vitest run src/data/localApi.test.ts src/features/health/LocalDataWorkspace.test.tsx src/features/health --maxWorkers=2
npm run typecheck
git add web/src/data/localApi.ts web/src/data/localApi.test.ts web/src/features/health/LocalDataWorkspace.tsx web/src/features/health/LocalDataWorkspace.test.tsx web/src/features/health/DataHealthPage.tsx web/src/styles.css
git commit -m "feat: add local data workspace"
~~~

Expected: client/workspace tests and TypeScript checks pass, with no changes to the approved navigation labels.

---

### Task 6: Wire development proxy and document the workflow (DYX-006)

**Goal:** Make the local API discoverable and runnable from a clean checkout while accurately explaining why the public static deployment cannot write to a database.

**Files:**
- Modify: web/vite.config.ts
- Modify: .env.example
- Modify: README.md
- Create: docs/runbooks/local-development.md

**Interfaces:**
- Vite development requests to /api/* proxy to http://127.0.0.1:8000.
- .env.example retains PORTFLOW_DATABASE_URL and adds PORTFLOW_LOCAL_API_PORT=8000.
- The runbook uses the existing Python package and scripts; it must not introduce a second package manager or a hosted service.

- [ ] **Step 1: Add the Vite proxy configuration.**

Add this server block to web/vite.config.ts without changing resolveBasePath or Vitest exclusions:

~~~
server: {
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8000",
      changeOrigin: false,
    },
  },
},
~~~

- [ ] **Step 2: Extend the environment example.**

Add PORTFLOW_LOCAL_API_PORT=8000 next to the existing database URL, leaving the existing Bronze/Silver/quarantine/Gold paths unchanged.

- [ ] **Step 3: Write the local-development runbook.**

Document these exact PowerShell commands and the two-terminal workflow:

~~~
Set-Location C:/Users/aliha/PortFlow
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
$env:PORTFLOW_DATABASE_URL = "postgresql://portflow:portflow@localhost:5433/portflow"
docker compose up -d --wait postgres
./.venv/Scripts/python.exe scripts/run_local_api.py
~~~

In a second terminal:

~~~
Set-Location C:/Users/aliha/PortFlow/web
npm install
npm run dev
~~~

Explain the sequence Data Health -> Seed demo data or Data Health -> select table -> paste JSON -> Validate and import -> Refresh snapshot, list the required full-row fields for timestamps and references, and include this valid incidents JSON example:

~~~json
[
  {
    "incident_id": "inc-000101",
    "equipment_id": "QC-001",
    "severity": "MAJOR",
    "status": "OPEN",
    "opened_at": "2026-09-02T12:00:00Z",
    "resolved_at": null,
    "root_cause": "Hydraulic leak",
    "created_at": "2026-09-02T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z"
  }
]
~~~

State that the hosted/static site intentionally shows Local API unavailable because it has no database connection.

- [ ] **Step 4: Update README and backlog.**

Add a short Local data workspace section in README.md linking to the runbook and restating that the public app reads versioned JSON only.

- [ ] **Step 5: Run configuration and documentation checks, then commit.**

~~~
Set-Location web
npm run typecheck
npm run build
Set-Location ..
git diff --check
git add web/vite.config.ts .env.example README.md docs/runbooks/local-development.md docs/product/BACKLOG.md
git commit -m "docs: document local data workflow"
~~~

Expected: Vite configuration typechecks, the production build succeeds, and the runbook contains no command that binds the API beyond localhost.

---

### Task 7: Verify the complete workflow and accessibility behavior (DYX-007)

**Goal:** Confirm the feature works through the real browser and database boundaries, while preserving the existing snapshot, accessibility, and build gates.

**Files:**
- Create: tests/integration/test_local_api.py
- Modify: docs/product/BACKLOG.md after the verification gates pass

**Interfaces:**
- Construct LocalApiConfig(database_url=database_url, output_dir=Path("web/public/data"), port=0), start create_server(config, service=service) on an ephemeral port in the integration test, and shut it down in a finally block.
- Use the public HTTP contracts rather than importing the service internals for the endpoint assertions.

- [ ] **Step 1: Write the real HTTP integration test.**

Start the API against the database_url fixture and use urllib.request to assert GET /api/status returns 200 with no database_url key, GET /api/schema returns seven tables, and POST /api/import for a valid terminal returns 200 with inserted_count == 1. Query PostgreSQL afterward to confirm the inserted ID exists.

- [ ] **Step 2: Run the API integration test with PostgreSQL.**

~~~
docker compose up -d --wait postgres
./.venv/Scripts/python.exe -m pytest tests/integration/test_local_api.py -q
~~~

Expected: PASS with Docker Desktop running. If the engine is unavailable, retain the exact failure in the handoff and run every non-DB gate below.

- [ ] **Step 3: Run the complete Python verification set.**

~~~
./.venv/Scripts/python.exe -m pytest tests/unit -q
./.venv/Scripts/python.exe -m pytest tests/integration -q
./.venv/Scripts/python.exe -m ruff check src tests scripts
./.venv/Scripts/python.exe -m mypy src
~~~

Expected: unit, integration, lint, and type checks pass when Docker is available; otherwise only the database-dependent integration command may fail with the known Docker engine error.

- [ ] **Step 4: Run the complete frontend verification set.**

~~~
Set-Location web
npm test -- --run --maxWorkers=2
npm run build
npm run verify:pages
~~~

Expected: all frontend tests pass, the bundle remains within the existing budgets, page verification passes, and the build contains the local workspace without changing the public snapshot contract.

- [ ] **Step 5: Verify the local preview in the chosen browser.**

Start the API and Vite dev server, then use the existing Edge browser session to check these states at desktop and mobile viewport sizes:

1. Click each of Overview, Equipment, Incidents, Live Demo, and Data Health from a cold page load; each page heading appears and no menu click leaves Loading selected view visible.
2. On Data Health, with the API stopped, Local API unavailable appears while the health metrics remain visible.
3. Start the API and database; Local database connected, Seed demo data, the table selector, JSON editor, and Refresh snapshot appear.
4. Import the documented incident example, confirm inserted/updated counts, refresh the snapshot, and confirm the existing snapshot view reloads.
5. Confirm all workspace controls and bottom navigation retain visible focus and a minimum 44px target without overlap.

- [ ] **Step 6: Run the final diff review and commit the integration test.**

~~~
Set-Location ..
git diff --check
git status --short
git add tests/integration/test_local_api.py docs/product/BACKLOG.md
git commit -m "test: verify local data workflow"
~~~

Before this commit, mark PF-029 complete in docs/product/BACKLOG.md with the local API, JSON import, snapshot refresh, and runbook as the delivered scope. Expected: the only uncommitted changes, if any, are unrelated user work; the feature diff contains no credentials, hosted-origin allowance, direct browser database connection, or new public route.

## Final Handoff

After Task 7, report the verified navigation behavior, the exact local startup commands, the JSON import workflow, and any database checks that could not run because Docker Desktop was unavailable. Do not call the feature complete until the verification commands and browser checks have produced the expected results.
