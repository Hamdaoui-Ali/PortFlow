# PF-120 Published snapshot filter scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the published snapshot's filter scope visible and let visitors recover from unsupported filter combinations in one accessible action.

**Architecture:** A pure `filterScope` helper derives terminal and UTC period copy from the validated snapshot. `AppShell` receives that scope and exposes a reset action through the existing filter context; `App` wires the snapshot scope and reset to the existing Overview mismatch state. No public-data or route contract changes.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing CSS tokens, Zod-validated `SnapshotV1`.

**Spec:** `docs/superpowers/specs/2026-09-23-portflow-pf-120-filter-scope-design.md`

## Global Constraints

- Use the already validated `SnapshotV1`; do not change the public snapshot schema.
- Ready and stale-cache snapshots may show scope; loading and unavailable states must not claim a scope.
- Preserve the existing `all` / `24h` reset values and current hash route.
- Keep unsupported filter choices available for future snapshots; do not fabricate data.
- Use native semantic controls and the existing visual tokens/focus styles.
- Every behavior change follows RED → GREEN TDD and receives its own focused commit.

## Review Focus

- A snapshot with an unknown but schema-valid terminal ID must show that ID rather than an incorrect city name — `filterScope.test.ts`.
- Source periods that are not exactly one calendar day must remain deterministic and UTC-labelled — `filterScope.test.ts`.
- Loading/error states must not present stale or invented scope — `App.test.tsx`.
- Resetting unsupported filters must update both visible controls and the query string while preserving a non-overview hash — `App.test.tsx`.
- The recovery button must remain keyboard-discoverable and not replace the existing no-fabrication warning — `App.test.tsx` and frontend accessibility tests.

---

### Task 1: Snapshot scope derivation

**Files:**
- Create: `web/src/app/filterScope.ts`
- Test: `web/src/app/filterScope.test.ts`

**Interfaces:**
- Consumes: `SnapshotV1` from `web/src/data/schema.ts`.
- Produces: `SnapshotFilterScope`, `deriveSnapshotFilterScope(snapshot: SnapshotV1): SnapshotFilterScope`, and `formatSnapshotPeriod(start: string, end: string): string` for the shell and Overview copy.

- [ ] **Step 1: Write the failing helper tests**

```ts
it("derives the known terminal and UTC source period", () => {
  expect(deriveSnapshotFilterScope(snapshot)).toEqual({
    terminalLabel: "Casablanca Terminal",
    periodLabel: "02 Sept 2026, 00:00–23:55 UTC",
  });
});

it("falls back to the validated terminal ID", () => {
  expect(deriveSnapshotFilterScope({
    ...snapshot,
    overview: { ...snapshot.overview, terminal_id: "TM-999" },
  }).terminalLabel).toBe("TM-999");
});
```

- [ ] **Step 2: Run the helper tests and verify they fail for the missing module**

Run: `npm --prefix web test -- --run src/app/filterScope.test.ts`

Expected: FAIL because `web/src/app/filterScope.ts` does not exist.

- [ ] **Step 3: Implement the smallest pure scope helper**

```ts
export interface SnapshotFilterScope {
  terminalLabel: string;
  periodLabel: string;
}

export function deriveSnapshotFilterScope(snapshot: SnapshotV1): SnapshotFilterScope {
  return {
    terminalLabel: terminalLabels[snapshot.overview.terminal_id] ?? snapshot.overview.terminal_id,
    periodLabel: formatSnapshotPeriod(
      snapshot.manifest.source_period_start,
      snapshot.manifest.source_period_end,
    ),
  };
}
```

Use `Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })`; format a same-day period as `DD Mon YYYY, HH:MM–HH:MM UTC` and a cross-day period as `DD Mon YYYY, HH:MM – DD Mon YYYY, HH:MM UTC`.

- [ ] **Step 4: Run the helper tests and verify they pass**

Run: `npm --prefix web test -- --run src/app/filterScope.test.ts`

Expected: all helper tests pass.

- [ ] **Step 5: Commit the helper**

```powershell
git add web/src/app/filterScope.ts web/src/app/filterScope.test.ts
git commit -m "feat: derive published snapshot filter scope"
```

### Task 2: Filter-band scope disclosure and reset context

**Files:**
- Modify: `web/src/app/AppShell.tsx`
- Create: `web/src/app/AppShell.test.tsx`

**Interfaces:**
- Consumes: `SnapshotFilterScope` from `web/src/app/filterScope.ts` and existing `AppFilters` values.
- Produces: `useAppFilters()` returning `{ terminal, range, resetFilters }`, and an optional `filterScope` AppShell prop.

- [ ] **Step 1: Write failing AppShell tests**

Add a small `FilterProbe` child that reads `resetFilters` from `useAppFilters`,
then render `AppShell` directly with a scope object and assert:

```ts
expect(screen.getByRole("note", { name: "Published snapshot scope" })).toHaveTextContent(
  "Casablanca Terminal",
);
expect(screen.getByRole("note", { name: "Published snapshot scope" })).toHaveTextContent(
  "02 Sept 2026, 00:00–23:55 UTC",
);
```

Click the probe's reset button and assert the URL query is cleared while its
hash remains unchanged. Render a loading shell without `filterScope` and assert
the scope note is absent.

- [ ] **Step 2: Run the targeted App tests and verify the new assertions fail**

Run: `npm --prefix web test -- --run src/app/AppShell.test.tsx`

