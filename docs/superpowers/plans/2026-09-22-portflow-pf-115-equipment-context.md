# PF-115 Equipment Detail Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic replay activity and related incident context to the selected equipment detail view without changing the public snapshot contract.

**Architecture:** Keep all derivation in pure TypeScript helpers. `EquipmentDetail` derives view models from the optional replay and incident datasets, and a focused `EquipmentContext` component renders explicit ready, empty, absent, unavailable, malformed, and no-match states. `App` and `EquipmentPage` only thread existing snapshot data through; no API, polling, schema, or dependency change is introduced.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing CSS, Zod-validated `SnapshotV1` data.

**Spec:** `docs/superpowers/specs/2026-09-22-portflow-pf-115-equipment-context-design.md`

## Global Constraints

- The public snapshot contract stays unchanged; do not edit `web/public/data` fixtures or `SnapshotV1` schemas.
- Add no API endpoint, database query, polling loop, streaming dependency, charting library, or hosted workflow.
- Activity events are ordered chronologically with original-array-index tie breaking and consecutive identical state/availability pairs collapsed.
- Incident records are filtered to the selected equipment and sorted by `opened_at` descending with incident-id tie breaking.
- Preserve existing deep links, global filters, back navigation, focus restoration, responsive breakpoints, and reduced-motion behavior.
- Keep data provenance explicit: absent, empty, unavailable, malformed, and no-match are not interchangeable states.

## Review Focus

- An omitted or empty replay dataset must not look like a healthy asset with no history; pin `absent` and `empty` separately in the derivation and component tests.
- Events with equal timestamps and repeated adjacent values must remain deterministic and must collapse only adjacent identical pairs; pin ordering, tie breaking, and immutability in the unit tests.
- An incident dataset that is absent, unavailable, malformed, or empty must retain its source status; pin every status in the component tests.
- Incident links must use the existing `?incident=<id>#incidents` route and encode the id through `URLSearchParams`; pin the exact accessible link and href in the detail test.
- Existing callers that omit the new optional props must keep the current metric grid and back/focus behavior without a runtime or type error; pin the legacy `EquipmentDetail` render and the fleet back/focus regression.

---

### Task 1: Derive stable equipment context view models

**Files:**
- Create: `web/src/features/equipment/equipmentContext.ts`
- Test: `web/src/features/equipment/equipmentContext.test.ts`

**Interfaces:**
- Consumes: `ReplayEventV1[] | undefined`, `IncidentDatasetState | undefined`, and the selected equipment id from `web/src/data/schema.ts`.
- Produces: `EquipmentActivityView`, `EquipmentIncidentView`, `deriveEquipmentActivity(events, equipmentId)`, and `deriveEquipmentIncidents(dataset, equipmentId)` for the presentation task.

- [ ] **Step 1: Write the failing unit tests**

Create a small replay fixture with two `QC-001` events at the same timestamp, an adjacent duplicate, one later state, and one `QC-002` event. Assert the public behavior through the exact helper signatures:

```ts
const activity = deriveEquipmentActivity(events, "QC-001");

expect(activity.status).toBe("ready");
expect(activity.events.map(({ state, available }) => ({ state, available }))).toEqual([
  { state: "ACTIVE", available: true },
  { state: "MAINTENANCE", available: false },
]);
expect(activity.events[0].event_id).toBe("evt-first-at-tie");
expect(events).toEqual(originalEvents);
```

Add explicit cases for `undefined -> absent`, `[] -> empty`, and a non-empty replay without a matching equipment id -> `no-match`. Add incident cases for `undefined -> absent`, every non-ready dataset status preserved, an empty ready dataset -> `empty`, a ready dataset with no matching equipment -> `no-match`, and matching records sorted newest-first with the incident id as the equal-time tie breaker.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```text
npm --prefix web test -- --run src/features/equipment/equipmentContext.test.ts
```

Expected: FAIL because `equipmentContext.ts` and its exported derivation helpers do not exist yet.

- [ ] **Step 3: Implement the pure helpers**

Define these exact types and functions:

```ts
export type EquipmentActivityStatus = "absent" | "empty" | "no-match" | "ready";
export interface EquipmentActivityView {
  status: EquipmentActivityStatus;
  events: ReplayEventV1[];
}

export type EquipmentIncidentStatus =
  | "absent" | "empty" | "unavailable" | "malformed" | "no-match" | "ready";
export interface EquipmentIncidentView {
  status: EquipmentIncidentStatus;
  records: IncidentRecordV1[];
}

export function deriveEquipmentActivity(
  events: ReplayEventV1[] | undefined,
  equipmentId: string,
): EquipmentActivityView;

export function deriveEquipmentIncidents(
  dataset: IncidentDatasetState | undefined,
  equipmentId: string,
): EquipmentIncidentView;
```

For activity, map matching events to `{ event, index }`, sort a copied array by `Date.parse(event.event_timestamp)` and then `index`, and build a new result array by skipping only an immediately previous entry with equal `state` and `available`. Return `ready` when at least one matching event exists, even if all matching events collapse into one entry. For incidents, preserve non-ready statuses, filter only ready records, sort a copied array by descending opened time and ascending incident id, and return `empty`, `no-match`, or `ready` as defined by the spec. Never call `.sort()` on the caller’s array.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```text
npm --prefix web test -- --run src/features/equipment/equipmentContext.test.ts
npm --prefix web run typecheck
```

Expected: all new unit tests pass and TypeScript reports no errors.

- [ ] **Step 5: Commit the pure data slice**

```text
git add web/src/features/equipment/equipmentContext.ts web/src/features/equipment/equipmentContext.test.ts
git commit -m "feat: derive equipment detail context"
```

### Task 2: Render accessible context states

**Files:**
- Create: `web/src/features/equipment/EquipmentContext.tsx`
- Test: `web/src/features/equipment/EquipmentContext.test.tsx`

**Interfaces:**
- Consumes: `EquipmentActivityView` and `EquipmentIncidentView` from Task 1.
- Produces: `EquipmentContext({ activity, incidents })`, with headings `Equipment activity` and `Related incidents` and keyboard-reachable incident links.

- [ ] **Step 1: Write the failing component tests**

Render `EquipmentContext` with each view-model status. Assert these exact messages:

```ts
expect(screen.getByRole("heading", { name: "Equipment activity" })).toBeInTheDocument();
expect(screen.getByText("Replay activity is not included in this snapshot.")).toBeInTheDocument();
expect(screen.getByText("No replay activity is available in this snapshot.")).toBeInTheDocument();
expect(screen.getByText("No replay events match this equipment.")).toBeInTheDocument();
```

Cover incident messages for absent (`Incident history is not included in this snapshot.`), empty (`No incidents are present in this snapshot.`), no-match (`No incidents match this equipment.`), unavailable (`Incident history is unavailable for this snapshot.`), and malformed (`Incident history could not be read from this snapshot.`). For ready states, assert a labelled list, UTC `<time dateTime>` values, state/availability text, the incident id, severity, root cause, and an accessible link with href `?incident=inc-000002#incidents`.

- [ ] **Step 2: Run the component tests to verify they fail**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentContext.test.tsx
```

Expected: FAIL because the component does not exist yet.

- [ ] **Step 3: Implement the context component**

Create one section for activity and one for related incidents. Use semantic `<ol>`/`<ul>` lists, `aria-labelledby` headings, `<time dateTime={event.event_timestamp}>`, and text labels such as `Available` or `Unavailable`. Render an incident as an anchor to `#incidents` whose query is created with `new URLSearchParams({ incident: record.incident_id }).toString()`, so the existing route remains the source of truth. Keep formatting local to this component: render UTC timestamps with `new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })` and display the source ISO value in the `dateTime` attribute.

- [ ] **Step 4: Run the component tests to verify they pass**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentContext.test.tsx
npm --prefix web run typecheck
```

Expected: all state and accessibility assertions pass with no type errors.

- [ ] **Step 5: Commit the presentation slice**

```text
git add web/src/features/equipment/EquipmentContext.tsx web/src/features/equipment/EquipmentContext.test.tsx
git commit -m "feat: render equipment context states"
```

### Task 3: Thread snapshot data into the selected equipment

**Files:**
- Modify: `web/src/features/equipment/EquipmentDetail.tsx`
- Modify: `web/src/features/equipment/EquipmentPage.tsx`
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/features/equipment/EquipmentDetail.test.tsx`
- Modify: `web/src/features/equipment/EquipmentPage.test.tsx`
- Test: `web/src/app/App.test.tsx` only if the route-level assertion cannot be kept in `EquipmentPage.test.tsx`

