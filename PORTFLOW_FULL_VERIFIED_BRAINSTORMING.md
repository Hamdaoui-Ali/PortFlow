# PortFlow — $0 Real-Time Logistics Data Platform
## Full Web-Verified Technical Brainstorming, Architecture & Implementation Roadmap — 2026 Definitive Edition

> **Project objective:** Build a production-style Data Engineering platform for a container terminal / logistics company while keeping the permanent project at **zero cloud spend**.
>
> **Core strategy:** PortFlow must work completely on a developer laptop using free/self-hosted technologies. Cloud services are optional deployment or learning profiles—not runtime dependencies.

---

# 0. 2026 Web-Verified Reconciliation & Definitive Decisions

> **Verification date:** 2026-09-02  
> This section reconciles the original PortFlow brainstorm with the later $0 architecture study and current official vendor documentation. It is intended to be the authoritative decision layer for the rest of this document.

## 0.1 Executive verdict

The two studies converge on the same architectural principle:

> **PortFlow should be local-first, production-style, and cloud-extensible rather than cloud-dependent.**

The permanent implementation should run completely on a developer machine at zero software/cloud subscription spend. Cloud services are optional profiles used to demonstrate portability and real platform knowledge.

The final cost model is therefore:

| Execution profile | Purpose | Billing risk | Decision |
|---|---|---:|---|
| **PortFlow Local** | Full working platform | None from cloud services | **Primary / mandatory** |
| **BigQuery Sandbox** | Real GCP analytical SQL | No billing account required | **Recommended** |
| **GCP Free-Tier Profile** | Pub/Sub / Cloud Run / GCS demo | Billing account required; overage possible | **Optional** |
| **Databricks Free Edition** | Spark / Delta / Databricks lab | No-cost, quota-limited | **Recommended extension** |
| **Microsoft Fabric Trial** | OneLake / Lakehouse / Power BI lab | Time-limited trial | Optional |
| **Snowflake Trial** | Stage / COPY / Snowflake analytics lab | Time-limited trial | Optional |

The project must remain fully useful when every optional cloud account is deleted.

---

## 0.2 What the later study got right

The later study's strongest ideas are retained:

- Docker Compose as the local backbone.
- PostgreSQL as the operational source database.
- Kafka-compatible streaming locally.
- DuckDB as the local analytical engine.
- Bronze / Silver / Gold data layers.
- Metabase as the first business BI tool.
- Cloud services as mappings rather than hard dependencies.
- A sprint order that first produces a working local end-to-end pipeline.
- ADRs explaining important technology choices.
- A one-command developer experience as a major portfolio goal.

---

## 0.3 What required correction

### GCP "Always Free" is not the same as guaranteed no-billing infrastructure

The normal Google Cloud Free Tier requires an active Cloud Billing account. Staying within the documented monthly limits can cost $0, but paid billing accounts can incur overage if limits are exceeded.

Therefore the project documentation must distinguish:

```text
BigQuery Sandbox
    = no billing account required

General GCP Free Tier
    = billing account required
    = free allowance + possible overage
```

This distinction is central to the "$0" claim.

---

### BigQuery Sandbox is the safest real GCP component

Current official documentation provides, subject to Google's terms and future changes:

```text
10 GB active storage
1 TB query processing per month
```

without requiring a credit card/billing account.

Important Sandbox limitations include:

```text
60-day automatic expiry of tables/views/partitions
no streaming
no DML
no BigQuery Data Transfer Service
```

Therefore PortFlow uses BigQuery Sandbox as an **analytical showcase**, not the live streaming destination.

Recommended path:

```text
PortFlow Local Gold
        ↓
Parquet / export
        ↓
BigQuery Sandbox
        ↓
GoogleSQL analysis
        ↓
Looker Studio
```

---

### Cloud Run quota figures must be kept separate from older Cloud Functions figures

Current Cloud Run request-based free allocation is documented as:

```text
2 million requests/month
180,000 vCPU-seconds/month
360,000 GiB-seconds/month
```

The older `400,000 GB-seconds / 200,000 GHz-seconds / 2M invocations` figures are associated with older Cloud Functions pricing models and should not be presented as Cloud Run service quotas.

PortFlow should prefer:

```text
Cloud Run service
```

for containerized Python workloads, and use a function only when the event-driven function model is genuinely useful.

---

### Pub/Sub volume calculations must use billed throughput rules

Pub/Sub currently includes the first:

```text
10 GiB/month
```

of basic throughput per billing account.

However, message billing is not simply raw JSON payload size. Google documents:

```text
minimum 1 KB assessed per request
publish throughput counts
subscribe throughput counts
```

So a 200-byte synthetic event is not necessarily billed as only 200 bytes.

Portfolio-scale PortFlow traffic should still remain far below the free allowance when configured conservatively, but the README should calculate assessed traffic correctly.

---

### Databricks Community Edition is outdated

The project should use:

# **Databricks Free Edition**

not the retired legacy Community Edition.

Free Edition is a no-cost learning/experimentation environment with quotas and serverless-only compute. It is appropriate for:

```text
PySpark
Delta
SQL
notebooks
pipeline experiments
medallion architecture
```

but not production hosting or SLA-sensitive workloads.

---

### MinIO becomes optional instead of Sprint-1 mandatory

The later study proposed MinIO as the local Cloud Storage replacement.

That idea remains architecturally valid, but PortFlow does not need object storage semantics to prove the first end-to-end pipeline.

The simpler first implementation is:

```text
local filesystem
     +
Parquet
```

with a storage abstraction such as:

```text
StorageBackend
├── LocalFilesystemBackend
├── S3Backend
└── GCSBackend
```

MinIO can be added later if S3-compatible behavior is useful.

This reduces Sprint-1 operational complexity.

---

### Metabase + DuckDB has an explicit support caveat

Metabase currently exposes DuckDB through a **community connector**, available for self-hosted Metabase and not officially supported by Metabase.

Two valid deployment patterns are therefore documented:

**Fast local demo**

```text
DuckDB
  ↓
Metabase community connector
```

**More conservative serving architecture**

```text
DuckDB / dbt transformations
          ↓
PostgreSQL Gold serving tables
          ↓
Metabase official PostgreSQL driver
```

Start with the first; keep the second as fallback.

---

## 0.4 Definitive local architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                              │
│                                                                      │
│ PostgreSQL   CSV / JSON   REST   Stateful Terminal / IoT Simulator  │
│                                                                      │
│ customers    schedules          crane telemetry                     │
│ vessels      maintenance        alarm events                        │
│ voyages      movements          incident events                     │
│ containers                       operational conditions             │
└──────────────┬───────────────────────────────────┬───────────────────┘
               │                                   │
               │ BATCH                             │ STREAMING
               ▼                                   ▼
       Python / Polars                         Redpanda
       incremental extraction                  Kafka protocol
               │                                   │
               │                            Python consumers
               │                                   │
               └────────────────┬──────────────────┘
                                ▼
                        BRONZE / RAW
                      partitioned Parquet
                                │
                                ▼
                             SILVER
                 validate / type / normalize
                    deduplicate / quarantine
                                │
                                ▼
                              GOLD
                       facts + dimensions
                      business-oriented KPIs
                                │
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
             DuckDB         PostgreSQL       BigQuery
            local OLAP       serving DB       Sandbox
                │               │                │
                ▼               ▼                ▼
          developer SQL      Metabase       Looker Studio
