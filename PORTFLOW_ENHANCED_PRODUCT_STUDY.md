# PortFlow — Enhanced Product Study

**Decision date:** 2026-09-02

**Product:** A publicly accessible container-terminal operations control tower with a reproducible local data platform.

**Hard constraint:** The permanent product must require no cloud bill, billing account, payment card, or continuously running developer machine.

**Authority:** This document supersedes `PORTFLOW_FULL_VERIFIED_BRAINSTORMING.md` where the two conflict. The original is retained as a research archive.

## 1. Executive decision

PortFlow should be built as two connected products:

1. A static public web application hosted on GitHub Pages.
2. A local data-engineering platform that generates, validates, and exports the analytical snapshots consumed by that application.

The public application is periodically refreshed. It includes a browser-side replay of timestamped historical events, clearly labelled as simulation. It does not require a public API, database, broker, or continuously running server.

This structure satisfies all three primary goals:

- visitors receive a functional public product;
- the repository demonstrates credible data engineering;
- the permanent architecture has no metered runtime dependency.

## 2. Audit of the original brainstorming

### 2.1 What remains valuable

The original study correctly emphasized:

- realistic logistics and terminal-domain data;
- correlated stateful simulation rather than random rows;
- batch and streaming concepts;
- Bronze, Silver, and Gold responsibilities;
- incremental ingestion and safe watermarks;
- idempotency, late data, quarantine, and backfills;
- dimensional modeling and documented fact grain;
- data quality and reconciliation;
- reproducible local execution;
- cloud services as optional learning extensions.

These ideas remain part of the long-term project.

### 2.2 What prevented it from being an executable product plan

The original study combined four different initiatives:

- a public product;
- a local data platform;
- a technology portfolio;
- cloud and big-data learning labs.

That created a 12-stage roadmap in which a usable public product arrived too late. It also made Redpanda, Dagster, Prometheus, Grafana, PySpark, Terraform, BigQuery, Databricks, Fabric, and Snowflake appear closer to mandatory than they are.

Other issues included:

- no defined public web delivery architecture;
- no clear distinction between static availability and an always-on backend;
- reliability postponed until after batch and streaming construction;
- dashboard technology selected before the public-user requirement was defined;
- duplicated recommendations and vendor claims;
- broken UTF-8 rendering in diagrams and arrows;
- acceptance criteria grouped by technology rather than user outcome;
- no browser data contract, payload budget, or stale-data experience;
- no explicit protection of the last successful public deployment.

### 2.3 Optimization applied

The new plan uses an outcome-first vertical slice:

```text
one terminal
  → deterministic operational records
  → one incremental extraction
  → one Bronze dataset
  → one validated Silver dataset
  → one Gold KPI
  → one JSON snapshot
  → one deployed page
```

Only after this path is correct and public do we widen the domain and interface.

## 3. Users and jobs

### Primary user: operations manager

Needs to understand:

- current terminal throughput;
- congestion and dwell time;
- equipment availability and utilization;
- active and recurring incidents;
- MTTR and MTBF;
- which equipment needs attention.

### Secondary user: engineering reviewer or recruiter

Needs evidence that:

- KPIs have documented formulas and grain;
- the data path is reproducible;
- invalid data is quarantined;
- reruns are deterministic and idempotent;
- quality and freshness are visible;
- architecture choices support the $0 constraint.

## 4. V1 product experience

### Operations Overview

- global terminal and date-range filters;
- throughput and dwell-time KPIs;
- equipment availability, MTTR, and MTBF;
- active incidents and critical alarms;
- timestamp and freshness status;
- definitions attached to every KPI.

### Equipment

- searchable and sortable equipment table;
- status, utilization, downtime, alarms, and reliability;
- equipment detail with history and connected incidents.

### Incidents

- terminal and severity filters;
- trends, recurring fault codes, recovery duration, and root causes;
- incident lifecycle drill-down.

### Live Demo

- deterministic replay of historical simulated events;
- start, pause, resume, reset, and speed controls;
- KPI and activity-feed updates;
- reduced-motion support;
- persistent notice that the replay is simulated.