**Interfaces:**
- Consumes: optional `ReplayEventV1[]` and optional `IncidentDatasetState` from the already-loaded `SnapshotV1`.
- Produces: `EquipmentDetail` props `{ record, onBack, replayEvents?, incidentDataset? }`; no caller is required to provide the new props.

- [ ] **Step 1: Write the failing wiring tests**

Extend the existing detail fixture with one `QC-001` replay sequence and the two published incident records. Render:

```tsx
render(
  <EquipmentDetail
    record={record}
    replayEvents={[matchingEvent]}
    incidentDataset={{ status: "ready", records: [incident] }}
    onBack={vi.fn()}
  />,
);
```

Assert that the detail still contains all eight current metric labels, plus `Equipment activity`, the matching event state, `Related incidents`, and the incident link. Keep the existing test that renders `<EquipmentDetail record={record} onBack={...} />` unchanged to pin optional-prop compatibility. In the page test, render a snapshot with `event_replay` and `incidents`, open `QC-001`, and assert that the context is present; retain the existing back-navigation/focus assertions.

- [ ] **Step 2: Run the wiring tests to verify they fail**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentDetail.test.tsx src/features/equipment/EquipmentPage.test.tsx
```

Expected: FAIL because the existing detail does not accept or render the new datasets and the page does not pass them.

- [ ] **Step 3: Implement the narrow data flow**

Import the schema and pure helper types. Add optional props to `EquipmentDetail`, derive both view models with `record.equipment_id`, and render `<EquipmentContext activity={...} incidents={...} />` after the existing metric list. Add optional `replayEvents` and `incidentDataset` props to `EquipmentPage`, pass them to `EquipmentDetail`, and update `AppContent` to call:

```tsx
<EquipmentPage
  dataset={snapshot.equipment ?? { status: "absent" }}
  replayEvents={snapshot.event_replay}
  incidentDataset={snapshot.incidents}
  filters={filters}
/>
```

Do not alter the equipment URL writer, selected-record lookup, return-focus effect, or global-filter behavior.

- [ ] **Step 4: Run the wiring tests to verify they pass**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentDetail.test.tsx src/features/equipment/EquipmentPage.test.tsx src/app/App.test.tsx
npm --prefix web run typecheck
```

Expected: existing detail, route, back-navigation, focus, filter, and new context assertions all pass.

- [ ] **Step 5: Commit the route-data slice**

```text
git add web/src/features/equipment/EquipmentDetail.tsx web/src/features/equipment/EquipmentPage.tsx web/src/app/App.tsx web/src/features/equipment/EquipmentDetail.test.tsx web/src/features/equipment/EquipmentPage.test.tsx web/src/app/App.test.tsx
git commit -m "feat: thread snapshot context into equipment detail"
```

### Task 4: Add responsive styling and route-link regression coverage

**Files:**
- Modify: `web/src/styles.css`
- Modify: `web/src/features/equipment/EquipmentContext.test.tsx`
- Modify: `web/src/features/equipment/EquipmentPage.test.tsx`

**Interfaces:**
- Consumes: the stable class names emitted by `EquipmentContext`.
- Produces: a context layout that uses existing border, typography, focus, mobile, and reduced-motion conventions without changing data behavior.

- [ ] **Step 1: Write the failing route and responsive contract tests**

Add a regression test that finds the related incident link by role and asserts `href="?incident=inc-000002#incidents"`, then verifies the existing detail back button still returns to `#equipment` and restores the selected fleet control. Keep the test data deterministic and avoid asserting pixel values; visual spacing remains a CSS/build concern rather than a pixel snapshot.