```

Supporting platform:

```text
dbt Core        transformation models + tests
Dagster         orchestration / schedules / backfills
PySpark         selected large-scale transformations
Prometheus      metrics
Grafana         engineering observability
Docker Compose  reproducible local environment
Terraform       optional cloud IaC
GitHub Actions  CI/CD
GitHub Pages    project documentation
```

---

## 0.5 Final tool decision matrix

| Capability | Local primary | Cloud / extension | Status |
|---|---|---|---|
| OLTP source | PostgreSQL Docker | Supabase optional | Keep PostgreSQL |
| Streaming | Redpanda | Pub/Sub | Keep Redpanda |
| Object/file storage | Local filesystem + Parquet | GCS / optional S3 | Keep simple first |
| Warehouse / OLAP | DuckDB | BigQuery | Keep |
| Transformations | dbt Core + SQL | BigQuery SQL / Databricks | Keep |
| Large transformations | PySpark | Databricks Free Edition | Add later |
| Orchestration | Dagster | Cloud scheduler profile optional | Keep Dagster |
| Business BI | Metabase | Looker Studio | Keep |
| Engineering BI | Grafana | Cloud Monitoring optional | Keep |
| Metrics | Prometheus | Cloud Monitoring optional | Keep |
| IaC | Docker Compose | Terraform | Keep |
| CI/CD | GitHub Actions | same | Keep |
| Project docs | Markdown / MkDocs | GitHub Pages | Keep |
| Fabric | N/A | 60-day trial | Optional lab |
| Snowflake | N/A | 30-day trial | Optional lab |

---

## 0.6 Recommended three-layer $0 framework

### Layer 1 — Permanent local platform

This is where most engineering happens:

```text
PostgreSQL
Redpanda
Python
Parquet
DuckDB
dbt
Dagster
Metabase
Prometheus
Grafana
Docker
```

No cloud spend.

### Layer 2 — No-billing cloud analytics

```text
BigQuery Sandbox
+
Looker Studio
```

Used to demonstrate genuine GCP analytical experience without making GCP the runtime foundation.

### Layer 3 — Optional cloud labs

```text
GCP Free-Tier profile
Databricks Free Edition
Fabric trial
Snowflake trial
```

These reproduce selected parts of the logical architecture and provide platform-specific learning.

---

## 0.7 Final development order

The definitive implementation sequence is:

| Sprint | Focus | Main output |
|---:|---|---|
| 1 | Domain + PostgreSQL | Operational model, seed data, simulator foundation |
| 2 | Batch | PostgreSQL/CSV → Bronze → Silver → Gold → DuckDB |
| 3 | Streaming | Redpanda producers/consumers + DLQ |
| 4 | Modeling | dbt + star schema + SCD Type 2 |
| 5 | Reliability | Incremental ingestion, watermarks, idempotency, backfills, late events |
| 6 | BI | Metabase Operations Control Tower |
| 7 | Platform Ops | Dagster + Prometheus + Grafana |
| 8 | Engineering | Tests + GitHub Actions + documentation |
| 9 | Big Data | PySpark + 1M/10M-event benchmarks |
| 10 | GCP | BigQuery Sandbox, Looker Studio, optional Pub/Sub/Cloud Run |
| 11 | Databricks | Free Edition + Delta + PySpark |
| 12 | Optional labs | Fabric / Snowflake |

Terraform is intentionally not a Sprint-1 concern. It becomes useful once there is actual cloud infrastructure worth provisioning.

---

## 0.8 North-star project description

> **PortFlow is a production-style real-time logistics and terminal operations data platform that unifies batch operational datasets and streaming equipment events into a trusted analytical ecosystem. The platform simulates container-terminal operations—including vessels, containers, cranes, alarms, incidents, movements and maintenance—and processes the resulting data through Bronze, Silver and Gold layers. It implements incremental and idempotent ingestion, watermarking, deduplication, late-event handling, dead-letter queues, schema evolution, automated data-quality controls and SCD Type 2 dimensional modeling. PortFlow exposes operational KPIs such as terminal throughput, container dwell time, equipment availability, MTTR, MTBF and recurring faults through business dashboards, while Prometheus and Grafana provide engineering observability over throughput, freshness, failures and consumer lag. The core platform is fully reproducible locally with Python, PostgreSQL, Redpanda, Parquet, DuckDB, dbt, Dagster and Docker, with optional BigQuery, GCP, PySpark and Databricks implementations used to demonstrate cloud and Big Data portability.**

---

## 0.9 Official sources used for the September 2026 verification

These links are intentionally kept in the project study so future implementation work can re-check limits before enabling cloud resources.

### Google Cloud

- Google Cloud Free Program / billing requirements  
  https://docs.cloud.google.com/free/docs/free-cloud-features
- BigQuery Sandbox  
  https://docs.cloud.google.com/bigquery/docs/sandbox
- Cloud Run pricing  
  https://cloud.google.com/run/pricing
- Pub/Sub pricing  
  https://cloud.google.com/pubsub/pricing

### Databricks

- Databricks Free Edition  
  https://docs.databricks.com/aws/en/getting-started/free-edition
- Databricks Free Edition limitations  
  https://docs.databricks.com/aws/en/getting-started/free-edition-limitations

### Microsoft Fabric

- Fabric free trial  
  https://www.microsoft.com/en/microsoft-fabric/getting-started

### Snowflake

- Snowflake trial  
  https://www.snowflake.com/en/snowflake-trial/

### GitHub

- Actions billing  
  https://docs.github.com/en/actions/concepts/billing-and-usage
- GitHub Pages  
  https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site

### Redpanda

- Kafka client compatibility  
  https://docs.redpanda.com/streaming/current/develop/kafka-clients/

### Metabase

- DuckDB community connector  
  https://www.metabase.com/data-sources/duckdb
- Community drivers  
  https://www.metabase.com/docs/latest/developers-guide/community-drivers

---

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What PortFlow Solves](#2-what-portflow-solves)
3. [Design Principles](#3-design-principles)
4. [The $0 Strategy](#4-the-0-strategy)
5. [Target Architecture](#5-target-architecture)
6. [Technology Stack](#6-technology-stack)
7. [Business Domain](#7-business-domain)
8. [Operational Source System](#8-operational-source-system)
9. [Synthetic Data & Terminal Simulator](#9-synthetic-data--terminal-simulator)
10. [Streaming Architecture](#10-streaming-architecture)
11. [Batch Architecture](#11-batch-architecture)
12. [Storage & Medallion Architecture](#12-storage--medallion-architecture)
13. [Warehouse & Analytical Engines](#13-warehouse--analytical-engines)
14. [Dimensional Modeling](#14-dimensional-modeling)
15. [SCD Type 2](#15-scd-type-2)
16. [Incremental ETL/ELT](#16-incremental-etlelt)
17. [Idempotency](#17-idempotency)
18. [Watermarking](#18-watermarking)
19. [Late & Out-of-Order Events](#19-late--out-of-order-events)
20. [Backfills & Reprocessing](#20-backfills--reprocessing)
21. [Schema Evolution & Data Contracts](#21-schema-evolution--data-contracts)
22. [dbt Analytics Engineering](#22-dbt-analytics-engineering)
23. [PySpark](#23-pyspark)
24. [Orchestration](#24-orchestration)
25. [Data Quality](#25-data-quality)
26. [Observability](#26-observability)
27. [Business Intelligence](#27-business-intelligence)
28. [Operations Control Tower](#28-operations-control-tower)
29. [Engineering Control Tower](#29-engineering-control-tower)
30. [SLIs, SLOs & SLAs](#30-slis-slos--slas)
31. [Failure Injection & Resilience Testing](#31-failure-injection--resilience-testing)
32. [Performance Benchmarking](#32-performance-benchmarking)
33. [Docker Environment](#33-docker-environment)
34. [Infrastructure as Code](#34-infrastructure-as-code)
35. [CI/CD](#35-cicd)
36. [Testing Strategy](#36-testing-strategy)
37. [Security & Secrets](#37-security--secrets)
38. [GCP Lab](#38-gcp-lab)
39. [BigQuery Sandbox](#39-bigquery-sandbox)
40. [Databricks Free Edition](#40-databricks-free-edition)
41. [Microsoft Fabric Lab](#41-microsoft-fabric-lab)
42. [Snowflake Lab](#42-snowflake-lab)
43. [GitHub Pages Project Site](#43-github-pages-project-site)
44. [Repository Structure](#44-repository-structure)
45. [Development Roadmap](#45-development-roadmap)
46. [Milestones & Acceptance Criteria](#46-milestones--acceptance-criteria)
47. [Portfolio & Resume Positioning](#47-portfolio--resume-positioning)
48. [Interview Stories](#48-interview-stories)
49. [What Not to Build](#49-what-not-to-build)
50. [Final Recommended Scope](#50-final-recommended-scope)
51. [Verified $0 / Free-Tier Assumptions](#51-verified-0--free-tier-assumptions)
52. [Useful Official References](#52-useful-official-references)

---

# 1. Executive Summary

**PortFlow** is a real-time logistics and terminal operations data platform designed to demonstrate production-oriented Data Engineering.

The system models a company operating one or more container terminals. It ingests:

- vessels and voyages;
- containers;
- equipment and cranes;
- equipment telemetry;
- equipment alarms;
- incidents;
- container movements;
- maintenance activity;
- weather and operational conditions;
- customers;
- terminal transactions.

It processes both:

- **batch data**, such as operational PostgreSQL tables and CSV/JSON files;
- **streaming data**, such as crane telemetry, alarms and equipment events.

The data is transformed through a **Bronze → Silver → Gold** architecture, validated, deduplicated, enriched, modeled into analytical fact/dimension tables, and exposed through operational and engineering dashboards.

The permanent architecture is intentionally **local-first**:

```text
PostgreSQL
Python generators
CSV / JSON / REST
        │
        ├────────── Batch ─────────────┐
        │                              │
        └──────── Streaming ─ Redpanda │
                                       ▼
                                Bronze / Raw
                                  Parquet
                                       │
                                       ▼
                                    Silver
                              clean / validate
                             dedup / standardize
                                       │
                                       ▼
                                     Gold
                              star-schema marts
                                       │
                   ┌───────────────────┼───────────────────┐
                   ▼                   ▼                   ▼
                DuckDB             PostgreSQL          BigQuery
                   │                                     Sandbox
                   ▼
                Metabase

