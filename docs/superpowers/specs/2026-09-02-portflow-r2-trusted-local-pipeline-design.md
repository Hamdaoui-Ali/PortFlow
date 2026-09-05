# PortFlow R2 Trusted Local Pipeline Design

Date: 2026-09-02  
Status: Accepted  
Preserves: docs/adr/0001-static-public-product.md and docs/adr/0002-snapshot-contract.md

## Goal

Make the first PortFlow KPI reproducible through a real local PostgreSQL source and a
failure-aware analytical pipeline, while keeping the public application static,
serverless, and permanently within the documented $0 boundary.

R2 produces trusted local data artifacts. It does not add public accounts, public
writes, a public database, a runtime API, or a continuously running service.

## User-visible outcome

After R2, a contributor can:

1. start one local PostgreSQL service;
2. apply migrations safely more than once;
3. seed the same connected terminal fixture repeatedly without duplicates;
4. extract source rows incrementally into immutable Bronze Parquet;
5. validate, normalize, deduplicate, and quarantine invalid rows in Silver;
6. run DuckDB and dbt Gold models with documented KPI formulas;
7. export a versioned, hashed, browser-sized snapshot;
8. repeat the complete command and receive identical logical data and hashes.

The existing public page continues to consume only public/data/manifest.json and
its versioned datasets. R2 changes the producer behind that boundary, not the
frontend interface.

## Options considered

### A. DuckDB-only source

This would be the smallest local setup, but it would not demonstrate extraction
from a realistic OLTP source. It is rejected for R2.

### B. Full production-style platform

This would add streaming, orchestration, observability, object storage, or cloud
services before the local contract is trusted. It increases cost and failure
surface without improving the first public product. It is deferred.

### C. Thin real stack — selected

Use PostgreSQL only as a local/CI source, raw SQL for the small operational access
layer, Parquet for immutable data files, Polars for typed row validation, DuckDB
for local analytical SQL, and dbt Core with the DuckDB adapter for documented
Gold lineage. This satisfies the study's source-to-export requirement while
keeping every runtime dependency local or free CI infrastructure.

## Architecture and data flow

    deterministic simulator
            |
            v
    PostgreSQL operational source
            |
            |  composite (updated_at, primary_key) cursor
            v
    Bronze Parquet: immutable staged partitions
            |
            |  schema, range, reference, temporal, duplicate checks
            +------------------------------+
            v                              v
    Silver Parquet: accepted rows     quarantine Parquet: raw row + reason
            |
            v
    DuckDB + dbt Core Gold models
            |
            |  JSON Schema + reconciliation + SHA-256
            v
    versioned public snapshot + manifest
            |
            v
    existing React/Vite static application

The browser never connects to PostgreSQL, Parquet, DuckDB, or dbt. The public
deployment contains only static files.

## Technology and runtime decisions

- Python execution is standardized on Python 3.12 in CI and documented local
  commands. The project may continue to support newer Python versions when all
  locked packages support them.
- PostgreSQL uses the postgres:16-alpine image in compose.yaml. It is a local
  development and CI dependency, never a public production service.
- The database layer uses psycopg 3 and parameterized SQL. An ORM is not added
  to this slice.
- Parquet writing and typed dataframe operations use Polars and PyArrow.
- Gold SQL runs in DuckDB through dbt Core with the dbt-duckdb adapter.
- uv.lock and web/package-lock.json remain authoritative dependency locks.
- CI uses a standard GitHub-hosted runner and a PostgreSQL service/container; no
  paid runner, secret, card, or external database is required.

## Operational source contract

The migration creates a schema_migrations table and these connected tables:

- terminals: terminal_id, name, UTC-compatible timezone label, created_at,
  updated_at;
- equipment: equipment_id, terminal_id, equipment type, commissioning date,
  created_at, updated_at;
- telemetry_events: the existing typed event fields plus updated_at;
- alarms: alarm_id, equipment_id, severity, code, opened/cleared timestamps,
  created_at, updated_at;
- incidents: incident_id, equipment_id, severity, status, opened/resolved
  timestamps, root cause, created_at, updated_at;
- maintenance_orders: maintenance_order_id, equipment_id, status,
  started/completed timestamps, created_at, updated_at;
- container_movements: movement_id, terminal_id, equipment identifier,
  movement type, container reference, event timestamp, created_at, updated_at.

All primary identifiers are stable text identifiers matching the domain contract.
Foreign keys protect terminal/equipment relationships. Check constraints protect
enumerated values, timestamp ordering, non-negative numeric fields, and UTC
offsets. Every extractable table has an index on (updated_at, primary_key).

The migration runner records applied filenames and refuses checksum changes to an
already applied migration. Re-running the same migration is a no-op. A failed
migration stops before later migrations run.

## Deterministic seed contract

src/portflow/seed.py exposes a deterministic seed function that accepts a
database connection and seed value. It derives stable rows from the existing
simulator seed and inserts connected records using INSERT ... ON CONFLICT
DO UPDATE with the same values. It never uses wall-clock timestamps or random
UUIDs.

The fixture includes at least one terminal, one equipment asset, telemetry,
alarms, incidents, maintenance, and movements. Seed output is checked by stable
row counts and a canonical digest of selected source columns. Running the seed
twice produces the same digest and no duplicate identifiers.

## Bronze extraction contract

src/portflow/ingestion/cursor.py owns a typed cursor:

    Cursor = tuple[datetime, str]

