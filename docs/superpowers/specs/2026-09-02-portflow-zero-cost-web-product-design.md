# PortFlow: Permanent-$0 Web Product Design

**Date:** 2026-09-02

**Status:** Approved in conversation

**Source study:** `PORTFLOW_FULL_VERIFIED_BRAINSTORMING.md`

## 1. Goal

Build a functional, publicly accessible PortFlow product that can remain online with no cloud bill, payment card, or continuously running developer machine.

PortFlow has two complementary surfaces:

1. A public operations control tower hosted as a static site.
2. A reproducible local data platform that generates and validates the site's analytical snapshots.

The public product is periodically refreshed. It does not claim to have a permanently running public streaming backend.

## 2. Product promise

A visitor can open PortFlow without signing in and explore a realistic container-terminal operation through trusted KPIs, equipment and incident drill-downs, data-health evidence, and a browser-side replay of historical events.

The replay is always labelled as simulated historical data. PortFlow never presents generated or replayed events as live terminal data.

## 3. Cost boundary

"$0" means zero required software subscription and zero required cloud spend. It excludes the developer's existing hardware, electricity, and internet connection.

The permanent product requires:

- GitHub Free for a public repository;
- GitHub Pages for static hosting;
- standard GitHub-hosted Actions for a public repository;
- free and open-source local development tools.

No billing account or payment card is part of the core architecture. Vendor quotas and terms must be rechecked before implementation and documented with a verification date.

## 4. V1 scope

### 4.1 Public product

V1 provides:

- a responsive Operations Overview;
- terminal, date-range, severity, and equipment filters;
- terminal throughput and container dwell-time KPIs;
- equipment availability, utilization, MTTR, and MTBF KPIs;
- incident and alarm trends;
- equipment and incident drill-downs;
- data freshness and quality status;
- a start, pause, resume, reset, and speed-controlled event replay;
- accessible chart summaries and keyboard navigation.

### 4.2 Local data product

V1 provides:

- a PostgreSQL operational source;
- deterministic seed data and a stateful terminal simulator;
- incremental Python extraction;
- immutable Bronze Parquet datasets;
- validated and deduplicated Silver datasets;
- DuckDB and dbt Gold models;
- compact browser-oriented JSON exports;
- automated data, pipeline, and frontend tests;
- automated GitHub Pages publication;
- one documented command to reproduce the published snapshot locally.

### 4.3 Explicitly deferred

The following are not V1 dependencies:

- public APIs, authentication, or user-generated data;
- public PostgreSQL, DuckDB, Kafka, or Redpanda services;
- genuine public live streaming;
- Dagster, Prometheus, and Grafana;
- PySpark and large-scale benchmarks;
- Terraform and billable GCP infrastructure;
- BigQuery, Databricks, Fabric, and Snowflake labs;
- MinIO or another object-storage emulator;
- multiple orchestration, streaming, BI, or cloud technologies.

Deferred capabilities may be added only after V1 acceptance criteria pass.

## 5. Architecture

```text
PostgreSQL operational source
            |
Deterministic stateful simulator
            |
Python incremental extraction
            |
Bronze Parquet
            |
Silver validation, normalization, quarantine, deduplication
            |
DuckDB + dbt Gold models and tests
            |
Versioned JSON snapshot + manifest
            |
React + TypeScript + Vite control tower
            |
GitHub Pages
```

### 5.1 Technology decisions

| Concern | V1 choice | Reason |
|---|---|---|
| Public hosting | GitHub Pages | Static, public, and no always-on server |
| Frontend | React + TypeScript + Vite | Typed, testable, and deployable as static assets |
| Charts | Apache ECharts | Rich interactive charts with no hosted service |
| Operational source | PostgreSQL | Realistic OLTP source and established project requirement |
| Extraction | Python + Polars | Small operational footprint and efficient local processing |
| Lake files | Parquet | Compact analytical format with broad tooling support |
| Local analytics | DuckDB | Serverless analytical SQL over Parquet |
| Modeling | dbt Core with DuckDB | Explicit lineage, tests, and SQL-centered transformations |
| Browser data | Versioned JSON | Simple, cacheable, inspectable, and mobile-friendly |
| Automation | GitHub Actions | Test, build, and publish from one workflow |