Platform services:
- dbt Core
- Dagster
- PySpark
- Prometheus
- Grafana
- Docker Compose
- Terraform
- GitHub Actions
```

The goal is not to make a toy ETL project.

The goal is to create a system that allows discussion of:

- ETL and ELT;
- batch and streaming;
- data lakes;
- data warehouses;
- dimensional modeling;
- SCD Type 2;
- data contracts;
- schema evolution;
- incremental loading;
- idempotency;
- watermarks;
- late events;
- backfills;
- dead-letter queues;
- data quality;
- observability;
- orchestration;
- Big Data processing;
- performance optimization;
- infrastructure as code;
- CI/CD;
- cloud warehouses;
- operational KPIs.

---

# 2. What PortFlow Solves

Imagine a logistics company operating multiple terminals.

Management asks:

- How efficiently is each terminal operating?
- How many containers are processed every hour?
- What is today's terminal throughput?
- Which cranes fail most frequently?
- Which alarms recur?
- What is the average incident recovery duration?
- What is equipment availability?
- What is MTTR?
- What is MTBF?
- Which containers have excessive dwell time?
- Which vessels or routes experience delays?
- Is congestion increasing?
- Which equipment is approaching abnormal behavior?
- How fresh is the operational data?
- Are any ingestion pipelines failing?
- Are invalid operational records entering dashboards?

Answering those questions requires more than charts.

It requires:

1. ingestion;
2. storage;
3. transformation;
4. business modeling;
5. quality controls;
6. orchestration;
7. monitoring;
8. analytical SQL;
9. reliable reruns;
10. scalable processing.

That is the real purpose of PortFlow.

---

# 3. Design Principles

## 3.1 Local-first

A developer cloning the repository should be able to run most of PortFlow using:

```bash
docker compose up
```

No mandatory cloud account.

No mandatory paid database.

No mandatory SaaS service.

---

## 3.2 Cloud-portable

Business logic should not be tightly coupled to one provider.

Example:

```text
Local                 GCP                  Databricks
-----                 ---                  ----------
Redpanda        <->   Pub/Sub
Parquet         <->   Cloud Storage       Delta
DuckDB          <->   BigQuery            Databricks SQL
Dagster         <->   Cloud Scheduler     Lakeflow Jobs
```

The exact implementations differ, but the architectural concepts remain portable.

---

## 3.3 Production-style, portfolio-sized

PortFlow does **not** need billions of records.

It needs enough volume and complexity to demonstrate sound engineering decisions.

A better project:

```text
10 million well-designed events
+ benchmarks
+ tests
+ recovery mechanisms
```

is more valuable than:

```text
1 billion random rows
+ no quality
+ no observability
+ no engineering story
```

---

## 3.4 Observable

Every important pipeline should expose:

- execution status;
- latency;
- throughput;
- failures;
- rejected records;
- freshness;
- consumer lag;
- last successful execution.

---

## 3.5 Replayable

A production data platform must survive reruns.

A pipeline should not corrupt results when:

```text
2026-09-01
```

is processed twice.

---

## 3.6 Data quality as a first-class concern

Bad data must not silently propagate into Gold.

Invalid records should either:

- be rejected;
- be quarantined;
- be corrected through explicit business logic.

---

# 4. The $0 Strategy

There are three categories of infrastructure.

## Mode A — PortFlow Local

The permanent implementation.

Target:

> **$0 cloud spend indefinitely.**

Uses:

- Python;
- PostgreSQL;
- Redpanda Community Edition;
- Parquet;
- DuckDB;
- dbt Core;
- PySpark;
- Dagster;
- Metabase OSS;
- Prometheus;
- Grafana;
- Docker;
- Terraform;
- GitHub Actions;
- GitHub Pages.

This uses the developer's own machine, so "$0" means **zero software/cloud subscription spend**, excluding hardware, internet and electricity.

---

## Mode B — Real Free Cloud Labs

Cloud environments that can meaningfully demonstrate cloud skills without becoming permanent paid dependencies.

Primary examples:

- BigQuery Sandbox;
- Databricks Free Edition.

---

## Mode C — Temporary Trials

Use only for targeted experiments.

Examples:

- Microsoft Fabric trial;
- Snowflake trial.

These should never become required for PortFlow to run.

---

# 5. Target Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                              │
│                                                                      │
│ PostgreSQL   CSV/JSON   REST APIs   Weather   Equipment Simulator    │
│                                                                      │
│ customers    schedules             crane telemetry                  │
│ vessels      maintenance           alarm events                     │
│ voyages      movements             incident events                  │
│ containers                                                          │
└──────────────┬──────────────────────────────────┬────────────────────┘
               │                                  │
               │ BATCH                            │ STREAMING
               ▼                                  ▼
       Python / Polars                      Redpanda
       incremental extract                  Kafka API
               │                                  │
               │                           Python consumers
               │                                  │
               └───────────────┬──────────────────┘
                               ▼
                         BRONZE / RAW
                          Parquet lake
                               │
                               ▼
                            SILVER
                        dbt / Python /
                          PySpark
                               │
                 clean / validate / dedup
                  standardize / quarantine
                               │
                               ▼
                             GOLD
                    dimensional data marts
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
       DuckDB             PostgreSQL             BigQuery
     local OLAP           serving DB             Sandbox
          │
          ▼
       Metabase
Operations Control Tower

Supporting services

Dagster        orchestration
Prometheus     metrics
Grafana        engineering observability
dbt            transformations/tests
PySpark        large transformations
Docker         reproducible environment
Terraform      infrastructure definitions
GitHub Actions CI/CD
GitHub Pages   portfolio documentation
```

---

# 6. Technology Stack

| Layer | Primary Technology | Purpose |
|---|---|---|
| Language | Python | ingestion, simulation, validation |
| Query language | SQL | transformations and analytics |
| OLTP source | PostgreSQL | operational system |
| Streaming | Redpanda | Kafka-compatible event broker |
| File format | Parquet | analytical lake storage |
| Local OLAP | DuckDB | analytical SQL |
| Transformations | dbt Core | ELT modeling and tests |
| Big Data | PySpark | large distributed-style jobs |
| Orchestration | Dagster | scheduling, retries, assets |
| BI | Metabase OSS | business dashboards |
| Monitoring | Prometheus | metric collection |
| Visualization | Grafana | engineering dashboard |
| Containers | Docker Compose | local platform |
| IaC | Terraform | infrastructure |
| CI/CD | GitHub Actions | automated validation |
| Cloud DW | BigQuery Sandbox | GCP analytics lab |
| Lakehouse | Databricks Free Edition | Spark/Delta lab |
| Documentation | Markdown + GitHub Pages | public portfolio |

