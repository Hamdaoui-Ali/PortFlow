# PF-120 Published snapshot filter scope

## Goal

Make the global filters honest and recoverable when the published snapshot covers
only a narrower terminal and time period than the available filter choices.

## Evidence and context

The published Overview currently offers `Tangier Terminal`, `Last 7 days`, and
`Last 30 days`, while the committed snapshot covers Casablanca Terminal and one
24-hour period. Selecting an unsupported choice correctly avoids fabricating
values, but leaves a large empty state and requires the visitor to discover how
to recover by changing a control manually.

The current filter band, warning state, URL query parameters, and visual language
are already established. PF-120 extends those existing boundaries; it does not
introduce a new route, backend request, or design system.

## User outcome

Before changing a filter, a visitor can see the terminal and source period that
the current published snapshot actually contains. If a visitor selects an
unsupported filter combination, the Overview explains that the selection is
outside the published scope and provides one native, keyboard-accessible action
to restore the supported filter state.

## In scope

- Derive a display-ready published scope from the validated snapshot.
- Show the scope beside the global filters after a snapshot is available,
  including when a cached snapshot is being shown after a refresh failure.
- Preserve the existing terminal and date-range choices for future snapshots;
  do not silently remove choices from the filter controls.
- Add a `Reset filters to published scope` button to the Overview mismatch state.
- Reset both React state and the URL query parameters while preserving the
  current hash route.
- Keep the existing no-fabrication behavior for unsupported combinations.
- Add pure helper, component, and integration coverage for the scope and reset
  behavior.

## Scope presentation

The filter band shows a compact note with the label `Published scope`, the
human-readable terminal name, and the UTC source period. The period is derived
from `manifest.source_period_start` and `manifest.source_period_end`, so the UI
does not hard-code the current fixture's date.

The mismatch state keeps its existing heading and adds:

> These filters do not match the published snapshot.

It then repeats the derived published scope and exposes a real button labelled
`Reset filters to published scope`. Clicking it selects `all` / `24h`, updates
the query string, preserves the current hash, and returns the normal Overview
content in the same interaction.

## Data and state boundaries

- Use the already validated `SnapshotV1`; no schema or public-data change is
  required.
- The scope helper must have deterministic output and a safe terminal-ID
  fallback for future snapshot values.
- Loading and unavailable states do not claim a published scope.
- Ready and stale-cache states may show the scope because both have a usable
  snapshot.
- Resetting filters changes only client-side filter state and the URL; it does
  not refetch the snapshot.

## Accessibility and responsive behavior

- The scope note is exposed as a short, named note without relying on color.
- The recovery control is a native `button`, has a visible label, and retains
  the existing focus treatment.
- The mismatch state remains readable when the filter band stacks at the mobile
  breakpoint.
- Existing select labels, URL semantics, focus restoration, and unsupported
  filter warning behavior remain unchanged.

## Out of scope

- Adding terminal or historical data to the public snapshot.
- Disabling or removing future filter choices.
- Changing the snapshot schema, data-health calculations, or navigation routes.
- Introducing a new Open Design artifact or a new visual language.

## Verification contract

- Pure helper tests cover the known terminal label, UTC period formatting, and
  fallback IDs.
- App tests cover scope visibility for a ready snapshot, hidden scope while
  loading, mismatch copy, URL-preserving reset, and restored Overview content.
- Frontend tests, typecheck, production build, performance budgets, Lighthouse,
  and the repository `verify_r2.ps1` gate pass before PR handoff.