### 5.2 Component boundaries

- The simulator owns domain behavior and produces deterministic operational records.
- The extractor owns incremental cursors and Bronze writes.
- Silver owns validation, normalization, deduplication, and quarantine.
- Gold owns business definitions and published KPI calculations.
- The exporter owns the public snapshot schema and size budget.
- The frontend consumes only the versioned public snapshot contract.
- The deployment workflow publishes only after all quality gates pass.

The frontend never connects directly to PostgreSQL or DuckDB. A future streaming pipeline must write into the same Bronze contracts so that Gold models and the frontend contract do not need to change.

## 6. Public data contract

Every deployment contains an immutable versioned snapshot directory and a small current manifest.

```text
public/data/
  manifest.json
  snapshots/<snapshot_id>/
    overview.json
    equipment.json
    incidents.json
    event-replay.json
    quality.json
```

The manifest contains at least:

- `schema_version`;
- `snapshot_id`;
- `generated_at` in UTC;
- `source_period_start` and `source_period_end` in UTC;
- record counts;
- quality status;
- relative dataset paths;
- content hashes.

The application validates the manifest and each dataset before use. Breaking schema changes require a new schema version and an explicit frontend migration.

## 7. User experience

### 7.1 Operations Overview

Show throughput, dwell time, availability, MTTR, MTBF, active incidents, and critical alarms. Global terminal and date filters update every compatible panel. Every KPI exposes its definition.

### 7.2 Equipment

Provide a searchable, sortable equipment list containing status, utilization, alarms, downtime, and reliability. Selecting equipment opens its metric history and related incidents.

### 7.3 Incidents

Provide severity and terminal filters, incident trends, recurring faults, recovery duration, root-cause distribution, and an incident lifecycle view.

### 7.4 Live Demo

Replay timestamped historical events in the browser. Controls include start, pause, resume, reset, and replay speed. KPI cards and an activity feed update deterministically. The page visibly states that this is a simulation replay.

### 7.5 Data Health

Show the snapshot timestamp, snapshot age, last successful pipeline run, record counts, rejected records, data-test results, and quality thresholds. Link to the project's methodology and source repository.

## 8. Domain slice

V1 uses the smallest connected domain that supports the approved experience:

- terminals;
- equipment;
- equipment telemetry;
- alarms;
- incidents;
- maintenance activity;
- container movements.

Vessels, voyages, customers, shipments, weather, and external REST sources are deferred unless a required V1 KPI cannot be demonstrated without them.

V1 may include more than one terminal only when necessary to demonstrate the global terminal filter. Data breadth must not delay a complete vertical slice.

## 9. Data correctness

The pipeline must preserve raw input in Bronze and prevent invalid records from reaching Gold.

Required controls include:

- stable event and business identifiers;
- composite incremental cursor `(updated_at, primary_key)`;
- watermark advancement only after a committed successful write;
- deterministic reruns;
- Silver deduplication;
- quarantine with machine-readable rejection reasons;
- referential-integrity and temporal checks;
- reconciliation from source to Bronze, Silver, Gold, and export;
- event time and ingestion time stored separately;
- documented KPI formulas and grains.

Reliability is built into each vertical slice. It is not postponed to a later reliability phase.

## 10. Failure handling

### 10.1 Pipeline and deployment

- Failed validation prevents snapshot publication.
- Watermarks remain unchanged after a failed write.
- Temporary files are not treated as committed partitions.
- A failed deployment leaves the last valid site and snapshot available.
- CI reports the failed stage and preserves useful test output.

### 10.2 Public application

- Loading, empty, malformed, unavailable, and stale states are distinct.
- The last valid loaded snapshot remains visible if a later request fails.
- Failure of one optional dataset does not blank unrelated views.
- Missing metrics display as unavailable; the UI never substitutes invented values.
- Stale data is clearly labelled using the manifest timestamp.