---

# 7. Business Domain

## 7.1 Terminals

```text
terminal_id
terminal_name
country
city
timezone
capacity_teu
status
```

Example:

```text
TM1 — Casablanca Terminal
TM2 — Tanger Med Terminal
TM3 — Valencia Terminal
```

---

## 7.2 Equipment

Equipment categories:

```text
QC      Quay Crane
ARMG    Automated Rail Mounted Gantry
RTG     Rubber-Tyred Gantry Crane
SC      Shuttle Carrier
TT      Terminal Tractor
RS      Reach Stacker
```

Table:

```text
equipment_id
terminal_id
equipment_type
manufacturer
model
installation_date
status
rated_load
```

---

## 7.3 Containers

```text
container_id
iso_type
length_ft
weight_kg
cargo_type
hazardous
reefer
customer_id
```

---

## 7.4 Vessels

```text
vessel_id
imo_number
vessel_name
operator
capacity_teu
```

---

## 7.5 Voyages

```text
voyage_id
vessel_id
origin_port
destination_port
scheduled_arrival
actual_arrival
scheduled_departure
actual_departure
status
```

---

## 7.6 Container movements

Examples:

```text
DISCHARGE
LOAD
YARD_TRANSFER
GATE_IN
GATE_OUT
RAIL_IN
RAIL_OUT
```

Table:

```text
movement_id
container_id
terminal_id
equipment_id
movement_type
source_location
destination_location
event_timestamp
```

---

## 7.7 Incidents

```text
incident_id
equipment_id
terminal_id
fault_type
severity
opened_at
acknowledged_at
resolved_at
technician_id
root_cause
resolution
```

---

## 7.8 Maintenance

```text
maintenance_order_id
equipment_id
maintenance_type
priority
opened_at
scheduled_at
completed_at
technician_id
parts_cost
labor_minutes
status
```

---

# 8. Operational Source System

PostgreSQL represents the terminal's transactional system.

Suggested schemas:

```text
operational.customers
operational.terminals
operational.vessels
operational.voyages
operational.containers
operational.equipment
operational.shipments
operational.maintenance_orders
operational.technicians
```

PostgreSQL is **not** the analytical data warehouse.

It represents the OLTP workload from which data is extracted.

This allows PortFlow to demonstrate:

```text
OLTP
  ↓
incremental extraction
  ↓
lake / warehouse
  ↓
analytics
```

---

# 9. Synthetic Data & Terminal Simulator

A major differentiator should be a realistic stateful simulator.

Avoid generating completely independent random values.

Instead simulate operational behavior.

## 9.1 Equipment state machine

Example:

```text
IDLE
 ↓
ACTIVE
 ↓
HIGH_LOAD
 ↓
WARNING
 ↓
ALARM
 ↓
INCIDENT_OPEN
 ↓
UNAVAILABLE
 ↓
MAINTENANCE
 ↓
RECOVERING
 ↓
ACTIVE
```

State affects measurements.

For example:

### ACTIVE

```text
load: 50–80%
temperature: 45–65°C
rpm: normal
```

### HIGH_LOAD

```text
load: 80–100%
temperature increases
energy consumption increases
```

### WARNING

Probability of:

```text
HYDRAULIC_PRESSURE_LOW
MOTOR_TEMPERATURE_HIGH
BRAKE_SYSTEM_WARNING
SENSOR_FAILURE
```

increases.

---

## 9.2 Correlated events

A useful simulation sequence:

```text
QC-014 load increases
        ↓
motor temperature increases
        ↓
HIGH_TEMPERATURE alarm
        ↓
alarm repeats 4 times
        ↓
incident opened
        ↓
equipment unavailable
        ↓
maintenance intervention
        ↓
incident resolved
        ↓
equipment active again
```

Now analytics can discover relationships.

---

## 9.3 Intentional bad data

Generate controlled failure percentages.

Example:

```yaml
simulation:
  duplicate_event_rate: 0.03
  missing_equipment_rate: 0.002
  invalid_timestamp_rate: 0.001
  late_event_rate: 0.04
  unknown_equipment_rate: 0.001
  out_of_order_rate: 0.05
```

The values should be configurable.

---

## 9.4 Event volume profiles

```text
tiny       1,000 events
small      100,000 events
medium     1,000,000 events
large      10,000,000 events
stress     configurable
```

Useful for benchmarking.

---

# 10. Streaming Architecture

Use Redpanda locally.

Redpanda provides a Kafka-compatible streaming interface and its Community Edition can be self-hosted.

Topics:

```text
portflow.telemetry
portflow.alarms
portflow.incidents
portflow.container_movements
portflow.weather
```

Dead-letter topics:

```text
portflow.dlq.telemetry
portflow.dlq.alarms
portflow.dlq.incidents
portflow.dlq.movements
```

---

## 10.1 Producer

Example:

```text
equipment-simulator
      ↓
serialize JSON
      ↓
publish
      ↓
portflow.telemetry
```

---

## 10.2 Consumer

```text
Redpanda
   ↓
consumer
   ↓
parse JSON
   ↓
schema validation
   ↓
business validation
   ↓
valid?
  /    \
yes     no
 |       |
Bronze  DLQ
```

---

## 10.3 Example telemetry event

```json
{
  "event_id": "evt_00182982",
  "schema_version": 2,
  "equipment_id": "QC-014",
  "terminal_id": "TM2",
  "event_timestamp": "2026-09-02T20:41:18Z",
  "load_percent": 83.2,
  "temperature_c": 74.8,
  "motor_rpm": 1434,
  "energy_kw": 84.1,
  "operating_mode": "ACTIVE",
  "producer": "equipment-simulator"
}
```

---

## 10.4 Example alarm

```json
{
  "event_id": "evt_alarm_82812",
  "schema_version": 1,
  "alarm_id": "ALM-891827",
  "equipment_id": "ARMG-022",
  "terminal_id": "TM2",
  "fault_code": "HYDRAULIC_PRESSURE_LOW",
  "severity": "HIGH",
  "event_timestamp": "2026-09-02T20:44:11Z"
}
```

---

# 11. Batch Architecture

Sources:

```text
PostgreSQL
CSV
JSON
REST API
```

Example:

```text
PostgreSQL
     ↓
incremental extractor
     ↓
Bronze Parquet
     ↓
Silver transformation
     ↓
Gold marts
```

Files could include:

```text
maintenance.csv
vessel_schedule.csv
customers.csv
container_movements.csv
equipment.csv
```

---

# 12. Storage & Medallion Architecture

Use Parquet as the main local lake format.

Directory layout:

```text
data/
├── bronze/
│   ├── equipment_events/
│   │   └── year=2026/month=09/day=02/
│   ├── alarms/
│   ├── incidents/
│   ├── container_movements/
│   └── maintenance/
│
├── silver/
│   ├── equipment_events/
│   ├── alarms/
│   ├── incidents/
│   ├── container_movements/
│   └── voyages/
│
└── gold/
    ├── fact_equipment_metrics/
    ├── fact_alarms/
    ├── fact_incidents/
    ├── fact_container_movements/
    ├── dim_terminal/
    ├── dim_equipment/
    ├── dim_vessel/
    ├── dim_customer/
    ├── dim_fault/
    └── dim_date/
```

---

## Bronze

Rule:

> Preserve what arrived.

Typical columns added by ingestion:

```text
_ingestion_timestamp
_source
_schema_version
_batch_id
_file_name
_partition_date
```

Do minimal transformation.

---

## Silver

Responsibilities:

- schema enforcement;
- type conversions;
- timestamp normalization;
- null validation;
- deduplication;
- business validation;
- reference validation;
- quarantine invalid records;
- joins;
- normalization.

---

## Gold

Responsibilities:

- business facts;
- dimensions;
- KPI tables;
- aggregates;
- dimensional star schema.

