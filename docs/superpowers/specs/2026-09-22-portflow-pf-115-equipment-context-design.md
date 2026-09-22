# PF-115 Equipment Detail Context Design

**Date:** 2026-09-22  
**Parent:** PF-114 Snapshot Freshness  
**Status:** Approved for implementation under the standing PortFlow workflow

## Problem

The equipment route identifies the selected asset, but its detail view stops at a sparse metric grid. An operator can see the current state without seeing the recent event context that explains how the asset reached that state. The existing public snapshot already contains replay events and incident records, so the product can provide useful context without changing the published data contract or adding a backend dependency.

## Goal

Make an equipment detail view useful for diagnosis by showing a deterministic, readable activity timeline and related incidents for the selected equipment, while preserving the current route, filter, accessibility, and snapshot-freshness behavior.

## Scope

### In scope

- Derive selected-equipment activity from the existing `SnapshotV1.event_replay` array.
- Collapse consecutive replay events with the same `state` and `available` value so repeated telemetry does not overwhelm the view.
- Render event timestamp, state, and availability in chronological order.
- Derive related incidents from the existing `IncidentDatasetState` and link each record to the existing incident detail route.
- Render honest absent, empty, unavailable, malformed, and no-match states for both datasets.
- Thread the optional snapshot data through `App`, `EquipmentPage`, and `EquipmentDetail` without changing the public JSON schema.
- Preserve deep links, back navigation, focus restoration, global filters, responsive layout, reduced-motion behavior, and the current metric grid.
- Add unit/component/route regression tests and update the product backlog and changelog.

### Out of scope

- New API endpoints, database queries, polling, streaming, or hosted data changes.
- Changes to `event-replay.json`, `incidents.json`, or the `SnapshotV1` contract.
- A new charting dependency.
- Redesigning the incident detail screen or the live-demo replay controls.
- Editing, acknowledging, or mutating incidents from the equipment view.

## User flow

1. An operator opens Equipment and selects an asset.
2. The detail view keeps the existing summary metrics at the top.
3. An `Equipment activity` section explains recent state transitions for that asset. It shows a loading-free deterministic state because the data is a static snapshot.
4. A `Related incidents` section lists incidents for the asset, newest opened first. Selecting one uses the existing incident deep link and route behavior.
5. If a dataset is missing or malformed, the view explains what is unavailable instead of implying that no activity or incidents exist.
6. The back action returns to the same equipment fleet context and restores focus as it does today.

## Data behavior

### Activity derivation

Add a pure helper that accepts `ReplayEventV1[] | undefined` and an equipment id and returns a stable list of activity entries.

- `undefined` means the replay dataset is absent.
- An empty array means the replay dataset is present but empty.
- A non-empty array with no selected-equipment events means there is no matching activity.
- Matching events are ordered by `event_timestamp` ascending, with original array index as a deterministic tie-breaker.
- Consecutive matching events are collapsed only when both `state` and `available` are unchanged.
- The original input array and event objects are never mutated.

### Incident derivation

Use the existing `IncidentDatasetState` union and filter only `status: "ready"` records whose `equipment_id` matches the selected asset.

- Sort matching incidents by `opened_at` descending, with incident id as a deterministic tie-breaker.
- Preserve the dataset's existing semantic status: `absent`, `empty`, `unavailable`, and `malformed` remain distinguishable from a valid ready dataset with no matches.
- Do not fabricate a “clear” or “healthy” state when the incident dataset is absent or unavailable.

## Component boundaries

- `web/src/features/equipment/equipmentContext.ts`: pure derivation and formatting-safe view models; no React or browser APIs.
- `web/src/features/equipment/EquipmentContext.tsx`: accessible activity and related-incident sections; owns only presentation of the derived states.
- `web/src/features/equipment/EquipmentDetail.tsx`: composes the existing metric list with `EquipmentContext` and passes the selected equipment id.
- `web/src/features/equipment/EquipmentPage.tsx`: passes optional replay and incident datasets when rendering the selected detail.
- `web/src/app/App.tsx`: supplies `snapshot.event_replay` and `snapshot.incidents` to the equipment route.
- `web/src/styles.css`: adds responsive context-section styles using the existing visual language and no new dependency.

The context component must remain usable with omitted optional props so existing equipment-page tests and an old snapshot continue to render the current summary without crashing.

## Accessibility and interaction

- Use headings that form a logical hierarchy under the equipment detail heading.
- Use a list or definition-list structure for activity and incident records rather than visually styled paragraphs only.
- Keep timestamps readable in UTC and include sufficient text labels for state and availability; color is supplementary.
- Preserve keyboard focus on the existing back button and focus restoration after returning to the fleet.
- Incident records must be keyboard reachable links with descriptive accessible names.
- Do not add hover-only information.
- Respect the existing reduced-motion media query and responsive breakpoints.

## Verification

- Pure helper tests cover undefined, empty, no-match, chronological ordering, stable ties, consecutive collapse, and input immutability.
- Component tests cover ready, empty, absent, unavailable, malformed, and no-match states for incidents plus all replay states.
- Equipment detail tests verify the summary metrics remain present, related incident links use the existing route shape, and old optional-data usage remains safe.
- Equipment-page/App route tests verify snapshot data reaches the detail route and back/focus behavior is unchanged.
- Run focused Vitest tests, the full frontend test suite, typecheck, production build, budget checks, and the repository verification script before opening the PR.

## Acceptance criteria

- Selecting an equipment asset gives an operator recent, readable activity context without leaving the equipment route.
- Related incidents are limited to the selected asset and link to the existing incident detail route.
- Every absent, empty, unavailable, malformed, and no-match state is explicit and tested.
- No public snapshot fixture or schema changes are required.
- Existing route, accessibility, responsive, filter, focus, and freshness behavior remains green.
- The branch has a reviewable sequence of focused commits, green CI, and no new SonarCloud or CodeRabbit findings that block the PR.

## Commit slices

1. Add failing unit tests for activity and incident derivation.
2. Implement the pure derivation helpers.
3. Add component tests and render the honest data states.
4. Wire replay and incident datasets through the equipment route.
5. Add responsive styling and route regression coverage.
6. Update backlog/changelog and run the complete verification gate.
