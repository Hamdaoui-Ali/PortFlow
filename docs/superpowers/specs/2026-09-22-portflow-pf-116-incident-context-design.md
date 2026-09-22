# PF-116 Incident Detail Context Design

**Date:** 2026-09-22
**Parent:** PF-115 Equipment Detail Context
**Status:** Approved for implementation under the standing PortFlow workflow

## Problem

The incident detail route explains the lifecycle of an incident, but the
affected equipment is presented only as plain text. An operator arriving from
an equipment incident link cannot inspect the equipment's current state,
availability, or utilization without manually returning to the fleet and
searching again. This makes the cross-entity workflow one-directional and
adds avoidable navigation work during diagnosis.

The current product audit found that the incident detail already has a clear
heading, severity, lifecycle fields, freshness notice, and reliable focus
placement. The missing piece is contextual equipment evidence and an obvious
next action.

## Goal

Make an incident detail useful for equipment triage by showing a compact,
snapshot-backed equipment context panel with a native link to the existing
equipment detail route.

## Scope

### In scope

- Derive the equipment record matching the selected incident's
  `equipment_id` from the existing `EquipmentDatasetState`.
- Render equipment ID, terminal, current state, availability, utilization,
  and downtime in the existing incident detail visual language.
- Link the equipment ID to `?equipment=<id>#equipment` using native anchor
  behavior so keyboard, modifier-click, and new-tab behavior remain intact.
- Preserve honest `absent`, `empty`, `unavailable`, `malformed`, and
  `no-match` states when equipment context cannot be shown.
- Thread the optional equipment dataset through `App`, `IncidentPage`, and
  `IncidentDetail` without changing `SnapshotV1` or public JSON files.
- Add responsive styles and unit/component/route regression tests.
- Update the backlog and changelog after the verification gate passes.

### Out of scope

- New APIs, database queries, polling, streaming, or snapshot schema changes.
- Editing, acknowledging, or mutating incidents or equipment.
- Reworking the incident table, incident filters, equipment fleet table, or
  live replay controls.
- A browser-history return contract from equipment detail back to the exact
  incident detail. The new link is an explicit cross-route inspection action;
  existing back controls and browser history remain unchanged.
- New charting or UI dependencies.

## User flow

1. An operator opens Incidents and selects an incident.
2. The incident detail keeps its existing lifecycle grid and severity.
3. An `Equipment context` section identifies the affected asset and shows the
   latest published equipment metrics available in the same snapshot.
4. Selecting the equipment ID opens the existing equipment detail route.
5. If equipment data is missing or cannot be matched, the panel explains the
   limitation instead of implying that the equipment is healthy or absent.

## Data behavior

Add a pure helper that accepts `EquipmentDatasetState | undefined` and an
equipment ID and returns a discriminated view model.

- `undefined` means the equipment dataset is absent.
- `status: "empty"`, `"unavailable"`, and `"malformed"` retain their exact
  semantic meaning.
- A ready dataset with no matching record returns `"no-match"`.
- A matching record returns a stable read-only projection; neither the dataset
  record nor its containing array is mutated.
- Equipment values remain snapshot values and are not inferred from incident
  severity or status.

## Component boundaries

- `web/src/features/incidents/incidentContext.ts`: pure derivation and safe
  formatting helpers; no React or browser APIs.
- `web/src/features/incidents/IncidentContextPanel.tsx`: accessible panel,
  status messages, metric list, and native equipment link.
- `web/src/features/incidents/IncidentDetail.tsx`: composes the panel below
  the incident lifecycle grid.
- `web/src/features/incidents/IncidentPage.tsx`: passes the optional
  equipment dataset to the selected detail.
- `web/src/app/App.tsx`: supplies `snapshot.equipment` to the incidents route.
- `web/src/styles.css`: responsive panel styling using existing tokens and
  breakpoints.

## Accessibility and interaction

- Use a heading under the incident detail heading and a definition list for
  equipment values.
- Give the equipment link an explicit accessible name such as `Open equipment
  QC-001`.
- Keep timestamps and numeric values readable with text labels and units;
  color is supplementary.
- Do not cancel the native link click, preserving keyboard activation and
  modifier-click behavior.
- Preserve the current incident heading focus behavior and reduced-motion
  rules.

## Verification

- Pure helper tests cover every dataset state, a matching record, no-match,
  and input immutability.
- Component tests cover the ready panel, route-shaped link, all honest error
  states, and the existing incident detail fields.
- Route tests verify snapshot equipment data reaches incident detail and a
  native link event is not prevented.
- Run focused Vitest tests, the full frontend suite, typecheck, production
  build, budget checks, `git diff --check`, and the repository verification
  script before opening the PR.

## Acceptance criteria

- An incident detail identifies its affected equipment and exposes current
  published context without leaving the route.
- The equipment ID is a keyboard-reachable native link to the existing route.
- All absent, empty, unavailable, malformed, and no-match states are explicit
  and tested.
- Existing lifecycle, freshness, focus, filters, static delivery, and public
  snapshot behavior remain green.
- The branch has focused commits, green CI, and no blocking SonarCloud or
  CodeRabbit findings.

## Commit slices

1. Add the PF-116 spec and implementation plan.
2. Add failing unit tests for equipment context derivation.
3. Implement the pure derivation helper.
4. Add the context panel and component tests.
5. Thread equipment data through the incident route and add navigation tests.
6. Add responsive styling and close the backlog/changelog evidence.
7. Run the complete verification gate before opening the PR.