---

# 13. Warehouse & Analytical Engines

## 13.1 DuckDB

DuckDB becomes the local OLAP engine.

Example:

```sql
SELECT
    terminal_id,
    equipment_id,
    COUNT(*) AS alarm_count
FROM read_parquet(
    'data/gold/fact_alarms/**/*.parquet'
)
WHERE event_timestamp >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR
GROUP BY terminal_id, equipment_id
ORDER BY alarm_count DESC;
```

Advantages:

- embedded;
- no server needed;
- excellent Parquet support;
- analytical SQL;
- low operational overhead.

---

## 13.2 PostgreSQL analytical serving

Optional.

Some Gold tables can also be loaded into PostgreSQL for:

- Metabase;
- integration tests;
- API serving.

---

## 13.3 BigQuery

Cloud analytical extension.

The logical models should remain similar:

```text
gold.fact_incidents
gold.fact_alarms
gold.fact_container_movements
gold.fact_equipment_metrics
```

---

# 14. Dimensional Modeling

PortFlow should demonstrate proper warehouse modeling.

## Facts

```text
fact_container_movements
fact_incidents
fact_alarms
fact_equipment_metrics
fact_maintenance
```

## Dimensions

```text
dim_equipment
dim_terminal
dim_vessel
dim_customer
dim_fault
dim_container
dim_date
dim_time
```

---

## 14.1 Fact grain

The grain must be documented.

Examples:

### fact_alarms

> One row per alarm event.

### fact_incidents

> One row per incident lifecycle.

### fact_container_movements

> One row per physical container movement event.

### fact_equipment_metrics

> One row per equipment per five-minute interval.

---

# 15. SCD Type 2

Implement at least one Type 2 dimension.

Best candidate:

```text
dim_equipment
```

Columns:

```text
equipment_sk
equipment_id
equipment_type
terminal_id
manufacturer
status
valid_from
valid_to
is_current
```

Example:

| equipment_sk | equipment_id | terminal | valid_from | valid_to | is_current |
|---:|---|---|---|---|---|
| 128 | QC-014 | TM1 | 2025-01-01 | 2026-04-14 | false |
| 284 | QC-014 | TM2 | 2026-04-15 | NULL | true |

Benefit:

An incident in January 2026 remains historically associated with TM1 even if the equipment later moved to TM2.

---

# 16. Incremental ETL/ELT

Do not reload everything every run.

Maintain:

```text
pipeline_watermarks
```

Example:

```text
pipeline_name
source_name
source_table
last_processed_timestamp
last_processed_id
updated_at
```

Incremental query:

```sql
SELECT *
FROM operational.maintenance_orders
WHERE updated_at > :last_processed_timestamp
ORDER BY updated_at;
```

After successful processing:

```text
watermark = maximum successfully committed timestamp
```

Never advance the watermark before the write is safely committed.

---

# 17. Idempotency

A core PortFlow feature.

Definition:

> Processing the same logical input repeatedly produces the same final analytical state.

Example duplicate:

```text
MV-73921
MV-73921
MV-73921
```

Bronze may preserve all three.

Silver should retain one canonical record.

Example:

```sql
ROW_NUMBER() OVER (
    PARTITION BY event_id
    ORDER BY _ingestion_timestamp DESC
)
```

Then:

```sql
WHERE row_number = 1
```

---

## 17.1 Batch idempotency

Running:

```bash
python pipelines/load_movements.py \
  --from 2026-09-01 \
  --to 2026-09-01
```

twice must not double Gold metrics.

---

## 17.2 Idempotency keys

Candidate keys:

```text
event_id
movement_id
alarm_id
incident_id
maintenance_order_id
```

---

# 18. Watermarking

Watermarks solve:

> What is the highest point in the source that has safely been processed?

Example:

```text
last_processed_timestamp = 2026-09-02T18:45:00Z
```

Next extraction:

```text
updated_at > watermark
```

For equal timestamps, combine:

```text
(updated_at, primary_key)
```

to prevent skipped rows.

---

# 19. Late & Out-of-Order Events

Streaming data can arrive late.

Example:

```text
event_time       20:10
arrival_time     20:18
```

Do not assume:

```text
arrival order == event order
```

Maintain both:

```text
event_timestamp
ingestion_timestamp
```

Possible policies:

```text
< 5 min late      normal
5–30 min late     accepted + tagged
> 30 min late     late-event workflow
```

Gold calculations should use event time where appropriate.

---

# 20. Backfills & Reprocessing

Support explicit historical reprocessing.

CLI:

```bash
python -m portflow.backfill \
  --dataset container_movements \
  --from 2026-08-01 \
  --to 2026-08-10
```

Requirements:

- deterministic;
- idempotent;
- visible in orchestration;
- logged;
- isolated by batch/run ID.

---

# 21. Schema Evolution & Data Contracts

A strong project should version event contracts.

## Version 1

```json
{
  "schema_version": 1,
  "equipment_id": "QC-001",
  "temperature": 64.2
}
```

## Version 2

```json
{
  "schema_version": 2,
  "equipment_id": "QC-001",
  "temperature": 64.2,
  "temperature_unit": "C",
  "motor_rpm": 1430
}
```

Consumer responsibilities:

- identify schema version;
- validate fields;
- map old versions;
- reject unsupported versions;
- preserve raw payload.

---

## 21.1 Data contract file

Example:

```yaml
name: equipment_telemetry
version: 2

required:
  - event_id
  - equipment_id
  - terminal_id
  - event_timestamp
  - schema_version

fields:
  temperature_c:
    type: float
    nullable: true

  load_percent:
    type: float
    min: 0
    max: 100
```

---

# 22. dbt Analytics Engineering

Use dbt Core for SQL-centric transformations.

Repository:

```text
dbt/
├── dbt_project.yml
├── models/
│   ├── staging/
│   ├── intermediate/
│   └── marts/
├── macros/
├── snapshots/
└── tests/
```

---

## Staging

```text
stg_equipment
stg_alarms
stg_incidents
stg_container_movements
stg_voyages
```

---

## Intermediate

```text
int_alarm_sequences
int_incident_durations
int_equipment_uptime
int_container_dwell
```

---

## Marts

```text
fact_alarms
fact_incidents
fact_container_movements
fact_equipment_metrics

dim_equipment
dim_terminal
dim_date
dim_vessel
dim_customer
```

---

## Tests

```yaml
columns:
  - name: equipment_id
    tests:
      - not_null

  - name: incident_id
    tests:
      - unique
      - not_null
```

Add custom tests for:

```text
resolved_at >= opened_at
weight_kg >= 0
load_percent between 0 and 100
known terminal
known equipment
```

---

# 23. PySpark

PySpark should solve a real larger-scale problem rather than exist only for the resume.

Candidate transformation:

```text
10M equipment events
       ↓
PySpark
       ↓
deduplicate
       ↓
window calculations
       ↓
hourly aggregates
       ↓
equipment availability
       ↓
Gold Parquet
```

Compare:

- Pandas;
- Polars;
- DuckDB;
- PySpark.

This gives a benchmark story rather than a checkbox.

---

# 24. Orchestration

Recommended first choice:

```text
Dagster
```

Potential asset graph:

```text
operational_postgres
        ↓
bronze_equipment
        ↓
silver_equipment
        ↓
dim_equipment
        ↓
fact_equipment_metrics
        ↓
terminal_kpis
```

Another:

```text
bronze_incidents
        ↓
silver_incidents
        ↓
fact_incidents
        ↓
mttr_metrics
```

Capabilities to demonstrate:

- schedules;
- retries;
- dependencies;
- partitioned assets;
- backfills;
- run metadata;
- failure hooks.

Airflow can be added later only if there is a clear reason.

---

# 25. Data Quality

Create a quality result model.

```text
data_quality_results
```

Columns:

```text
run_id
pipeline_name
table_name
rule_name
records_checked
records_failed
failure_rate
status
execution_timestamp
```

Example:

