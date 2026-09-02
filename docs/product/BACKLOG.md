# PortFlow V1 Backlog

**Backlog goal:** Ship the approved public, permanent-$0 PortFlow product.

**Ordering rule:** Work from top to bottom. A task starts only when all listed dependencies are complete.

**Priority meanings:** `P0` blocks the first public release. `P1` is required for V1 acceptance. `P2` is post-V1.

## Release map

| Release | Outcome | Included tasks |
|---|---|---|
| R0 | Verified constraints | PF-001–PF-002 |
| R1 | First public vertical slice | PF-003–PF-007 |
| R2 | Trusted local pipeline | PF-008–PF-013 |
| R3 | Usable operations product | PF-014–PF-017 |
| R4 | Exploration and replay | PF-018–PF-021 |
| R5 | Product hardening | PF-022–PF-026 |
| R6 | Reproducible public V1 | PF-027–PF-030 |

## Current next action

Start **PF-014**. R2 is complete; the next release adds the first operator workflow on top of the trusted static snapshot.

## Completed checkpoints

- **R1 first public slice:** `9423cbb`, `f2ba319`, `e004d02`, `3ceaef0`, and `e53641a`, with the approved design and plan in `docs/superpowers/`.
- **R2 trusted local pipeline:** `8deb3b4`, `ab35b6a`, `e290238`, `0572fc0`, `16c9e69`, and `f6c7226` (with dbt artifact hygiene in `d625750`).

## R0 — Verified constraints

### Task PF-001 — Create the cost evidence ledger

**Priority:** P0

**Dependencies:** None

**Goal:** Establish evidence for every external service required by V1.

**Files:** `docs/product/cost-evidence.md`

**Action:** Record the official GitHub Free, Pages, and Actions documentation URL, verification date, relevant limit, billing requirement, risk, and fallback.

**Why:** The product must not claim permanent $0 from outdated quota assumptions.

**Verification:** Every required external service has a dated official source and fallback; no cloud billing account is required.

**Expected result:** A reviewer can independently validate the $0 claim.

### Task PF-002 — Freeze V1 scope and architecture records

**Priority:** P0

**Dependencies:** PF-001

**Goal:** Prevent deferred technologies from re-entering V1.

**Files:** `docs/adr/0001-static-public-product.md`, `docs/adr/0002-local-analytical-pipeline.md`, `README.md`

**Action:** Document the static-site boundary, snapshot contract, local pipeline, and explicit exclusions.

**Why:** Scope control is necessary to reach a working product.

**Verification:** The README and ADRs match the approved design and contain no public backend dependency.

**Expected result:** Contributors share one unambiguous V1 architecture.

## R1 — First public vertical slice

### Task PF-003 — Establish the tested project foundation

**Priority:** P0

**Dependencies:** PF-002

**Goal:** Create one repository with independently testable Python and web workspaces.

**Files:** `pyproject.toml`, `src/portflow/`, `tests/`, `web/`, `Makefile`, `.gitignore`, `.env.example`

**Action:** Configure Python, TypeScript, linting, unit tests, deterministic test settings, and developer commands.

**Why:** Every later task needs repeatable commands and boundaries.

**Verification:** Python and frontend smoke tests pass from a clean checkout.

**Expected result:** `make test` runs both test suites successfully.

### Task PF-004 — Define the first domain contract

**Priority:** P0

**Dependencies:** PF-003

**Goal:** Define terminal, equipment, and telemetry records used by the first slice.

**Files:** `src/portflow/domain/models.py`, `src/portflow/contracts/telemetry.py`, `tests/unit/test_telemetry_contract.py`

**Action:** Add typed models, UTC timestamp rules, stable identifiers, and telemetry range validation.

**Why:** Producers, transformations, and UI exports need one shared meaning.

**Verification:** Valid fixtures pass; invalid identifiers, timestamps, and metric ranges fail with reason codes.

**Expected result:** A versioned telemetry contract exists and is tested.

### Task PF-005 — Generate deterministic telemetry

**Priority:** P0

**Dependencies:** PF-004

**Goal:** Produce realistic repeatable equipment events.

**Files:** `src/portflow/simulator/equipment.py`, `tests/unit/test_equipment_simulator.py`

**Action:** Implement seeded equipment state transitions and correlated load and temperature values.

**Why:** Stable fixtures make analytics, screenshots, and tests reproducible.

