# PF-121 Design Specification — Consistent Filter Recovery

**Status:** Ready for implementation  
**Date:** 2026-09-23  
**Parent slice:** PF-120 published snapshot filter scope

## Problem

PortFlow now discloses the validated snapshot scope and offers a reset action
when the Overview route cannot satisfy the selected terminal or date range.
Equipment and Incidents still stop at route-specific unavailable or empty
states. A user can therefore select an unsupported global filter, move to an
operational route, and lose the recovery path that exists on Overview.

## Goal

Make unsupported global filters recoverable in every operational data view that
is bounded by the published snapshot: Overview, Equipment, and Incidents.

## User outcome

When the selected terminal or range is outside the validated snapshot scope,
the route must:

1. explain that the selected filters are unsupported;
2. show the same published terminal and UTC period already shown in the global
   filter band;
3. hide route data that would imply a supported result; and
4. offer `Reset filters to published scope`, preserving the current route hash
   and returning keyboard focus to the main content.

## Scope and invariants

- Reuse `SnapshotFilterScope` as the single source of truth for the terminal ID,
  terminal label, and UTC period label.
- Treat `all` as a supported terminal selection and `24h` as the supported
  published range.
- Apply the same recovery component and copy structure to all three bounded
  operational views.
- Keep Data Health and Live Demo independent of global filter matching because
  their contracts are snapshot-level trust and replay respectively.
- Do not change the public snapshot schema, API boundary, URL key names, or
  backend pipeline.
- Do not render equipment rows, incident metrics, incident trend data, or
  detail views while the global filter scope is unsupported.

## Interaction and accessibility

- The recovery action is a native button with a stable accessible name.
- The published scope is exposed as readable text, not only color or iconography.
- After reset, focus moves to `#main-content`, matching route-navigation
  behavior and avoiding focus loss when the recovery state unmounts.
- Existing route-specific not-found and dataset-unavailable states remain
  unchanged when the global filter scope is valid.

## Acceptance criteria

- `SnapshotFilterScope` exposes the validated terminal ID in addition to its
  existing labels.
- A shared predicate identifies `all`/`24h` plus the snapshot terminal as the
  supported global filter scope.
- Overview, Equipment, and Incidents use one shared recovery state for
  unsupported global filters.
- Reset clears only global filter query parameters, preserves the active hash,
  restores `all`/`24h`, and focuses main content.
- Tests cover supported and unsupported terminal/range combinations for
  Equipment and Incidents, plus regression coverage for Overview and the
  shared scope helper.
- Existing dataset, detail, URL, accessibility, build, budget, and Lighthouse
  checks continue to pass.

## Out of scope

- Adding historical snapshot selection or a multi-period backend.
- Changing terminal or range option lists.
- Adding reset actions for local equipment search, sorting, incident severity,
  or detail identifiers.
- Changing the public deployment or pipeline contracts.