| rule | checked | failed | failure % | status |
|---|---:|---:|---:|---|
| equipment_exists | 185821 | 17 | 0.009% | PASS |
| valid_timestamp | 185821 | 2 | 0.001% | PASS |
| positive_weight | 42839 | 91 | 0.212% | FAIL |
| unique_event_id | 185821 | 431 | 0.232% | WARN |

---

## Quality categories

### Schema quality

- required fields;
- expected types;
- schema version.

### Domain quality

- known equipment;
- known terminal;
- valid severity.

### Logical quality

```text
resolved_at >= opened_at
```

### Numeric quality

```text
container_weight > 0
0 <= load_percent <= 100
```

### Uniqueness

```text
event_id unique after Silver
```

---

# 26. Observability

Two dimensions:

## Data observability

- freshness;
- row counts;
- missing data;
- quality failures;
- schema drift.

## Platform observability

- broker health;
- consumer lag;
- pipeline runtime;
- throughput;
- error rate;
- retries.

---

## Prometheus metrics

```text
portflow_events_received_total
portflow_events_rejected_total
portflow_events_processed_total
portflow_consumer_lag
portflow_pipeline_duration_seconds
portflow_pipeline_records_read
portflow_pipeline_records_written
portflow_pipeline_records_rejected
portflow_data_freshness_seconds
portflow_last_success_timestamp
```

---

# 27. Business Intelligence

Use:

```text
Metabase OSS
```

for the permanent local BI environment.

Metabase can connect to PostgreSQL and other supported analytical databases.

A future alternative is Apache Superset.

---

# 28. Operations Control Tower

Build a dashboard named:

> **PortFlow Operations Control Tower**

Sections:

## Terminal overview

- containers handled today;
- containers/hour;
- active vessels;
- current congestion;
- equipment availability;
- active incidents;
- critical alarms;
- average dwell time.

---

## Equipment reliability

- top failing equipment;
- MTTR;
- MTBF;
- failure rate;
- alarm recurrence;
- equipment utilization;
- availability %.

---

## Incident analysis

- incidents by severity;
- incidents by equipment;
- incidents by terminal;
- recurring faults;
- recovery duration;
- root-cause distribution.

---

## Container operations

- imports vs exports;
- dwell time;
- delayed containers;
- gate throughput;
- yard transfers;
- hourly throughput.

---

# 29. Engineering Control Tower

Grafana dashboard:

```text
PORTFLOW DATA PLATFORM HEALTH
```

Panels:

```text
Events/sec
Consumer lag
Pipeline duration
Pipeline failures
Rejected events
DLQ depth
Data freshness
Records processed
Records rejected
Last successful ingestion
```

Example:

```text
Events/sec         182
Consumer lag        23
Rejected events    0.3%
P95 latency        2.1s
Freshness           12s
Last batch       SUCCESS
```

---

# 30. SLIs, SLOs & SLAs

Define measurable targets.

```yaml
slos:

  streaming_latency:
    target_seconds: 10

  data_freshness:
    target_seconds: 30

  batch_duration:
    target_minutes: 5

  quality_failure_rate:
    maximum_percent: 0.1

  pipeline_success_rate:
    target_percent: 99
```

Track:

```text
P50
P95
P99
```

latency.

Example:

```text
P50    0.8s
P95    2.1s
P99    4.7s
Target < 10s
PASS
```

---

# 31. Failure Injection & Resilience Testing

Deliberately break the platform.

Examples:

```bash
docker stop portflow-redpanda
```

Observe producer behavior.

Restart:

```bash
docker start portflow-redpanda
```

Verify recovery.

---

Stop consumer:

```bash
docker stop portflow-stream-consumer
```

Continue generating events.

Restart consumer.

Observe:

```text
consumer lag rises
consumer lag falls
messages processed
no data loss
```

---

Other scenarios:

- kill PostgreSQL during batch;
- malformed events;
- duplicate messages;
- unavailable downstream storage;
- expired credentials in cloud profile;
- invalid schema version.

Document expected recovery behavior.

---

# 32. Performance Benchmarking

Create reproducible benchmark datasets.

Example:

```text
1M
5M
10M
```

events.

Compare storage.

Example target experiment:

| Format | Size |
|---|---:|
| JSON | measured |
| CSV | measured |
| Parquet | measured |

Do not invent benchmark numbers in README—generate them with scripts.

---

## 32.1 Engine benchmark

Same analytical query using:

```text
Pandas
Polars
DuckDB
PySpark
```

Measure:

```text
execution time
peak memory
output row count
```

---

## 32.2 Partition benchmark

Compare:

```text
full dataset scan
vs
date partition filter
```

Measure bytes/rows read and execution time.

---

## 32.3 BigQuery benchmark

Where sandbox limitations allow:

- query only needed columns;
- partitioned analytical tables where supported by the chosen workflow;
- compare scanned bytes.

BigQuery pricing makes bytes scanned an important optimization concept.

---

# 33. Docker Environment

Suggested services:

```yaml
services:
  postgres:
  redpanda:
  redpanda-console:
  dagster-webserver:
  dagster-daemon:
  metabase:
  prometheus:
  grafana:
```

Python ingestion/transformation services can run:

- as Docker containers;
- as local development processes.

---

## Developer commands

```bash
make up
make down
make seed
make simulate
make batch
make dbt
make test
make benchmark
make reset
```

---

# 34. Infrastructure as Code

Use Terraform for cloud definitions.

Repository:

```text
infrastructure/
├── local/
│   └── docker/
│
└── terraform/
    ├── gcp/
    │   ├── providers.tf
    │   ├── variables.tf
    │   ├── outputs.tf
    │   ├── bigquery.tf
    │   ├── pubsub.tf
    │   ├── cloudrun.tf
    │   ├── storage.tf
    │   └── iam.tf
    │
    └── environments/
        ├── dev.tfvars
        └── demo.tfvars
```

Important:

Terraform can be:

```text
fmt
validated
planned
reviewed
```

without permanently provisioning cloud infrastructure.

---

# 35. CI/CD

Use GitHub Actions.

Public repositories can use standard GitHub-hosted Actions runners without usage charges under GitHub's current policy.

Pipeline:

```text
Pull Request
    ↓
Python lint
    ↓
Python unit tests
    ↓
SQLFluff
    ↓
dbt parse/compile
    ↓
dbt tests
    ↓
Terraform fmt
    ↓
Terraform validate
    ↓
Docker build
    ↓
integration tests
```

Main branch:

```text
merge
  ↓
build documentation
  ↓
publish GitHub Pages
```

---

# 36. Testing Strategy

## Unit tests

Test:

- parsers;
- validators;
- state machines;
- watermark calculations;
- deduplication helpers.

---

## Data tests

Test:

- uniqueness;
- referential integrity;
- allowed values;
- temporal constraints;
- nullability.

---

## Integration tests

Example:

```text
producer
  ↓
Redpanda
  ↓
consumer
  ↓
Bronze
```

Assert event appears.

---

## End-to-end tests

Example:

```text
generate incident
      ↓
stream
      ↓
Bronze
      ↓
Silver
      ↓
Gold
      ↓
dashboard-ready table
```

---

## Idempotency tests

Run same batch twice.

Assert:

```text
Gold row count unchanged
Gold aggregates unchanged
```

---

# 37. Security & Secrets

Never commit:

```text
passwords
API keys
cloud credentials
private service account files
```

Use:

```text
.env
.env.example
GitHub Actions secrets
```

Add `.gitignore`.

For local development:

```text
POSTGRES_PASSWORD=...
```

comes from environment variables.

---

# 38. GCP Lab

The GCP version should demonstrate mappings rather than replace the local platform.

Example:

```text
Local                         GCP
-----                         ---
Redpanda                  -> Pub/Sub
local Parquet             -> Cloud Storage
Python consumer           -> Cloud Run / function
DuckDB                    -> BigQuery
local scheduler           -> Cloud Scheduler
Docker definitions        -> Cloud Run container
Terraform                 -> GCP resources
```

Because billing can activate beyond free allowances, use GCP cautiously.

The safest permanently-free Google component for this project is the BigQuery Sandbox.

---

# 39. BigQuery Sandbox