**Verification:** The same seed produces the same event sequence and event identifiers.

**Expected result:** One command generates the first trusted dataset.

### Task PF-006 — Build one Gold KPI snapshot

**Priority:** P0

**Dependencies:** PF-005

**Goal:** Convert generated telemetry into one tested equipment-availability KPI.

**Files:** `src/portflow/analytics/availability.py`, `src/portflow/export/snapshot.py`, `tests/unit/test_availability.py`, `tests/integration/test_first_snapshot.py`

**Action:** Calculate availability from fixtures and export a schema-versioned `overview.json` plus `manifest.json`.

**Why:** This proves the source-to-browser contract before broadening the platform.

**Verification:** Fixture calculations and snapshot schema pass; identical inputs produce identical content hashes.

**Expected result:** A deterministic public snapshot exists.

### Task PF-007 — Render and deploy the first page

**Priority:** P0

**Dependencies:** PF-006

**Goal:** Make the first KPI publicly viewable.

**Files:** `web/src/app/App.tsx`, `web/src/data/snapshot.ts`, `web/src/features/overview/AvailabilityCard.tsx`, `web/src/**/*.test.tsx`, `.github/workflows/pages.yml`

**Action:** Load and validate the snapshot, render the KPI with timestamp and definition, then publish a static build.

**Why:** The first public deployment validates the core delivery strategy early.

**Verification:** Component and browser tests pass; the deployed URL works with the developer machine off.

**Expected result:** PortFlow has its first functional public vertical slice.

## R2 — Trusted local pipeline

### Task PF-008 — Create the operational PostgreSQL schema

**Priority:** P0

**Dependencies:** PF-005

**Goal:** Persist terminal, equipment, telemetry, alarm, incident, maintenance, and movement records.

**Files:** `db/migrations/001_operational_schema.sql`, `src/portflow/db/`, `tests/integration/test_operational_schema.py`, `compose.yaml`

**Action:** Add constrained tables, indexes for composite extraction cursors, and a containerized test database.

**Why:** V1 must demonstrate extraction from a real OLTP source.

**Verification:** Migrations run twice safely and constraints reject invalid fixture rows.

**Expected result:** A reproducible operational database is available locally and in CI.

### Task PF-009 — Seed the operational database

**Priority:** P0

**Dependencies:** PF-008

**Goal:** Load deterministic connected domain fixtures.

**Files:** `src/portflow/seed.py`, `tests/integration/test_seed.py`

**Action:** Insert repeatable terminal, equipment, event, alarm, incident, maintenance, and movement data using stable identifiers.

**Why:** Every pipeline and UI test needs known connected records.

**Verification:** Repeated seed runs produce the same logical state without duplicates.

**Expected result:** `make seed` creates a known source dataset.

### Task PF-010 — Implement incremental Bronze extraction

**Priority:** P0

**Dependencies:** PF-009

**Goal:** Extract new or changed source rows safely into immutable Parquet partitions.

**Files:** `src/portflow/ingestion/cursor.py`, `src/portflow/ingestion/postgres_to_bronze.py`, `tests/unit/test_cursor.py`, `tests/integration/test_bronze_extraction.py`

**Action:** Query using `(updated_at, primary_key)`, write a staged partition, commit it, and only then advance the watermark.

**Why:** Timestamp-only extraction can skip ties and premature watermark updates can lose data.

**Verification:** Equal timestamps are handled, failed writes preserve the old watermark, and repeated runs add no logical duplicates.

**Expected result:** Incremental Bronze data is complete and replayable.

### Task PF-011 — Build Silver validation and quarantine

**Priority:** P0

**Dependencies:** PF-010

**Goal:** Produce clean typed datasets while preserving invalid records with reasons.

**Files:** `src/portflow/quality/rules.py`, `src/portflow/transforms/silver.py`, `tests/unit/test_quality_rules.py`, `tests/integration/test_silver.py`

**Action:** Validate schema, ranges, references, timestamps, and duplicates; route failures to quarantine.

**Why:** Invalid data must not silently enter business metrics.

**Verification:** Controlled bad fixtures receive stable reason codes and do not appear in Silver.

**Expected result:** Silver and quarantine totals reconcile with Bronze.

### Task PF-012 — Build dbt Gold models and KPI tests

**Priority:** P0

**Dependencies:** PF-011

**Goal:** Create documented facts, dimensions, and approved KPI calculations.