## 11. Accessibility and responsiveness

V1 must provide:

- complete keyboard navigation;
- visible focus states;
- semantic headings and landmarks;
- sufficient color contrast;
- text equivalents for chart conclusions;
- status communication that does not rely on color alone;
- reduced-motion behavior for event replay;
- usable layouts at narrow mobile widths;
- concise labels, consistent navigation, and progressive disclosure.

## 12. Testing strategy

### 12.1 Unit tests

Test simulator state transitions, validators, cursor calculations, deduplication, KPI formulas, exporters, frontend selectors, and replay state.

### 12.2 Data tests

Test uniqueness, accepted values, referential integrity, nullability, temporal constraints, metric ranges, fact grain, and source-to-export reconciliation.

### 12.3 Integration tests

Test PostgreSQL to Bronze, Bronze to Silver, Silver to Gold, Gold to public JSON, and manifest-to-frontend loading.

### 12.4 End-to-end tests

Build a deterministic small dataset, publish it to a preview build, and verify navigation, filters, drill-downs, replay controls, accessibility-critical paths, and error states.

### 12.5 Idempotency test

Run the same pipeline input twice and assert identical Gold values, export hashes, and record counts.

## 13. Deployment workflow

For each change:

1. Lint and type-check Python, SQL, and TypeScript.
2. Run unit tests.
3. Generate a deterministic small dataset.
4. Run dbt and data-quality tests.
5. Export and validate the public snapshot.
6. Build and test the frontend.
7. Run end-to-end and accessibility checks.
8. Publish to GitHub Pages only from the protected main branch.

Scheduled snapshot regeneration is optional. The site remains valid and available with its last successfully published snapshot.

## 14. V1 acceptance criteria

V1 is accepted only when:

- the public URL loads without authentication or a running developer machine;
- the four product areas work on desktop and mobile;
- global filters and drill-downs produce correct results;
- replay controls work without a backend;
- the replay is clearly labelled as simulated;
- published KPIs reconcile with Gold data;
- snapshot freshness and quality status are visible;
- invalid source records are quarantined and excluded from Gold;
- rerunning identical input does not change results;
- failed validation cannot replace the last good deployment;
- keyboard navigation and accessible chart summaries pass review;
- a clean clone can reproduce the published snapshot using documented commands;
- no required step requests a billing account or payment card.

## 15. Delivery strategy

Work proceeds as thin vertical slices:

1. One terminal, one equipment type, one KPI, and one rendered page.
2. Complete deterministic data generation and source-to-page reconciliation.
3. Add the connected equipment, incident, and movement domain.
4. Add filters, drill-downs, event replay, and Data Health.
5. Harden reliability, accessibility, CI, documentation, and deployment.

The first deployable slice comes before streaming, orchestration, observability infrastructure, cloud labs, or benchmark work.

## 16. Post-V1 extensions

Recommended order after V1 acceptance:

1. Redpanda-based local streaming into the established Bronze contract.
2. Dagster orchestration and operational metadata.
3. Prometheus and Grafana engineering observability.
4. Larger data and DuckDB/Polars/PySpark benchmarks.
5. BigQuery Sandbox analytical portability lab.
6. Databricks Free Edition Delta/PySpark lab.
7. Optional cloud trials only when they answer a specific learning question.

Every extension must preserve the static public product and must remain removable without breaking V1.

## 17. Decisions replacing the source study

This design supersedes the source study where they conflict:

- Web accessibility is a V1 requirement.
- GitHub Pages, not Metabase, is the public product surface.
- Metabase, Grafana, and Dagster are post-V1 local extensions.
- PostgreSQL Gold serving tables are unnecessary for the static public site.
- Redpanda streaming is post-V1 rather than a prerequisite.
- Reliability is implemented with each pipeline slice rather than in a late phase.
- Cloud labs and large-scale benchmarking are excluded from the functional-product backlog.
- The roadmap is outcome-driven rather than organized around technologies.
