# PF-117 Overview Equipment Pulse Implementation Plan

**Goal:** Make Overview's aggregate equipment availability actionable with a
small, deterministic snapshot-backed equipment pulse.

**Branch:** `codex/pf-117-overview-equipment-pulse`

**Source:** `docs/superpowers/specs/2026-09-23-portflow-pf-117-overview-equipment-pulse-design.md`

## Guardrails

- Work only from the merged `origin/main` baseline.
- Keep the implementation static and snapshot-backed; do not add APIs,
  queries, polling, credentials, or dependencies.
- Preserve current Overview URL, filter, freshness, focus, and native-link
  behavior.
- Treat dataset status as product meaning. Never turn absent, unavailable, or
  malformed evidence into a healthy-looking empty fleet.
- Use test-first slices and commit each independently reviewable change.

## Task 1 - Document the slice

Create the PF-117 spec and this plan. Confirm the ranking, component boundary,
semantic states, route shape, accessibility requirements, and verification
commands. Commit the documents separately before touching implementation code.

## Task 2 - Add failing derivation tests

Create `web/src/features/overview/overviewEquipmentPulse.test.ts` with typed
fixtures and tests for:

1. omitted dataset -> `absent`;
2. empty, unavailable, and malformed datasets -> the same semantic state;
3. ready dataset with no records -> `empty`;
4. unavailable records before available records;
5. lower availability and higher downtime ordering, including null values;
6. deterministic equipment ID tie-breaking and the three-record limit;
7. input array and record immutability.

Run the focused test and expect it to fail because the helper does not exist.
Commit the failing tests only.

## Task 3 - Implement the pure ranking helper

Add `overviewEquipmentPulseData.ts` with a discriminated result type and
`deriveOverviewEquipmentPulse(dataset)`. Copy before sorting, keep null values
last for numeric comparisons, and return at most three original records.

Run the focused helper suite and the web typecheck, then commit the
implementation.

## Task 4 - Build the accessible pulse panel

Add `OverviewEquipmentPulse.tsx` and component tests. The ready view should
render the section heading, snapshot-ranking explanation, native equipment
links, terminal, state, availability, and downtime values. Render explicit
messages for every non-ready result, including a ready empty array.

Run the focused component suite and commit the panel.

## Task 5 - Thread snapshot data through Overview

Pass `snapshot.equipment` from `App.tsx` into `OverviewPage` and compose the
pulse after the aggregate availability card. Add App coverage proving the
equipment snapshot records appear on the default Overview route and retain
the route-shaped native links.

Run all Overview and App tests. Commit the route wiring and regression tests.

## Task 6 - Apply existing visual language

Add responsive CSS for the pulse using the existing control-tower spacing,
border, type, link, and breakpoint tokens. Validate desktop and narrow layouts
in the local browser. Keep reduced-motion behavior unchanged.

Run the full frontend suite, typecheck, production build, Pages-path check,
and frontend budget checks. Commit styling separately.

## Task 7 - Close product evidence

After the implementation gate passes, update `docs/product/BACKLOG.md` to
record PF-117 as the current review checkpoint and add a dated PF-117 entry to
`CHANGELOG.md`. State the static snapshot boundary and the deterministic
ranking. Commit documentation separately.

## Task 8 - Verify and hand off

Run the exact repository gate from the worktree, then confirm:

- no generated artifacts or dependency folders are tracked;
- `git diff --check` passes;
- Python tests, Ruff, and mypy pass;
- frontend tests, typecheck, build, budgets, and Lighthouse pass;
- the branch is clean after commit;
- PR CI, SonarCloud, and CodeRabbit are green.

Open a PR from `codex/pf-117-overview-equipment-pulse` into `main`. Do not
merge it automatically; stop and ask the user to review and merge before
selecting the next specification.

## Commit slices

1. `docs: specify PF-117 overview equipment pulse`
2. `test: define overview equipment pulse ranking`
3. `feat: derive deterministic overview equipment pulse`
4. `test: cover overview equipment pulse panel`
5. `feat: expose equipment pulse on overview`
6. `style: add responsive overview equipment pulse`
7. `docs: record PF-117 review checkpoint`