**Files:** `analytics/dbt_project.yml`, `analytics/models/`, `analytics/tests/`, `tests/fixtures/kpi_cases/`

**Action:** Model equipment, incidents, alarms, and movements; calculate throughput, dwell time, availability, utilization, MTTR, and MTBF.

**Why:** Business semantics must live in tested analytical models rather than UI code.

**Verification:** dbt tests pass and every KPI matches its hand-calculated fixture.

**Expected result:** Trusted Gold models support the complete V1 interface.

### Task PF-013 — Export the complete public snapshot

**Priority:** P0

**Dependencies:** PF-012

**Goal:** Publish browser-sized versioned datasets from Gold.

**Files:** `src/portflow/export/models.py`, `src/portflow/export/writer.py`, `schemas/public-snapshot-v1.json`, `tests/integration/test_public_export.py`

**Action:** Export overview, equipment, incidents, replay, and quality datasets with counts, hashes, and UTC period metadata.

**Why:** The snapshot is the stable boundary between the data platform and web product.

**Verification:** JSON Schema validation, hash verification, size budgets, and Gold-to-export reconciliation pass.

**Expected result:** The full public data contract is safe to deploy.

## R3 — Usable operations product

### Task PF-014 — Implement the application shell and navigation

**Priority:** P0

**Dependencies:** PF-007

**Goal:** Provide stable navigation and global filter state.

**Files:** `web/src/app/`, `web/src/components/layout/`, `web/src/state/filters.ts`, `web/src/styles/`

**Action:** Create responsive navigation, page routing, terminal/date filters, skip link, and visible focus behavior.

**Why:** All views require a consistent accessible frame.

**Verification:** Navigation and filters work by keyboard at desktop and mobile widths.

**Expected result:** Users can move through a coherent product shell.

### Task PF-015 — Complete Operations Overview

**Priority:** P0

**Dependencies:** PF-013, PF-014

**Goal:** Present the approved operational KPIs and trends.

**Files:** `web/src/features/overview/`, `web/src/features/overview/**/*.test.tsx`

**Action:** Build KPI cards, trend charts, global filtering, timestamp, freshness badge, definitions, loading, empty, and error states.

**Why:** Overview is the primary user entry point.

**Verification:** UI values match fixture outputs under every supported filter combination.

**Expected result:** An operations manager can assess terminal status quickly.

### Task PF-016 — Implement stale and failed-snapshot recovery

**Priority:** P0

**Dependencies:** PF-015

**Goal:** Keep the public product useful during dataset failures.

**Files:** `web/src/data/cache.ts`, `web/src/data/errors.ts`, `web/src/components/DataState.tsx`, associated tests

**Action:** Distinguish unavailable, malformed, empty, and stale data; retain the last valid loaded snapshot.

**Why:** The UI must not become blank or misleading when an asset fails.

**Verification:** Fault-injection tests prove each state and confirm that no fabricated value appears.

**Expected result:** Data failures are isolated, visible, and recoverable.

### Task PF-017 — Add KPI definitions and methodology

**Priority:** P1

**Dependencies:** PF-015

**Goal:** Make every displayed metric auditable.

**Files:** `web/src/content/kpis.ts`, `web/src/components/KpiDefinition.tsx`, `docs/product/kpi-catalog.md`

**Action:** Display grain, formula, time boundary, exclusions, and zero-denominator behavior.

**Why:** Numbers without definitions are not a trusted data product.

**Verification:** Every KPI identifier in the snapshot resolves to documented content.

**Expected result:** Users and reviewers can understand and verify every metric.

## R4 — Exploration and replay

### Task PF-018 — Build equipment exploration

**Priority:** P1

**Dependencies:** PF-013, PF-014

**Goal:** Let users find unreliable equipment and inspect its history.

**Files:** `web/src/features/equipment/`, associated tests

**Action:** Add search, sorting, status filters, reliability columns, charts, and detail routing.

**Why:** Equipment reliability is a primary business job.

**Verification:** Search, sorting, filters, URL state, and fixture drill-down values pass tests.

**Expected result:** Users can move from fleet-level patterns to one asset.

### Task PF-019 — Build incident exploration

**Priority:** P1

**Dependencies:** PF-013, PF-014

**Goal:** Let users analyze incident patterns and lifecycles.

**Files:** `web/src/features/incidents/`, associated tests