### Data Health

- snapshot generation time and age;
- last successful pipeline run;
- layer record counts and reconciliation;
- rejected-record count and reasons;
- quality rules and outcomes;
- link to methodology and repository.

## 5. V1 architecture

```text
PostgreSQL + deterministic terminal simulator
                    |
            incremental Python extractor
                    |
              Bronze Parquet
                    |
        Silver validate / type / deduplicate
                    |
          DuckDB + dbt Gold models
                    |
       versioned JSON snapshot + manifest
                    |
        React + TypeScript + Vite site
                    |
               GitHub Pages
```

### Technology choices

| Responsibility | Choice | V1 reason |
|---|---|---|
| Public UI | React + TypeScript + Vite | Static build, typed contracts, testable interactions |
| Charts | Apache ECharts | Interactive charts without hosted BI |
| Public host | GitHub Pages | Static availability with no application server |
| Source | PostgreSQL | Realistic OLTP extraction source |
| Processing | Python + Polars | Focused local pipeline with low overhead |
| Storage | Parquet | Compact analytical persistence |
| Analytics | DuckDB | Local analytical SQL over Parquet |
| Modeling | dbt Core | Explicit SQL lineage and tests |
| Public contract | Versioned JSON | Cacheable, inspectable, and browser-friendly |
| Automation | GitHub Actions | Validate, build, and publish from the repository |

## 6. Minimal domain

V1 includes only the connected entities needed by the approved experience:

- terminal;
- equipment;
- equipment telemetry;
- alarm;
- incident;
- maintenance activity;
- container movement.

Vessels, voyages, customers, shipments, weather, and external APIs are post-V1 unless a required KPI proves impossible without one of them.

### Required identifiers

- `terminal_id`
- `equipment_id`
- `event_id`
- `alarm_id`
- `incident_id`
- `maintenance_order_id`
- `movement_id`

All timestamps are stored as UTC. Events preserve both event time and ingestion time.

## 7. KPI definitions

Every KPI must define its grain, time boundary, numerator, denominator, exclusions, and behavior when the denominator is zero.

| KPI | Definition |
|---|---|
| Throughput | Completed container movements in the selected period, with TEU-equivalent as a later enhancement |
| Average dwell time | Mean elapsed time between a container's qualifying entry and exit movements for completed stays |
| Availability | Available time divided by scheduled time within the selected period |
| Utilization | Active operating time divided by available time within the selected period |
| MTTR | Total resolved-incident repair duration divided by resolved incident count |
| MTBF | Total operating time divided by count of qualifying failures |
| Active incidents | Incidents opened and not resolved at the selected period end |
| Critical alarms | Alarm events with severity `CRITICAL` in the selected period |

Fixture-based tests must lock these definitions before the dashboard is trusted.

## 8. Public snapshot contract

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

The manifest supplies:

- schema version;
- immutable snapshot identifier;
- UTC generation timestamp;
- UTC source-period bounds;
- quality status;
- record counts;
- relative dataset paths;
- content hashes.

The frontend validates every file before use. Publication is atomic from the user's perspective: a failed build cannot replace the last successful deployment.

## 9. Reliability model

Reliability is part of each slice, not a separate late project phase.

### Extraction

- use `(updated_at, primary_key)` as the cursor;
- advance the watermark only after a committed Bronze write;
- attach run and batch identifiers;
- retain source metadata.

### Transformation

- preserve raw input in Bronze;
- validate and normalize in Silver;
- quarantine invalid rows with explicit reason codes;
- deduplicate by stable business or event identifiers;
- document Gold grains and formulas;
- reconcile record counts between layers.

### Publication

- reject invalid snapshot schemas;
- verify hashes and record counts;
- publish only after all data and UI tests pass;
- retain the last successful deployment after failure.

### Browser

- distinguish loading, empty, stale, malformed, and unavailable states;
- retain the last valid in-memory snapshot after a refresh failure;
- isolate optional dataset failures;
- never invent missing values.

## 10. Accessibility and responsive behavior

The public product requires:

