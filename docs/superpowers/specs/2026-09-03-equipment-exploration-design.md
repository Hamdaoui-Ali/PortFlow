# PF-018 Equipment Exploration Design

**Status:** Draft for review
**Date:** 2026-09-03
**Scope:** Fleet-table-first equipment exploration with detail routing

## Goal

Give an operations manager a reliable path from the equipment fleet to one
asset's current operating picture. The first release of this feature starts
with a searchable, sortable fleet table and lets the user open a detail view
for a selected equipment record.

## Constraints

- Keep the public product static and browser-only.
- Use only validated snapshot data; do not calculate or invent missing values
  in the UI.
- Preserve the approved PortFlow visual system: divider-led surfaces, compact
  tables, deep navy text, cobalt/teal analytical accents, and no decorative
  card grid.
- Reuse global terminal and date-range filter state.
- Preserve the existing loading, unavailable, malformed, empty, and stale
  recovery behavior.
- Keep the feature usable with the current public fixture, which contains one
  equipment record.

## Recommended approach

Use a small page registry and feature-local equipment modules instead of
putting equipment behavior directly in `App` or introducing a routing
dependency. The shell will continue to own navigation and global filters;
the equipment feature will own dataset interpretation, table state, and detail
selection.

## Architecture

### Snapshot contract

Add an equipment record schema with these fields:

- `equipment_id`
- `terminal_id`
- `current_state`
- `available`
- `availability`
- `utilization`
- `downtime_minutes`
- `alarm_count`
- `mttr_minutes`
- `mtbf_hours`

The manifest's optional `equipment` dataset is fetched and validated by the
snapshot loader. A failed optional equipment fetch must not invalidate the
Overview snapshot. When the equipment dataset is malformed or unavailable,
the Equipment page reports that state; it does not display partial rows.

### Page routing

Use the existing hash navigation. `#overview` remains the default route and
`#equipment` renders the equipment feature. A selected equipment record uses
an equipment hash/query state that can be copied and revisited, while a clear
back link returns to the fleet view. Unknown hashes fall back to the Overview
page.

### Feature modules

The feature is divided into focused units:

- `equipmentData`: schema and typed record boundary.
- `equipmentTable`: filtering, sorting, and table rendering.
- `EquipmentPage`: page-level empty/loading/error states and selection state.
- `EquipmentDetail`: selected-record summary and return navigation.
- URL state helpers: equipment search, sort column, sort direction, and
  selected equipment ID.

Pure filtering and sorting helpers must be independently testable. React
components should receive records and state through props where practical.

## User flow

1. User selects `Equipment` in either navigation surface.
2. The page loads the validated equipment records already attached to the
   current snapshot.
3. User searches by equipment ID; the table updates without a network call.
4. User selects a sortable column; the first selection sorts ascending and a
   second selection reverses direction.
5. User selects an equipment ID; the URL preserves the selected record and a
   detail view opens.
6. User follows the back link; the fleet table returns with search and sort
   state intact.

## Table and detail behavior

The table columns are:

`Equipment ID`, `Terminal`, `State`, `Availability`, `Utilization`,
`Downtime`, `Alarms`, and `MTTR`.

Numeric values use tabular formatting. Nullable metrics display `Unavailable`.
Availability and utilization render as percentages; downtime and MTTR render
in minutes. State communicates its meaning through text and a restrained
semantic color, never color alone.

The detail view shows the selected equipment ID, terminal, current state,
availability, utilization, downtime, alarm count, MTTR, and MTBF. It uses the
same definitions and stale-data notice patterns as the Overview.

## URL state

The equipment page uses URL parameters for `search`, `sort`, `direction`, and
`equipment`. Defaults are omitted from the URL. Invalid values are normalized
to safe defaults. Browser back/forward must restore the visible table or
detail selection without creating a second source of truth.

## Error and empty states

- Snapshot loading: show the existing shell and a loading status.
- Equipment dataset absent: show an explicit unavailable state explaining
  that no equipment dataset was published.
- Equipment dataset malformed: show a validation state and no rows.
- Valid dataset with zero rows: show an empty state with no fabricated count.
- Search with no matches: show a no-results state and preserve the search.
- Stale snapshot: show the existing last-valid-snapshot warning above the
  equipment content.
- Unknown equipment ID: show a detail-not-found state with a fleet-view link.

## Accessibility and responsive behavior

- Use a native table with a caption or accessible name, column headers, and
  sortable-header buttons that expose `aria-sort`.
- Use a labelled search input with a 44 px target.
- Make equipment IDs keyboard-focusable links or buttons with clear names.
- Keep status text visible and do not rely on color to convey state.
- On narrow screens, hide only lower-priority columns after confirming their
  information remains available in the detail view; do not transform rows
  into unrelated cards.
- Preserve focus visibility and the existing skip-link behavior.

## Testing strategy

Write tests before implementation for:

- equipment schema acceptance and rejection;
- optional equipment dataset loading and isolation from Overview failures;
- filtering by search and global terminal selection;
- stable ascending/descending sorting for text and numeric columns;
- URL state defaults, normalization, and back/detail navigation;
- table headers, `aria-sort`, keyboard selection, and accessible names;
- detail rendering and unknown-equipment handling;
- loading, absent, malformed, empty, no-results, and stale states;
- regression coverage for Overview and existing snapshot recovery.

Verification will include the full Vitest suite, TypeScript typecheck,
production build with `/PortFlow/`, Pages-path verification, and diff checks.

## Out of scope

- Editing equipment records.
- Live backend calls or polling.
- Equipment-specific time-series charts before a published equipment history
  dataset exists.
- Multi-terminal fixture expansion beyond what the snapshot provides.
- A client-side routing dependency.