**Action:** Add terminal/severity filters, trend and root-cause charts, recurring faults, and lifecycle detail.

**Why:** Incident recovery and recurrence drive reliability decisions.

**Verification:** Counts, durations, filters, and lifecycle ordering match fixtures.

**Expected result:** Users can identify and investigate recurring operational failures.

### Task PF-020 — Implement deterministic replay state

**Priority:** P1

**Dependencies:** PF-013

**Goal:** Replay snapshot events entirely in the browser.

**Files:** `web/src/features/replay/replayMachine.ts`, `web/src/features/replay/replayMachine.test.ts`

**Action:** Implement start, pause, resume, reset, speed, deterministic virtual time, and reduced-motion behavior.

**Why:** Replay demonstrates event-driven behavior without an always-on backend.

**Verification:** Fake-clock tests prove state transitions and event order at every speed.

**Expected result:** Replay behavior is predictable and testable.

### Task PF-021 — Build the Live Demo interface

**Priority:** P1

**Dependencies:** PF-014, PF-020

**Goal:** Show replay controls, activity, and changing KPIs.

**Files:** `web/src/features/replay/LiveDemoPage.tsx`, `web/src/features/replay/components/`, associated tests

**Action:** Connect replay state to accessible controls, event feed, and KPI changes; label the simulation persistently.

**Why:** The product should feel operational without making a false live-data claim.

**Verification:** Keyboard, reduced-motion, labelling, reset, and KPI update tests pass.

**Expected result:** Visitors can control and understand the simulation replay.

## R5 — Product hardening

### Task PF-022 — Build Data Health

**Priority:** P1

**Dependencies:** PF-013, PF-014

**Goal:** Expose freshness, reconciliation, rejects, and quality outcomes.

**Files:** `web/src/features/health/`, associated tests

**Action:** Render manifest time, age, layer counts, rejection reasons, rules, and pipeline status.

**Why:** Trust and observability are part of the product.

**Verification:** Health values reconcile with the quality export and stale thresholds.

**Expected result:** Users can distinguish healthy, stale, and invalid data.

### Task PF-023 — Complete responsive and accessibility behavior

**Priority:** P0

**Dependencies:** PF-015, PF-018, PF-019, PF-021, PF-022

**Goal:** Make every approved view usable without a mouse and on narrow screens.

**Files:** `web/src/styles/`, shared UI components, `web/e2e/accessibility.spec.ts`

**Action:** Correct semantics, focus order, contrast, chart summaries, status text, touch targets, and mobile overflow.

**Why:** Accessibility is an acceptance criterion, not optional polish.

**Verification:** Automated accessibility checks pass and the manual keyboard checklist has no blocker.

**Expected result:** The complete product is accessible and responsive.

### Task PF-024 — Add end-to-end reconciliation tests

**Priority:** P0

**Dependencies:** PF-013, PF-023

**Goal:** Prove one deterministic input across every layer and displayed KPI.

**Files:** `tests/e2e/test_pipeline_reconciliation.py`, `web/e2e/reconciliation.spec.ts`

**Action:** Run source → Bronze → Silver → Gold → JSON → browser and compare known counts, hashes, and KPIs.

**Why:** Separate green component tests do not prove the complete product is correct.

**Verification:** The full fixture produces the exact expected results in pipeline and UI.

**Expected result:** One automated test proves end-to-end correctness.

### Task PF-025 — Add failure-injection coverage

**Priority:** P1

**Dependencies:** PF-010, PF-011, PF-016, PF-024

**Goal:** Verify recovery from the failures claimed in the design.

**Files:** `tests/resilience/`, `web/e2e/failure-states.spec.ts`

**Action:** Inject failed writes, duplicate rows, invalid references, malformed JSON, missing assets, and stale manifests.

**Why:** Recovery behavior must be demonstrated, not described only in documentation.

**Verification:** Watermarks, quarantine, prior snapshots, and unaffected views behave as specified.

**Expected result:** Failure modes have repeatable evidence.

### Task PF-026 — Enforce performance budgets

**Priority:** P1

**Dependencies:** PF-013, PF-023

**Goal:** Keep the static product usable on ordinary mobile connections.

**Files:** `scripts/check_budgets.py`, `web/lighthouse.config.js`, workflow configuration

**Action:** Enforce snapshot, bundle, startup, and interaction budgets using measured build artifacts.