src/portflow/ingestion/postgres_to_bronze.py queries each table with:

    WHERE (updated_at, primary_key) > (%s, %s)
    ORDER BY updated_at, primary_key
    LIMIT %s

Each row is written with source metadata: table name, extraction run ID, source
updated timestamp, and extraction timestamp. A batch is first written to a
temporary file, flushed, and validated. The completed file is then moved to its
deterministic immutable partition path. Only after that commit is the cursor
advanced.

The partition identity is derived from table name and the final (updated_at,
primary_key) cursor. If a retry finds the same committed partition, it verifies
the content hash and reuses it. A failure before commit leaves the cursor
unchanged and no temporary file is considered Bronze data. Reading Bronze
deduplicates by the stable source primary key and latest cursor position, so a
retry cannot create logical duplicates.

## Silver validation and quarantine contract

Silver validation is explicit and machine-readable. Stable reason codes are:

- SCHEMA_INVALID
- RANGE_INVALID
- REFERENCE_INVALID
- TEMPORAL_INVALID
- DUPLICATE_KEY

Each Bronze row produces either one normalized Silver row or one quarantine row
containing the raw source payload, table name, stable primary identifier,
reason code, and human-readable detail. A row with multiple failures uses a
deterministically ordered list of reason codes.

Silver applies domain types, normalizes UTC timestamps, checks foreign-key
references against the same validated run, and removes duplicate business
identifiers deterministically. It never silently drops a row. The run report
must reconcile:

    Bronze input rows = Silver accepted rows + quarantined rows

## Gold and KPI contract

dbt reads Silver Parquet through DuckDB and materializes documented Gold models
for equipment, alarms, incidents, maintenance, movements, and telemetry. Model
documentation declares grain, keys, source columns, and freshness assumptions.

The first Gold KPI set is:

- throughput: completed container movements in the selected period;
- average dwell time: mean elapsed time for completed qualifying stays;
- availability: available time divided by scheduled time;
- utilization: active operating time divided by available time;
- MTTR: resolved-incident repair duration divided by resolved incidents;
- MTBF: operating time divided by qualifying failures;
- active incidents: incidents open at period end;
- critical alarms: critical alarms in the selected period.

Each formula has a hand-calculated fixture covering a normal case, an empty
denominator, and a boundary timestamp. The zero-denominator result is null,
never zero. Gold outputs include the source period and row counts needed for
export reconciliation.

## Public export contract

PF-013 extends the existing exporter without breaking demo-v1. It writes:

    public/data/
      manifest.json
      snapshots/<snapshot_id>/
        overview.json
        equipment.json
        incidents.json
        event-replay.json
        quality.json

schemas/public-snapshot-v1.json defines the manifest and dataset shapes. Every
dataset is serialized as canonical UTF-8 JSON with sorted keys, compact
separators, and a terminal newline. The manifest records schema version,
immutable snapshot ID, UTC generation/source-period timestamps, quality status,
record counts, relative paths, and lowercase SHA-256 hashes.

Before a snapshot can be published, the exporter verifies JSON Schema, hashes,
record counts, KPI values against Gold, cross-dataset identifiers, and the
documented browser-size budget. A failed check returns non-zero and leaves the
previous committed public snapshot untouched.

## Failure, replay, and cost boundaries

- No cursor advances after a failed Bronze write.
- No invalid or unreconciled row reaches Gold.
- No invalid or oversized snapshot reaches public/data.
- A failed CI or Pages build cannot replace the last valid deployment.
- The R1 deterministic fixture command remains available for fast frontend tests;
  the R2 end-to-end command additionally proves the PostgreSQL-to-export path.
- Docker data is local and disposable. CI uses an ephemeral service. No
  production database or user data is introduced.
- The product remains static and usable with the developer machine off.

## Test and acceptance strategy

### Unit tests

Test migration checksum handling, cursor ordering, equal-timestamp ties,
canonical serialization, each validation reason code, deduplication, and every
KPI formula.

### Integration tests

Run PostgreSQL migrations, seed the fixture, extract Bronze, validate Silver,
run dbt Gold, and export the public snapshot. Assert foreign keys and check
constraints reject invalid rows. Assert Bronze/Silver/quarantine reconciliation
and Gold/export reconciliation.

### Idempotency tests

Run seed twice and the complete pipeline twice in clean temporary output
directories. Require equal source digests, partition content hashes, Gold
values, record counts, and public export hashes.

### CI gate

The CI workflow starts PostgreSQL, installs locked Python and Node dependencies,
runs the complete R2 pipeline, checks that generated public data produces no Git
diff, runs Python and frontend quality checks, and builds the Pages artifact.

## Delivery slices

1. PF-008: migration table, operational schema, connection helper, Compose
   service, and constraint tests.
2. PF-009: deterministic seed command and idempotency tests.
3. PF-010: typed cursor, atomic Bronze writer, retry semantics, and
   PostgreSQL-to-Bronze integration test.
4. PF-011: Silver validators, quarantine output, deduplication, and layer
   reconciliation.
5. PF-012: DuckDB/dbt project, Gold models, KPI catalog, and fixture tests.
6. PF-013: public JSON Schema, complete datasets, hashes, size checks, and
   Gold-to-export integration test.
7. R2 release gate: clean Compose run, deterministic rerun, full verification,
   and an updated evidence record.

Every slice ends in a focused commit. R3 frontend work starts only after the R2
release gate passes.
