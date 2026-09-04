# PF-025 Failure-Injection Coverage Design

## Goal

PF-025 adds repeatable evidence for the recovery guarantees already promised by
PortFlow. The tests must prove that a failed or invalid input is isolated, that
previous valid state is preserved where promised, and that unaffected views do
not fabricate values.

## Scope

The work covers two boundaries:

1. The local Python pipeline from Bronze extraction through Silver validation
   and snapshot publication.
2. The frontend snapshot loader and its route-level data states.

The tests remain local and deterministic. They may use the existing PostgreSQL
fixture for integration behavior, temporary directories for filesystem failure
simulation, and injected frontend fetchers. They will not require a browser
runner, network access, or a hosted deployment.

## Failure matrix

| Boundary | Injected failure | Required evidence |
|---|---|---|
| Bronze extraction | Partition write fails before commit | Previous cursor remains unchanged; no partial committed partition is treated as available. |
| Bronze/Silver quality | Duplicate row or invalid reference | Row is quarantined with a stable reason code; Silver excludes it; Bronze = Silver + quarantine. |
| Cursor state | Cursor replacement fails | Existing cursor file remains readable and unchanged; temporary state is cleaned up. |
| Public snapshot | Dataset write or validation fails | Existing published snapshot remains intact; incomplete staging output is not promoted. |
| Frontend manifest | Missing, malformed, or unavailable manifest | Loader returns the documented failure kind and the app exposes a visible recovery state. |
| Frontend dataset | Missing or malformed optional dataset | Affected view reports its state while Overview and other valid datasets remain usable. |
| Freshness | Manifest is stale | UI labels the snapshot stale and does not present it as current. |
| Recovery | Valid snapshot follows a failed load | Last valid cached snapshot is retained and restored without fabricated KPI values. |

PF-025 does not add new failure semantics. If a test exposes behavior that
contradicts the existing contract, the smallest production fix is allowed and
must be covered by the failing test.

## Test architecture

`tests/resilience/` will contain focused Python tests grouped by contract:

- ingestion write/cursor preservation tests use temporary paths and injected
  replacement or write callbacks;
- Silver tests use small controlled records and assert reason codes, output
  membership, and reconciliation totals;
- export tests use a valid prior snapshot plus a failing staged write or invalid
  document and assert immutability of the prior snapshot.

`web/e2e/failure-states.spec.tsx` will exercise the real `App` and
`loadSnapshot` with an injected fetcher. Each case will define only the
manifest and dataset responses needed for that state, then assert visible
status text, preservation of valid route content, and absence of invented
metrics. The suite will be excluded from normal frontend tests unless the
failure-state fixture mode is explicitly enabled, matching PF-024's isolated
generated-snapshot suite.

## Data flow and isolation

Python failures are injected below public side effects: temporary staging and
cursor paths are used before any committed output is changed. Frontend cases
are pure in-memory fetch scenarios. The cache is cleared between tests, except
for the explicit recovery case, which seeds one valid snapshot and then
verifies that a later failed load returns that snapshot with the expected age
or stale indication.

No test may silently substitute a KPI when a required dataset is unavailable.
Assertions should use the existing typed state values (`unavailable`,
`malformed`, `empty`, and stale behavior) and stable user-visible labels.

## Verification and commit slices

Tests are written first and observed failing for the intended reason. The
implementation proceeds in these slices:

1. Add Python resilience tests and make the pipeline contracts pass.
2. Add frontend failure-state tests and make the existing loader/cache behavior
   pass.
3. Run the full Python and frontend suites, typecheck, production build, and
   Pages-path verification.
4. Update the backlog to PF-026 and record the implementation commits.

PF-025 is complete only when each failure matrix row has executable evidence,
the normal suites remain green, and the repository has no uncommitted test
artifacts.

## Out of scope

- Cloud or deployment failure simulation.
- Browser automation or visual redesign.
- New retry policies, telemetry systems, or resilience abstractions without a
  failing contract test that requires them.
- Failure injection for PF-026 performance budgets or later CI/deployment work.
