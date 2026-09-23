# PF-116 Incident Detail Context Implementation Plan

**Goal:** Add snapshot-backed equipment context and a native equipment deep
link to incident detail without changing the public data contract.

**Branch:** `codex/pf-116-incident-context`

**Source:** `docs/superpowers/specs/2026-09-22-portflow-pf-116-incident-context-design.md`

## Guardrails

- Work only from the merged `origin/main` baseline.
- Keep the implementation static and snapshot-backed; do not add APIs,
  queries, polling, credentials, or dependencies.
- Preserve all current incident URL, filter, focus, freshness, and native-link
  behavior.
- Treat dataset status as product meaning. Never turn absent, unavailable, or
  malformed evidence into a healthy-looking empty state.
- Use test-first slices and commit each independently reviewable change.

## Task 1 — Document the slice

Create the PF-116 spec and this plan. Confirm the scope, component boundary,
semantic states, route shape, accessibility requirements, and verification
commands. Commit the documents separately before touching implementation code.

## Task 2 — Add failing derivation tests

Create `web/src/features/incidents/incidentContext.test.ts` with a small typed
fixture and tests for:

1. omitted dataset → `absent`;
2. empty dataset → `empty`;
3. unavailable dataset → `unavailable`;
4. malformed dataset → `malformed`;
5. ready dataset with no matching equipment → `no-match`;
6. ready dataset with a matching record → stable `ready` projection;
7. input array and record immutability.

Run the focused test and expect it to fail because the helper does not exist.
Commit the failing tests only.

## Task 3 — Implement the pure context helper

Add `incidentContext.ts` with a discriminated result type and
`deriveIncidentEquipmentContext(dataset, equipmentId)`. Keep it free of React
and browser APIs. Return the original immutable record or a read-only
projection with only the fields the panel needs; keep state checks explicit and
ordered from dataset status to record matching.

Run the focused helper suite, Ruff/mypy where applicable, and commit the
implementation.

## Task 4 — Build the accessible context panel

Add `IncidentContextPanel.tsx` and component tests. The ready view should
render:

- `Equipment context` heading;
- native `Open equipment <id>` link with `?equipment=<id>#equipment`;
- Terminal, State, Availability, Utilization, and Downtime values;
- explicit messages for every non-ready result.

Do not attach an `onClick` handler that cancels the anchor's default action.
Run the focused component suite and commit the panel.

## Task 5 — Thread snapshot data through the incident route

Pass `snapshot.equipment` from `App.tsx` to `IncidentPage`, then into
`IncidentDetail`. Keep existing callers safe when the optional dataset is not
provided. Add route coverage that selects `inc-000002`, verifies the context
panel and link, and confirms a dispatched click is not prevented before the
test performs the jsdom `history.pushState`/`hashchange` transition.

Run all incident and app tests. Commit the route wiring and regression tests.

## Task 6 — Apply existing visual language

Add responsive CSS for the context panel using the existing detail-grid,
surface, border, type, and breakpoint tokens. Validate desktop and narrow
layouts in the local browser. Keep reduced-motion behavior unchanged.

Run the full frontend suite, typecheck, production build, and frontend budget
checks. Commit the styling and any focused test adjustments.

## Task 7 — Close product evidence

After the implementation gate passes, update `docs/product/BACKLOG.md` to
record PF-116 as complete and set the next action to be selected after this
review. Add a dated PF-116 entry to `CHANGELOG.md` describing the incident
context panel and its explicit snapshot-only boundary. Commit documentation
separately.

## Task 8 — Verify and hand off

Run the exact repository gate from the worktree, then confirm:

- no generated artifacts or dependency folders are tracked;
- `git diff --check` passes;
- Python tests, Ruff, and mypy pass;
- frontend tests, typecheck, build, budgets, and Lighthouse pass;
- the branch is clean after commit;
- PR CI, SonarCloud, and CodeRabbit are green.

Open a PR from `codex/pf-116-incident-context` into `main`. Do not merge it
automatically; stop and ask the user to review and merge before selecting the
next specification.
