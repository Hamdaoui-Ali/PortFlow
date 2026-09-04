# PF-024 End-to-End Pipeline Reconciliation Design

## Status

Approved design for implementation planning.

## Goal

Prove that one deterministic PortFlow input survives the complete path from
PostgreSQL through Bronze, Silver, quarantine, Gold, public JSON export, and
the browser UI without count, hash, timestamp, or KPI drift.

## Scope

PF-024 adds reconciliation coverage for the existing local pipeline and the
existing frontend snapshot boundary. It does not change production pipeline
behavior, schemas, routes, data, deployment, or the browser interaction model.

The tests cover the five published datasets already required by the V1 public
contract: `overview`, `equipment`, `incidents`, `event_replay`, and `quality`.

## Test architecture

The Python test begins with the existing deterministic PostgreSQL seed and runs
the existing pipeline stages:

```text
PostgreSQL → Bronze → Silver/quarantine → dbt Gold → public JSON
```

It writes to pytest-managed temporary directories. The test reads the
generated `manifest.json` and every referenced dataset directly from that
temporary export.

The browser test consumes the same exported JSON boundary through an injected
fetcher and the existing `loadSnapshot` function. It renders the real `App`
with the resulting `SnapshotV1`; it does not duplicate feature markup or use a
second application. No browser E2E runner is introduced.

## Reconciliation assertions

The Python test must verify:

- all five manifest dataset entries exist;
- every manifest SHA-256 matches the exact exported dataset bytes;
- snapshot ID and source-period timestamps match the deterministic run;
- expected Bronze, Silver, quarantine, Gold, and public record counts;
- expected overview KPIs, including throughput, availability, utilization,
  active incidents, and critical alarms;
- a repeated pipeline run is byte-stable and respects the immutable snapshot
  boundary.

The browser test must verify that the exported files load through
`loadSnapshot` and that the real application displays values from that exact
snapshot:

- Overview displays the expected availability and throughput;
- Equipment displays the expected equipment record ID;
- Incidents displays the expected incident ID;
- Live Demo displays the expected replay event;
- Data Health displays the expected quality and reconciliation evidence.

Expected values come from the deterministic fixture and the generated export;
they are not hidden in production components or replaced with broad
“renders successfully” assertions.

## Failure behavior

Failures must identify the earliest broken boundary:

- pipeline-stage errors preserve the existing `PipelineError` behavior;
- count mismatches identify the layer and expected/actual count;
- hash mismatches identify the dataset path;
- manifest, dataset, or schema failures identify the exported path or
  contract;
- browser failures identify the route and missing or incorrect displayed
  value.

The tests must not disable reconciliation assertions, skip required datasets,
or fabricate a browser-only snapshot when the generated export is incomplete.
Temporary pipeline and browser artifacts are isolated in test-managed
directories and are removed after each run.

## Files and boundaries

Create:

- `tests/e2e/test_pipeline_reconciliation.py`
- `web/e2e/reconciliation.spec.tsx`

Modify `docs/product/BACKLOG.md` only for final tracking. Production source,
snapshot schemas, routes, public data, and test-support interfaces remain
unchanged. After verification, update the backlog so PF-025 becomes the next
action.

## Verification and completion

PF-024 is complete only when:

- the new Python reconciliation test passes against the seeded database;
- the new browser reconciliation test passes against the temporary export;
- the full Python test suite passes;
- the full frontend test suite passes;
- TypeScript typecheck passes;
- the `/PortFlow/` production build passes;
- Pages-path verification passes;
- `git diff --check` passes.

Separate commits will preserve the Python test, browser test, and backlog
advancement as reviewable slices.

## Non-goals

- adding a browser automation framework;
- changing pipeline implementation or public snapshot schemas;
- adding new metrics, routes, or data;
- testing failure injection, which remains PF-025;
- replacing existing component and integration tests.