- semantic navigation and headings;
- complete keyboard operation;
- visible focus indicators;
- sufficient contrast;
- text summaries for chart conclusions;
- status communication beyond color;
- reduced-motion replay behavior;
- usable mobile layouts;
- concise labels and progressive disclosure.

These are acceptance requirements, not polish tasks.

## 11. Testing

### Unit

Simulator transitions, validation rules, composite cursors, deduplication, KPI formulas, exporters, frontend selectors, and replay state.

### Data

Uniqueness, accepted values, referential integrity, nullability, timestamps, metric ranges, fact grain, and layer reconciliation.

### Integration

PostgreSQL → Bronze, Bronze → Silver, Silver → Gold, Gold → JSON, and manifest → frontend.

### End to end

Build a deterministic small snapshot and verify navigation, filters, drill-downs, replay, responsive layout, accessibility-critical flows, and error states.

### Idempotency

Run identical input twice and require identical Gold values, counts, and public-export hashes.

## 12. Permanent-$0 analysis

### Strongest design guarantee

The application build contains static HTML, CSS, JavaScript, and data assets. It has no metered production compute, database, message broker, or API.

### Remaining policy dependency

GitHub Free, Pages, and Actions availability and quotas are vendor policies that can change. They must be checked against official documentation before implementation and recorded with:

- verification date;
- direct official URL;
- exact relevant constraint;
- impact if changed;
- fallback.

The fallback for static hosting is any free static host or local serving. The architecture is not GitHub-runtime-specific.

### Verification status

Live Chrome verification is currently blocked because the requested Chrome control connection is unavailable. Therefore this document intentionally does not repeat the original study's dated quota figures as newly verified facts.

## 13. V1 exclusions

Do not add these before V1 acceptance:

- public accounts, authorization, or writes;
- server-side APIs;
- public streaming infrastructure;
- Redpanda or Kafka;
- Dagster;
- Prometheus or Grafana;
- Metabase as the public product;
- MinIO;
- PySpark;
- Terraform;
- BigQuery, Databricks, Fabric, or Snowflake;
- multi-cloud equivalents;
- arbitrary large-data targets.

## 14. Delivery stages

| Stage | User-visible outcome |
|---|---|
| 0 | Cost and policy assumptions have an evidence ledger |
| 1 | One deterministic KPI renders from a generated snapshot |
| 2 | The complete local data path is correct and idempotent |
| 3 | Overview filters and KPI explanations work |
| 4 | Equipment and incident exploration work |
| 5 | Event replay and Data Health work |
| 6 | Accessibility, responsive behavior, and failure recovery pass |
| 7 | GitHub Pages deployment is reproducible and protected by CI |

## 15. V1 acceptance

V1 is complete only when:

- a public visitor can use the application without authentication;
- no developer machine must remain running;
- no required step requests billing details;
- all approved views work on desktop and mobile;
- filters and drill-downs return correct data;
- replay works without a backend and is labelled as simulation;
- published KPIs reconcile with Gold fixtures;
- snapshot freshness and quality evidence are visible;
- invalid records are quarantined and excluded from Gold;
- identical reruns produce identical results;
- failed validation cannot replace the last valid deployment;
- accessibility-critical paths pass automated and manual review;
- a clean clone reproduces the published snapshot through documented commands.

## 16. Post-V1 path

Add extensions in this order only after V1 acceptance:

1. Redpanda local streaming into the established Bronze contract.
2. Dagster orchestration and run metadata.
3. Prometheus and Grafana engineering observability.
4. reproducible DuckDB, Polars, and PySpark benchmarks.
5. BigQuery Sandbox portability study.
6. Databricks Free Edition Delta/PySpark study.
7. time-limited cloud trials for a specific documented learning goal.

Every extension must be removable without breaking the public V1.

## 17. Final product statement

PortFlow is a public, interactive terminal-operations control tower backed by a reproducible local data-engineering system. It turns deterministic operational and equipment data into tested analytical snapshots, exposes trusted logistics and reliability KPIs, demonstrates failure-aware processing, and remains publicly usable without an always-on paid backend.
