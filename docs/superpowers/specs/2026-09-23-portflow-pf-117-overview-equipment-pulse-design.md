# PF-117 Overview Equipment Pulse Design

**Date:** 2026-09-23
**Parent:** PF-116 Incident Detail Context
**Status:** Approved for implementation under the standing PortFlow workflow

## Problem

The Overview page communicates an aggregate equipment availability value and
an hourly trend, but it does not show which published equipment records make
up that result. An operator who sees a degraded aggregate must leave Overview,
open Equipment, and search manually before they can inspect a likely cause.

## Goal

Add a compact equipment pulse to Overview so operators can move from the
aggregate availability signal to a small, deterministic set of equipment
records that deserve attention, without changing the static snapshot boundary.

## Scope

### In scope

- Derive a stable maximum of three records from the existing
  `EquipmentDatasetState`.
- Rank unavailable records first, then lower numeric availability, then higher
  numeric downtime, with equipment ID as the deterministic tie-breaker.
- Render equipment ID, terminal, current state, availability, and downtime in
  the existing Overview visual language.
- Link each equipment ID to the existing native route
  `?equipment=<id>#equipment`.
- Preserve explicit `absent`, `empty`, `unavailable`, and `malformed` dataset
  states instead of presenting missing evidence as a healthy fleet.
- Thread the optional equipment dataset from `SnapshotV1` into Overview.
- Add responsive styles, pure derivation tests, component tests, and an
  Overview route regression test.
- Update the product backlog and changelog after the verification gate passes.

### Out of scope

- New endpoints, database queries, polling, streaming, or snapshot schema
  changes.
- Replacing the Equipment fleet table, its filters, or its sorting behavior.
- New charts, client-side navigation dependencies, controls, or mutations.
- Inferring health from incident severity, state text, or aggregate values when
  an equipment metric is unavailable.

## User flow

1. An operator opens Overview and sees the aggregate availability and trend.
2. The `Equipment pulse` section explains that it is derived from the same
   published snapshot.
3. Up to three records are shown, with unavailable or lower-availability
   records first and downtime as a secondary signal.
4. Selecting an equipment ID follows the existing native Equipment detail
   route, preserving keyboard, modifier-click, and new-tab behavior.
5. If the equipment dataset is not published or cannot be read, the section
   explains the limitation instead of fabricating an empty or healthy state.

## Data behavior

Add a pure helper that accepts `EquipmentDatasetState | undefined` and returns
a discriminated view model.

- `undefined` returns `absent`.
- `empty`, `unavailable`, and `malformed` retain their exact semantic meaning.
- A ready dataset with no records returns `empty` so the UI remains honest even
  if a producer supplies an empty ready array.
- A ready dataset is copied before ranking; the source array and records are
  never mutated.
- Null availability and downtime sort after numeric values for their fields.
- The helper returns at most three original immutable record references in the
  deterministic attention order.

## Component boundaries

- `web/src/features/overview/overviewEquipmentPulse.ts`: pure derivation and
  safe formatting helpers; no React or browser APIs.
- `web/src/features/overview/OverviewEquipmentPulse.tsx`: accessible panel,
  status messages, metrics, and native equipment links.
- `web/src/features/overview/OverviewPage.tsx`: composes the pulse after the
  aggregate availability card.
- `web/src/app/App.tsx`: supplies `snapshot.equipment` to Overview.
- `web/src/styles.css`: responsive pulse styling using existing tokens and
  breakpoints.

## Accessibility and interaction

- Use a named section heading and a list for the ranked records.
- Give every equipment link an explicit accessible name such as
  `Open equipment QC-001`.
- Keep state, percentages, units, and unavailable values as text; color is
  supplementary.
- Do not cancel native anchor behavior.
- Keep the existing Overview focus, freshness, filter, and reduced-motion
  behavior unchanged.

## Verification

- Pure helper tests cover every dataset state, ranking, null ordering, limit,
  deterministic ties, and input immutability.
- Component tests cover the ready panel, native route-shaped links, formatting,
  and every honest non-ready state.
- App route coverage verifies snapshot equipment data reaches Overview.
- Run focused Vitest tests, the full frontend suite, typecheck, production
  build, budget checks, `git diff --check`, and the repository verification
  script before opening the PR.

## Acceptance criteria

- Overview makes the aggregate availability actionable with up to three
  snapshot-backed equipment records.
- The ranking is deterministic, documented, and tested.
- Equipment IDs are keyboard-reachable native links to the existing route.
- All absent, empty, unavailable, and malformed states are explicit and
  tested.
- Existing Overview KPIs, filters, freshness, static delivery, and public
  snapshot behavior remain green.
- The branch has focused commits, green CI, and no blocking SonarCloud or
  CodeRabbit findings.

## Commit slices

1. Add the PF-117 spec and implementation plan.
2. Add failing unit tests for pulse derivation.
3. Implement the pure derivation helper.
4. Add the pulse component and component tests.
5. Thread snapshot data through Overview and add route regression coverage.
6. Add responsive styling and close the backlog/changelog evidence.
7. Run the complete verification gate before opening the PR.
