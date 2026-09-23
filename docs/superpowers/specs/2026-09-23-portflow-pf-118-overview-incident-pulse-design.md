# PF-118 Overview incident pulse

## Goal

Give an operator a short, trustworthy list of the incidents that need attention from the Overview route, with a native link to the existing incident lifecycle view.

## Context

The Overview already exposes an `Active incidents` KPI and an equipment pulse. The incident route already validates the optional incident dataset, supports `?incident=<id>#incidents`, and renders the lifecycle detail. The missing connection is a small, scan-friendly list that answers “which incidents?” without requiring a route change first.

The current visual audit showed that the Overview uses a quiet, document-like rhythm: section kicker, short heading, explanatory sentence, and bordered rows. The incident route uses the same cobalt/teal/amber status language and already provides the destination for each row.

## User outcome

From Overview, an operator can identify the three most important incidents in the selected published snapshot and open any one in the existing incident detail view. If incident data is missing or invalid, the Overview explains that fact without implying that no incidents exist.

## In scope

- Add an `OverviewIncidentPulse` component below the existing equipment pulse.
- Add a pure ranking/state helper in `overviewIncidentPulseData.ts`.
- Accept the existing optional `IncidentDatasetState`; do not add a network request or change the snapshot schema.
- Show at most three records.
- Rank records by:
  1. open status before resolved status;
  2. severity `CRITICAL`, then `MAJOR`, then `MINOR`;
  3. newest `opened_at` instant first;
  4. `incident_id` ascending as the deterministic tie-breaker.
- Show incident ID, severity, root cause, terminal/equipment context, lifecycle status, and the UTC opening time.
- Link each record with `?incident=<encoded-id>#incidents`.
- Preserve native browser navigation and the existing incident detail/focus behavior.
- Use an `output` element for non-ready dataset messages so status updates remain accessible without relying on a generic `div` role.
- Keep all new props and helper inputs read-only.

## Honest dataset states

| Input | Overview message |
|---|---|
| `undefined` / `absent` | `Incident pulse is not included in this snapshot.` |
| `empty` / ready with zero records | `No incidents are present in this snapshot.` |
| `unavailable` | `Incident pulse is unavailable for this snapshot.` |
| `malformed` | `Incident pulse could not be read from this snapshot.` |

The list must not render for any non-ready state or for a ready dataset with zero records.

## Out of scope

- New backend or public-data generation changes.
- New filters, pagination, charts, or incident mutations.
- Replacing the existing incident page or detail route.
- A new Open Design artifact; the component extends an existing visual system and the current audit supplies the visual target.

## Accessibility and responsive behavior

- Use a named section heading and a named list.
- Use real links with visible incident IDs; do not replace navigation with click-only handlers.
- Keep severity text visible in addition to color.
- Use a semantic `time` with the source timestamp in `dateTime`.
- Preserve visible focus styles from the existing link treatment.
- Stack row columns on narrow screens using the existing mobile breakpoint pattern.

## Verification contract

- Unit tests pin ranking, timestamp tie-breaking, limit, and each dataset state.
- Component tests pin accessible headings/list structure, native links, severity/status content, and `output` state messages.
- App integration coverage proves the validated incident dataset appears on Overview and links to the existing incident route.
- Frontend typecheck, build, lint/test commands, and the repository verification script must pass before the PR is handed off.