- [ ] **Step 2: Run the regression tests to verify the new contract is not yet complete**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentContext.test.tsx src/features/equipment/EquipmentPage.test.tsx
```

Expected: the link/back assertions pass, giving the styling change a stable interaction contract to preserve.

- [ ] **Step 3: Add the context styles**

Add styles adjacent to the existing equipment detail rules for `.equipment-context`, `.equipment-context-section`, `.equipment-context-header`, `.equipment-activity-list`, `.equipment-activity-item`, `.equipment-activity-state`, `.equipment-incident-list`, and `.equipment-incident-item`. Use the existing `--border`, `--muted`, `--ink`, `--cobalt`, and `--surface` variables. Give each section a top rule and readable spacing; keep activity timestamps tabular and incident links visibly keyboard-focusable. Under the existing `max-width: 899px` media query, stack the context sections and allow activity rows to wrap. Under `max-width: 359px`, remove horizontal padding only where the existing equipment detail already does so. Add no animation; the existing reduced-motion rules therefore remain valid.

- [ ] **Step 4: Run the regression and build checks**

Run:

```text
npm --prefix web test -- --run src/features/equipment/EquipmentContext.test.tsx src/features/equipment/EquipmentPage.test.tsx
npm --prefix web run typecheck
npm --prefix web run build
```

Expected: all focused tests, TypeScript, and the production build pass.

- [ ] **Step 5: Commit the interaction and styling slice**

```text
git add web/src/styles.css web/src/features/equipment/EquipmentContext.test.tsx web/src/features/equipment/EquipmentPage.test.tsx
git commit -m "style: make equipment context responsive"
```

### Task 5: Record the shipped post-V1 feature

**Files:**
- Modify: `docs/product/BACKLOG.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the completed PF-115 behavior and verification evidence from Tasks 1-4.
- Produces: an accurate project record that identifies PF-115 as the current post-V1 checkpoint and records its scope boundaries.

- [ ] **Step 1: Update the backlog**

Replace the stale “No subsequent post-V1 specification is currently approved” sentence with a PF-115 entry that names the design/plan paths, the actual implementation commit ids, and the feature boundaries: derived activity, related incidents, explicit dataset states, unchanged public data, and preserved route/focus behavior. Set the next action to the next unapproved post-V1 feature only if one exists; otherwise state that PF-115 is the current approved slice and no later feature is approved.

- [ ] **Step 2: Add a changelog entry**

Add a dated `PF-115 Equipment detail context` section at the top of `CHANGELOG.md` describing the activity timeline, related incident links, honest absent/empty/unavailable/malformed states, and unchanged static snapshot boundary. Do not claim hosted or live operational data.

- [ ] **Step 3: Validate and commit the documentation**

Run:

```text
git diff --check
rg -n "PF-115|Equipment detail context|No subsequent post-V1" docs/product/BACKLOG.md CHANGELOG.md
```

Expected: PF-115 is documented in both files and the obsolete approval sentence is gone. Commit:

```text
git add docs/product/BACKLOG.md CHANGELOG.md
git commit -m "docs: record PF-115 equipment context"
```

### Task 6: Run the full verification gate and prepare the PR

**Files:**
- No planned source changes; if a command exposes a regression, add the smallest focused test and implementation fix in a new commit before continuing.

**Interfaces:**
- Consumes: all implementation and documentation commits from Tasks 1-5.
- Produces: a clean verified branch ready for push and a PR containing the design, plan, implementation, docs, and evidence.

- [ ] **Step 1: Run the complete frontend verification**

From the repository root, run:

```text
npm --prefix web test -- --run --maxWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
python scripts/check_budgets.py
git diff --check
```

Expected: the full Vitest suite passes, TypeScript and Vite build succeed, budgets pass, and the diff has no whitespace errors.

- [ ] **Step 2: Run the repository verification script**

Run:

```text
./scripts/verify_r2.ps1
```

Expected: deterministic public data is unchanged, Python tests and static checks pass, and the script exits zero. If Docker or an external service is unavailable, record the exact bounded environment limitation in the PR instead of changing the product boundary.

- [ ] **Step 3: Inspect the final change set**

Run:

```text
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: only PF-115 files are present, the worktree is clean after committing, and the log contains focused design, plan, data, UI, wiring, styling, and documentation commits.

- [ ] **Step 4: Push and open the PR**

```text
git push --set-upstream origin codex/pf-115-equipment-context
```

Open a PR from `codex/pf-115-equipment-context` into `main` with this summary:

```text
Summary
- Add deterministic equipment activity context derived from the existing replay snapshot.
- Add related incident links with explicit dataset-state messaging.
- Preserve the static public-data boundary, equipment URL state, focus restoration, and responsive behavior.

Verification
- npm --prefix web test -- --run --maxWorkers=1
- npm --prefix web run typecheck
- npm --prefix web run build
- python scripts/check_budgets.py
- ./scripts/verify_r2.ps1
```

- [ ] **Step 5: Wait for CI and automated review before handoff**

Confirm the required workflow, SonarCloud quality gate, and CodeRabbit review are green. If a check fails, reproduce it locally, add a focused regression test first, fix the smallest affected code path, rerun the relevant gate, and push the fix as a new commit. After the PR is green, stop for the user’s review and merge decision before starting PF-116.