Expected: FAIL because the shell has no scope note or reset context yet.

- [ ] **Step 3: Add reset state and the accessible scope note**

Extend the filter context with:

```ts
resetFilters: () => void;
```

Implement it by setting `terminal` to `"all"`, `range` to `"24h"`, and reusing `updateFilters("all", "24h")`. Add the optional `filterScope` prop and render a named `<p className="filter-scope" role="note" aria-label="Published snapshot scope">` after the filter controls when scope is available.

- [ ] **Step 4: Run the targeted App tests and verify they pass**

Run: `npm --prefix web test -- --run src/app/AppShell.test.tsx`

Expected: all AppShell tests pass, including scope visibility, loading absence,
and reset state/URL behavior.

- [ ] **Step 5: Commit the shell behavior**

```powershell
git add web/src/app/AppShell.tsx web/src/app/AppShell.test.tsx
git commit -m "feat: disclose published filter scope"
```

### Task 3: Overview mismatch recovery

**Files:**
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/features/overview/OverviewPage.tsx`
- Modify: `web/src/app/App.test.tsx`

**Interfaces:**
- Consumes: `deriveSnapshotFilterScope`, `SnapshotFilterScope`, and `resetFilters`.
- Produces: an Overview mismatch state with a native `Reset filters to published scope` button that returns to the same hash route with supported query parameters removed.

- [ ] **Step 1: Write the failing reset-flow test**

```ts
it("resets unsupported filters to the published scope", async () => {
  window.history.replaceState({}, "", "/?terminal=TM-002&range=7d#equipment");
  render(<App loadData={() => Promise.resolve(snapshot)} />);

  fireEvent.click(screen.getAllByRole("link", { name: "Overview" })[0]);
  expect(await screen.findByRole("heading", { name: "Snapshot unavailable for selected filters" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Reset filters to published scope" }));

  expect(window.location.search).toBe("");
  expect(window.location.hash).toBe("#overview");
  expect(screen.getByLabelText("Terminal")).toHaveValue("all");
  expect(screen.getByLabelText("Date range")).toHaveValue("24h");
  expect(await screen.findByRole("heading", { name: "Hourly equipment availability" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the reset-flow test and verify it fails**

Run: `npm --prefix web test -- --run src/app/App.test.tsx`

Expected: FAIL because the Overview mismatch state has no reset button and App does not pass scope/reset behavior through.

- [ ] **Step 3: Wire the validated scope and reset action through App**

Derive scope only for `ready` and `stale` snapshot states. Pass it to `AppShell`, pass `resetFilters` to `OverviewPage`, and update the mismatch branch to include the honest scope copy plus the native reset button. Do not change `matchesFilters` or show KPI values for unsupported selections.

- [ ] **Step 4: Run the App tests and verify the reset flow passes**

Run: `npm --prefix web test -- --run src/app/App.test.tsx`

Expected: all App tests pass; the mismatch state recovers in one interaction and preserves route semantics.

- [ ] **Step 5: Commit the recovery flow**

```powershell
git add web/src/app/App.tsx web/src/features/overview/OverviewPage.tsx web/src/app/App.test.tsx
git commit -m "feat: recover unsupported snapshot filters"
```

### Task 4: Responsive styling, documentation, and full verification

**Files:**
- Modify: `web/src/styles.css`
- Modify: `docs/product/BACKLOG.md`
- Test: `web/e2e/accessibility.spec.tsx` (only if the existing selector coverage needs a PF-120 assertion)

**Interfaces:**
- Consumes: the existing CSS tokens and the completed PF-120 shell/mismatch markup.
- Produces: readable scope and recovery treatment at desktop and mobile widths, plus the PF-120 completion checkpoint.

- [ ] **Step 1: Add the focused styling**

Style `.filter-scope` as a compact muted note in the filter band, allow it to wrap at narrow widths, and include the existing `.data-state button` focus treatment for the recovery button. Do not add new colors or icons.

- [ ] **Step 2: Run frontend tests, typecheck, and build**

Run: `npm --prefix web test -- --run --maxWorkers=1`

Expected: all frontend tests pass.

Run: `npm --prefix web run typecheck`

Expected: TypeScript exits successfully.

Run: `npm --prefix web run build`

Expected: Vite emits a production build.

- [ ] **Step 3: Run accessibility and performance verification**

Run: `npm --prefix web run lighthouse`

Expected: three Lighthouse runs complete and the configured assertions pass.

Run: `python scripts/check_budgets.py`

Expected: snapshot, bundle, and startup budgets pass.

- [ ] **Step 4: Update the backlog checkpoint**

Record PF-119 as merged at `8cd636d` and PF-120 as the current implementation checkpoint, including the scope disclosure, reset behavior, and verification evidence. Keep the next-action wording truthful until the PR merges.

- [ ] **Step 5: Commit styling and documentation**

```powershell
git add web/src/styles.css docs/product/BACKLOG.md
git commit -m "docs: record PF-120 filter scope checkpoint"
```

- [ ] **Step 6: Run the complete repository gate**

Run: `./scripts/verify_r2.ps1`

Expected: Python, frontend, typecheck, build, budgets, and Lighthouse all pass with no generated public-data diff.

- [ ] **Step 7: Review the final diff and commit history**

Run: `git diff --check; git status --short --branch; git log --oneline --decorate -12`

Expected: a clean PF-120 worktree with focused commits and no generated/private artifacts.