**Why:** A static site can still fail users through oversized data and JavaScript.

**Verification:** CI fails when a committed fixture exceeds its documented budget.

**Expected result:** Performance regressions cannot silently ship.

## R6 — Reproducible public V1

### Task PF-027 — Build the complete CI quality gate

**Priority:** P0

**Dependencies:** PF-024, PF-025, PF-026

**Goal:** Prevent invalid code or data from reaching production.

**Files:** `.github/workflows/ci.yml`

**Action:** Run lint, types, unit, data, integration, end-to-end, accessibility, export validation, and performance checks.

**Why:** Publication safety depends on automated evidence.

**Verification:** A controlled failure in each stage blocks the workflow.

**Expected result:** Main cannot publish an invalid build.

### Task PF-028 — Make GitHub Pages publication safe

**Priority:** P0

**Dependencies:** PF-001, PF-027

**Goal:** Publish immutable successful builds without damaging the last valid deployment.

**Files:** `.github/workflows/pages.yml`, `web/vite.config.ts`, deployment documentation

**Action:** Build with the repository base path, upload one artifact, use deployment concurrency, and deploy only from protected main.

**Why:** The public product must survive failed rebuilds.

**Verification:** Preview paths work, failed quality gates do not deploy, and the production URL loads all assets.

**Expected result:** Deployment is repeatable, static, and failure-safe.

### Task PF-029 — Document one-command reproduction

**Priority:** P0

**Dependencies:** PF-028

**Goal:** Let a new contributor reproduce the published snapshot and site.

**Files:** `README.md`, `docs/runbooks/local-development.md`, `Makefile`

**Action:** Document prerequisites, environment setup, seed, pipeline, tests, frontend, build, reset, and troubleshooting.

**Why:** Reproducibility is part of the product claim.

**Verification:** Follow the runbook from a clean clone without undocumented steps.

**Expected result:** One documented command produces a verified local build.

### Task PF-030 — Run the V1 release gate

**Priority:** P0

**Dependencies:** PF-029

**Goal:** Verify every approved acceptance criterion before declaring V1 complete.

**Files:** `docs/releases/v1-checklist.md`, `CHANGELOG.md`

**Action:** Record automated results, manual accessibility checks, responsive screenshots, public URL, cost-evidence review, and known limitations.

**Why:** Completion requires evidence across product, data, reliability, accessibility, deployment, and cost.

**Verification:** Every checklist item has a passing result or V1 remains incomplete.

**Expected result:** PortFlow V1 has an auditable release record.

## Post-V1 backlog

These items are P2 and cannot block V1:

- PF-101: Redpanda local streaming into the existing Bronze contract.
- PF-102: Streaming deduplication, late events, and dead-letter handling.
- PF-103: Dagster orchestration and run metadata.
- PF-104: Prometheus and Grafana engineering observability.
- PF-105: Larger DuckDB, Polars, and PySpark benchmarks.
- PF-106: BigQuery Sandbox portability lab.
- PF-107: Databricks Free Edition Delta/PySpark lab.
- PF-108: Optional time-limited cloud comparison.

## Specification coverage

| Approved requirement | Delivery tasks |
|---|---|
| Permanent-$0 evidence and fallbacks | PF-001–PF-002 |
| Public static product and first vertical slice | PF-003–PF-007 |
| Deterministic source and complete local data path | PF-004–PF-013 |
| Incremental safety, quarantine, Gold semantics, and reconciliation | PF-010–PF-013, PF-024–PF-025 |
| Versioned public snapshot contract | PF-006, PF-013 |
| Operations Overview and filters | PF-014–PF-017 |
| Equipment and incident drill-downs | PF-018–PF-019 |
| Browser replay with simulation disclosure | PF-020–PF-021 |
| Data freshness and quality visibility | PF-016, PF-022 |
| Accessibility and responsive behavior | PF-014, PF-021, PF-023 |
| Performance budgets | PF-026 |
| Safe CI and static publication | PF-027–PF-028 |
| Clean-clone reproducibility and release evidence | PF-029–PF-030 |

## Definition of done for every task

A task is done only when:

- its tests were written first and observed failing for the intended reason;
- the minimal implementation makes those tests pass;
- related regression tests pass;
- identifiers and contracts match neighboring tasks;
- documentation affected by the change is updated;
- no secret, generated private data, or billing dependency is introduced;
- the change is committed independently with a descriptive message.