BigQuery Sandbox is particularly useful because Google currently allows users to explore BigQuery without a credit card or billing account.

Current documented Sandbox free usage includes:

```text
10 GB active storage
1 TB query processing/month
```

Important limitations:

- tables/views/partitions automatically expire after 60 days;
- streaming is not supported;
- DML is not supported;
- BigQuery Data Transfer Service is not supported.

Therefore:

> Do not use the Sandbox as PortFlow's real-time streaming backbone.

Use it as an analytical showcase.

Example:

```text
Local Gold Parquet
       ↓
load/export workflow
       ↓
BigQuery Sandbox
       ↓
analytical SQL
       ↓
screenshots / benchmarks / documented queries
```

---

# 40. Databricks Free Edition

Databricks Free Edition is a no-cost environment for personal learning and experimentation.

It replaced the legacy Community Edition.

Good PortFlow use case:

```text
Parquet
   ↓
Databricks
   ↓
Bronze Delta
   ↓
PySpark
   ↓
Silver Delta
   ↓
Gold Delta
   ↓
SQL dashboard
```

Important:

Free Edition is quota-limited and serverless-only.

Current documented limitations include restrictions around:

- compute size/usage;
- SQL warehouse capacity;
- concurrent jobs;
- active pipelines;
- networking;
- enterprise administration.

If the quota is exceeded, compute can become unavailable until the relevant limit resets.

Therefore Databricks Free Edition is ideal for:

```text
learning
portfolio demos
notebooks
pipeline experiments
Delta architecture
SQL analysis
```

not production hosting.

---

# 41. Microsoft Fabric Lab

Microsoft currently offers a 60-day Fabric trial.

The current trial describes:

```text
64 CU trial capacity
up to 1 TB OneLake storage
```

Use it only after the local PortFlow system works.

Suggested experiment:

```text
Gold Parquet
    ↓
OneLake
    ↓
Lakehouse
    ↓
PySpark
    ↓
Warehouse
    ↓
Power BI / Fabric reporting
```

Save:

- notebooks;
- screenshots;
- documentation;
- architecture comparisons.

When the trial ends, PortFlow continues working locally.

---

# 42. Snowflake Lab

Snowflake currently advertises a 30-day AI Data Cloud trial with $400 of free credits.

Use it for a short ingestion experiment:

```text
Parquet
   ↓
stage
   ↓
COPY INTO
   ↓
RAW
   ↓
STAGING
   ↓
ANALYTICS
```

Learn:

```text
warehouses
stages
COPY INTO
resource monitors
auto-suspend
query profile
```

Snowflake should remain optional because the trial is time-limited.

---

# 43. GitHub Pages Project Site

Host static documentation for PortFlow from the public repository.

Possible project site:

```text
<username>.github.io/portflow/
```

Pages:

```text
Home
Architecture
Data Model
Streaming
Batch
Quality
Observability
Benchmarks
Cloud Labs
Dashboard Gallery
Runbook
GitHub
```

GitHub Pages is available for public repositories on GitHub Free.

Use it for documentation—not a commercial SaaS application.

---

# 44. Repository Structure

Recommended final structure:

```text
portflow/
│
├── README.md
├── LICENSE
├── Makefile
├── docker-compose.yml
├── .env.example
├── pyproject.toml
│
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── streaming.md
│   │   ├── batch.md
│   │   └── cloud-mapping.md
│   ├── adr/
│   ├── diagrams/
│   ├── data-contracts/
│   ├── data-model/
│   ├── runbooks/
│   └── benchmarks/
│
├── generators/
│   ├── equipment/
│   ├── alarms/
│   ├── incidents/
│   ├── containers/
│   └── voyages/
│
├── ingestion/
│   ├── batch/
│   └── streaming/
│
├── streaming/
│   ├── producers/
│   ├── consumers/
│   ├── schemas/
│   └── dlq/
│
├── data/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── dbt/
│   ├── models/
│   ├── macros/
│   ├── snapshots/
│   └── tests/
│
├── spark/
│   ├── jobs/
│   └── tests/
│
├── orchestration/
│   └── dagster/
│
├── warehouse/
│   ├── postgres/
│   ├── duckdb/
│   └── bigquery/
│
├── quality/
│
├── observability/
│   ├── prometheus/
│   └── grafana/
│
├── dashboards/
│   └── metabase/
│
├── infrastructure/
│   ├── local/
│   └── terraform/
│       └── gcp/
│
├── cloud/
│   ├── gcp/
│   ├── databricks/
│   ├── fabric/
│   └── snowflake/
│
├── benchmarks/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── data_quality/
│   └── end_to_end/
│
└── .github/
    └── workflows/
```

---

# 45. Development Roadmap

Do **not** build everything simultaneously.

## V1 — Domain Foundation

Build:

- PostgreSQL;
- schema migrations;
- realistic seed data;
- equipment simulator;
- business glossary.

Goal:

> Understand the terminal domain and have reliable sources.

---

## V2 — Batch Pipeline

Build:

```text
PostgreSQL / CSV
      ↓
Python
      ↓
Bronze Parquet
      ↓
Silver
      ↓
Gold
```

Add:

- incremental extraction;
- watermark table;
- batch metadata.

---

## V3 — Analytics Engineering

Add:

- DuckDB;
- dbt;
- star schema;
- Gold marts;
- SCD Type 2;
- advanced SQL.

---

## V4 — Streaming

Add:

- Redpanda;
- producer;
- consumers;
- event contracts;
- DLQ;
- deduplication;
- late events.

---

## V5 — Reliability

Add:

- idempotency;
- backfills;
- retries;
- data quality;
- failure injection;
- reconciliation.

---

## V6 — Orchestration

Add:

- Dagster;
- schedules;
- assets;
- partitioning;
- run history;
- retry policy.

---

## V7 — Operations

Add:

- Prometheus;
- Grafana;
- Metabase;
- SLIs/SLOs;
- Control Tower dashboards.

At this point PortFlow is already a complete portfolio project.

---

## V8 — Engineering Platform

Add:

- Terraform;
- GitHub Actions;
- automated tests;
- documentation publication;
- release tags.

---

## V9 — Big Data

Add:

- PySpark;
- 10M-event benchmark;
- transformation comparison.

---

## V10 — GCP Analytics

Add:

- BigQuery Sandbox;
- analytical SQL;
- cost/scanned-byte experiments;
- cloud architecture documentation.

---

## V11 — Databricks

Add:

- Free Edition workspace;
- PySpark notebook;
- Delta tables;
- pipeline demo;
- SQL/dashboard output.

---

## V12 — Optional Labs

Only after everything above:

- Fabric;
- Snowflake.

---

# 46. Milestones & Acceptance Criteria

## Milestone 1 — Source Ready

Acceptance:

- PostgreSQL schema deploys cleanly;
- seed command works;
- simulator creates consistent domain events;
- tests pass.

---

## Milestone 2 — Batch Ready

Acceptance:

- incremental source extraction;
- Parquet Bronze;
- cleaned Silver;
- Gold marts;
- rerun does not duplicate records.

---

## Milestone 3 — Streaming Ready

Acceptance:

- telemetry producer publishes continuously;
- consumer validates;
- invalid messages go to DLQ;
- duplicates are handled;
- late events are identified;
- restart does not lose committed data.

---

## Milestone 4 — Analytics Ready

Acceptance:

- star schema;
- SCD Type 2;
- operational KPIs;
- dbt tests;
- Metabase dashboard.

---

## Milestone 5 — Platform Ready

Acceptance:

- orchestration;
- monitoring;
- Grafana;
- SLO metrics;
- CI pipeline;
- documented runbook.

---

## Milestone 6 — Portfolio Ready

Acceptance:

- architecture diagram;
- screenshots;
- benchmark results;
- one-command local setup;
- public documentation;
- resume-ready description.

---

# 47. Portfolio & Resume Positioning

A weak description would be:

> Built an ETL project using Python.

A strong description:

> **PortFlow — Real-Time Logistics Data Platform**  
> Designed and implemented a production-style batch and streaming data platform for container-terminal operations, ingesting PostgreSQL datasets and equipment telemetry into Bronze/Silver/Gold layers using Python, Redpanda, Parquet, dbt and PySpark. Built incremental and idempotent pipelines with watermarking, late-event handling, DLQs, backfills, SCD Type 2 dimensions and automated data-quality checks; exposed terminal throughput, equipment reliability, MTTR/MTBF and dwell-time KPIs through analytical marts and operational dashboards. Containerized the platform with Docker, orchestrated workflows with Dagster, added Prometheus/Grafana observability, CI/CD through GitHub Actions and cloud analytics experiments using BigQuery and Databricks.

Do not claim a cloud feature until it is actually implemented.

---

# 48. Interview Stories

PortFlow should create multiple concrete engineering stories.

## Story 1 — Duplicate events

Problem:

```text
at-least-once delivery generated duplicate alarm events
```

Solution:

```text
stable event IDs
Bronze preservation
Silver window deduplication
idempotent merge
```

---

## Story 2 — Late events

Problem:

Telemetry arrives 10 minutes late.

Solution:

```text
event time
ingestion time
late-event classification
recomputation window
```

---

## Story 3 — Incremental extraction

Problem:

Reloading millions of operational rows every run is wasteful.

Solution:

```text
updated_at watermark
composite cursor
safe watermark commit
```

---

## Story 4 — Historical equipment changes

Problem:

Equipment moves from terminal TM1 to TM2.

Solution:

```text
SCD Type 2
surrogate keys
valid_from / valid_to
historical facts preserved
```

---

## Story 5 — Pipeline failure

Problem:

Streaming consumer is unavailable.

Solution:

```text
broker retention
consumer offset
restart
catch-up
lag observation
```

---

## Story 6 — Bad operational records

Problem:

Negative container weights and invalid timestamps.

Solution:

```text
validation rules
quarantine
quality metrics
Gold protection
```

---

## Story 7 — Performance

Problem:

Large analytical scans are slow.

Solution:

```text
Parquet
partitioning
DuckDB
PySpark benchmark
BigQuery scanned-byte analysis
```

---

# 49. What Not to Build

Avoid building:

```text
GCP + AWS + Azure simultaneously
```

Do not implement every equivalent service.

Avoid adding technology only because it appears in a job description.

Bad:

```text
Airflow
Dagster
Prefect
Mage
```

all in one repository.

Pick one.

Bad:

```text
Kafka
Redpanda
RabbitMQ
Pulsar
```

all for the same pipeline.

Pick one.

Bad:

```text
Metabase
Superset
Looker
Power BI
Grafana
```

all as identical BI tools.

Use:

```text
Metabase -> business BI
Grafana  -> engineering observability
```

Cloud products should have specific learning objectives.

---

# 50. Final Recommended Scope

## Absolutely implement

```text
Python
SQL
PostgreSQL
Redpanda
Parquet
DuckDB
dbt Core
Dagster
Docker
GitHub Actions
Metabase
Prometheus
Grafana

Batch ETL
Streaming
Bronze / Silver / Gold
Incremental ingestion
Idempotency
Watermarks
Backfills
Late events
Out-of-order events
DLQ
Data quality
Dimensional modeling
SCD Type 2
Observability
SLOs
Testing
CI/CD
```

---

## Implement after core platform works

```text
PySpark
BigQuery Sandbox
Databricks Free Edition
Terraform GCP profile
```

---

## Optional only

```text
Microsoft Fabric trial
Snowflake trial
```

---

# 51. Verified $0 / Free-Tier Assumptions

> Verified against official vendor documentation in September 2026. Free offerings and limits can change; re-check before implementation.

## BigQuery Sandbox

Current official documentation states:

- no credit card/billing account required for Sandbox use;
- 10 GB active storage;
- 1 TB processed query data per month;
- tables/views/partitions expire after 60 days;
- streaming is unsupported;
- DML is unsupported;
- BigQuery Data Transfer Service is unsupported.

Therefore BigQuery Sandbox is excellent for analytical demos but should not be the streaming foundation.

---

## Google Cloud Free Tier

Google Cloud currently lists free monthly allowances for services including:

- BigQuery;
- Cloud Run;
- Pub/Sub;
- Cloud Storage.

However, most normal GCP usage requires billing to be enabled and charges can apply beyond free allowances.

Therefore PortFlow should not rely on those free allowances to remain permanently cost-safe.

---

## Databricks Free Edition

Current official Databricks documentation describes Free Edition as:

- no-cost;
- designed for learning and experimentation;
- serverless-only;
- quota-limited;
- non-commercial;
- subject to fair-use limits.

Therefore it is a good portfolio/lab environment, not permanent production infrastructure.

---

## Microsoft Fabric

Current Microsoft documentation advertises:

```text
60-day free trial
64 CU trial capacity
up to 1 TB OneLake storage
```

Use temporarily.

---

## Snowflake

Current Snowflake documentation advertises:

```text
30-day experience
$400 free credits
```

Use temporarily.

---

## GitHub Actions

Current GitHub documentation states standard GitHub-hosted runners are free for public repositories.

This makes a public PortFlow repository well suited for CI.

---

## GitHub Pages

GitHub Pages is available for public repositories under GitHub Free.

Use for the project's static documentation and portfolio site.

---

## Docker Desktop

Docker currently states Docker Desktop is free for:

- personal use;
- education;
- non-commercial open-source projects;
- qualifying small businesses.

For this personal portfolio project, it fits the free-use category.

---

## Redpanda Community Edition

Redpanda documentation describes Community Edition as free and source-available for self-hosted use, subject to its license restrictions.

Use it as PortFlow's local Kafka-compatible broker.

---

## Metabase

Metabase provides a free self-hosted Open Source edition and an official Docker image.

Use it for the local business dashboard.

---

# 52. Useful Official References

## Google Cloud / BigQuery

- BigQuery Sandbox  
  https://docs.cloud.google.com/bigquery/docs/sandbox

- BigQuery pricing / free usage  
  https://cloud.google.com/bigquery/pricing

- Google Cloud Free Tier  
  https://cloud.google.com/free

---

## Databricks

- Databricks Free Edition  
  https://docs.databricks.com/aws/en/getting-started/free-edition

- Free Edition limitations  
  https://docs.databricks.com/aws/en/getting-started/free-edition-limitations

---

## Microsoft Fabric

- Fabric free trial  
  https://www.microsoft.com/en/microsoft-fabric/getting-started

---

## Snowflake

- Snowflake trial  
  https://www.snowflake.com/en/snowflake-trial/

---

## GitHub

- GitHub Actions billing  
  https://docs.github.com/en/actions/concepts/billing-and-usage

- GitHub Pages  
  https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages

---

## Docker

- Docker Desktop license  
  https://docs.docker.com/subscription/desktop-license/

---

## Redpanda

- Redpanda licensing  
  https://docs.redpanda.com/streaming/current/get-started/licensing/overview/

---

## Metabase

- Metabase OSS  
  https://www.metabase.com/start/oss

- Metabase Docker  
  https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker

---

## Apache Superset

- Apache Superset  
  https://superset.apache.org/

---

# Closing Vision

PortFlow should ultimately tell one coherent engineering story:

> **A realistic real-time logistics data platform that processes terminal operations data through reliable batch and streaming pipelines, builds trusted analytical models, handles real-world failure modes, exposes operational KPIs, measures its own health and can be demonstrated locally or through carefully selected free cloud environments.**

The project's strength should come from **depth, reliability and engineering decisions**, not from listing the largest possible number of cloud products.

The ideal final demonstration is:

```text
git clone
   ↓
docker compose up
   ↓
seed operational system
   ↓
start terminal simulator
   ↓
events appear in Redpanda
   ↓
Bronze receives data
   ↓
Silver validates/deduplicates
   ↓
Gold builds KPIs
   ↓
Metabase shows terminal operations
   ↓
Grafana shows pipeline health
   ↓
Dagster shows orchestration
   ↓
GitHub Actions verifies everything
```

with BigQuery and Databricks available as credible cloud extensions.

That is the version of PortFlow worth building.
