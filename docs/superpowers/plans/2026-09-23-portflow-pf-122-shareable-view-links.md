# PF-122 Shareable Investigation Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accessible `Copy view link` action that copies the exact URL-backed PortFlow view without changing the snapshot contract.

**Architecture:** Keep clipboard behavior in a focused `ShareViewLink` component with injected URL and clipboard functions for deterministic tests. Render it in the existing `AppShell` filter band and use existing shell tokens and responsive breakpoints for styling.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Lucide React, existing CSS tokens, GitHub Pages static hosting.

**Spec:** `docs/superpowers/specs/2026-09-23-portflow-pf-122-shareable-view-links-design.md`

## Global Constraints

- Copy only on an explicit button activation; never write to the clipboard on load or navigation.
- Preserve the complete `window.location.href`, including pathname, search, and hash.
- Use an `output` live region for polite success and failure feedback.
- Keep the static-site, no-backend, no-persistence boundary unchanged.
- Preserve the existing 320px responsive breakpoint and visible focus treatment.
- Do not introduce a new dependency or notification framework.

## Review Focus

- Clipboard API missing: the control must show an actionable address-bar fallback instead of throwing.
- Clipboard rejection: the failure message must be visible and announced, with focus remaining on the button.
- URL mutation before activation: the handler must copy the URL at click time, not render time.
- Query and hash preservation: deep equipment/incident state must be copied byte-for-byte.
- Narrow layout: the control and feedback must wrap without horizontal overflow at 320px.

### Task 1: Record the PF-122 design contract

**Files:**
- Create: `docs/superpowers/specs/2026-09-23-portflow-pf-122-shareable-view-links-design.md`
- Create: `docs/superpowers/plans/2026-09-23-portflow-pf-122-shareable-view-links.md`

**Interfaces:**
- Produces the behavior contract used by Tasks 2–4.

- [x] **Step 1: Write the design contract and implementation plan**

  Include scope, non-goals, exact feedback copy, accessibility behavior, and
  the verification commands before product code changes.

- [x] **Step 2: Self-review the documents**

  Confirm that every spec requirement has a task, that no task changes the
  snapshot schema, and that each review-focus condition has a test owner.

- [ ] **Step 3: Commit the design artifacts**

```powershell
git add docs/superpowers/specs/2026-09-23-portflow-pf-122-shareable-view-links-design.md docs/superpowers/plans/2026-09-23-portflow-pf-122-shareable-view-links.md
git commit -m "docs: define PF-122 shareable view links"
```

### Task 2: Define deterministic clipboard behavior with failing tests

**Files:**
- Create: `web/src/app/ShareViewLink.tsx`
- Test: `web/src/app/ShareViewLink.test.tsx`

**Interfaces:**
- Produces `ShareViewLink` with optional `getUrl?: () => string` and
  `writeClipboard?: (value: string) => Promise<void>` test seams.

- [ ] **Step 1: Write the failing tests**

```tsx
it("copies the complete current view URL and announces success", async () => {
  const writeClipboard = vi.fn().mockResolvedValue(undefined);
  render(
    <ShareViewLink
      getUrl={() => "https://portflow.test/?terminal=TM-002&range=7d#equipment"}
      writeClipboard={writeClipboard}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

  await waitFor(() => expect(writeClipboard).toHaveBeenCalledWith(
    "https://portflow.test/?terminal=TM-002&range=7d#equipment",
  ));
  expect(screen.getByRole("status")).toHaveTextContent("View link copied.");
});

it("announces an actionable fallback when clipboard writing fails", async () => {
  const writeClipboard = vi.fn().mockRejectedValue(new Error("permission denied"));
  render(<ShareViewLink getUrl={() => "https://portflow.test/#incidents"} writeClipboard={writeClipboard} />);

  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Copy unavailable. Use your browser address bar.",
  );
});

it("reads the URL at activation time", async () => {
  let currentUrl = "https://portflow.test/#overview";
  const writeClipboard = vi.fn().mockResolvedValue(undefined);
  render(<ShareViewLink getUrl={() => currentUrl} writeClipboard={writeClipboard} />);
  currentUrl = "https://portflow.test/?equipment=QC-001#equipment";

  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

  await waitFor(() => expect(writeClipboard).toHaveBeenCalledWith(currentUrl));
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm --prefix web test -- --run src/app/ShareViewLink.test.tsx --maxWorkers=1`

Expected: FAIL because `ShareViewLink` does not exist yet.

- [ ] **Step 3: Implement the minimal component**

  Render a native button with the `Link2` icon, call the injected URL and
  clipboard functions inside the click handler, catch rejected or unavailable
  clipboard access, and expose the exact messages through an empty-when-idle
  `<output aria-live="polite">` element.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `npm --prefix web test -- --run src/app/ShareViewLink.test.tsx --maxWorkers=1`

Expected: PASS for the URL, success, failure, and activation-time cases.

- [ ] **Step 5: Commit the component contract**

```powershell
git add web/src/app/ShareViewLink.tsx web/src/app/ShareViewLink.test.tsx
git commit -m "feat: add shareable view link action"
```

### Task 3: Place and style the action in the application shell

**Files:**
- Modify: `web/src/app/AppShell.tsx`
- Modify: `web/src/app/AppShell.test.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes `ShareViewLink` from Task 2.
- Produces the same shell and URL behavior with an additional share action.

- [ ] **Step 1: Add a shell placement assertion**

  Extend the existing ready-shell test to assert that
  `screen.getByRole("button", { name: "Copy view link" })` is present beside
  the global filter controls, without invoking the browser clipboard.

- [ ] **Step 2: Run the shell test to verify the placement assertion fails**

Run: `npm --prefix web test -- --run src/app/AppShell.test.tsx --maxWorkers=1`

Expected: FAIL because `AppShell` does not render the action yet.

- [ ] **Step 3: Render the component in the existing filter band**

  Add a small `.filter-actions` wrapper around the existing filter summary and
  `ShareViewLink`. Keep the published scope note separate so its current
  semantics and layout remain unchanged.

- [ ] **Step 4: Add responsive styles**

  Style the action as a secondary outlined control using `--cobalt`,
  `--border`, `--surface`, and `--focus`. Give the feedback a stable inline
  area, let the action wrapper wrap on narrow widths, and set its mobile grid
  placement to span the filter band without widening the page.

- [ ] **Step 5: Run shell and accessibility-focused tests**

Run: `npm --prefix web test -- --run src/app/AppShell.test.tsx e2e/accessibility.spec.tsx --maxWorkers=1`

Expected: PASS with the new control visible and no new axe violations.

- [ ] **Step 6: Commit shell integration and styles**

```powershell
git add web/src/app/AppShell.tsx web/src/app/AppShell.test.tsx web/src/styles.css
git commit -m "feat: place share link action in filter band"
```

### Task 4: Reconcile documentation and run the quality gates

**Files:**
- Modify: `docs/product/BACKLOG.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Documents PF-122 as complete only after the implementation and verification
  commands pass.

- [ ] **Step 1: Add the PF-122 completion checkpoint**

  Update the current next action from the stale PF-121 review checkpoint to
  PF-122 complete, record the implementation commit identifiers, and state that
  clipboard failure keeps the browser address bar as the fallback.

- [ ] **Step 2: Add the changelog entry**

  Record the user-visible copy-link action, its accessibility feedback, and the
  no-backend boundary.

- [ ] **Step 3: Run frontend verification**

Run:

```powershell
npm --prefix web test -- --run --maxWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
python scripts/check_budgets.py
npm --prefix web run lighthouse
```

Expected: all tests, typecheck, build, budgets, and three Lighthouse runs pass.

- [ ] **Step 4: Run repository verification**

Run: `./scripts/verify_r2.ps1`

Expected: Python tests, Ruff, mypy, frontend checks, and the deterministic
public-data diff pass.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/product/BACKLOG.md CHANGELOG.md
git commit -m "docs: close PF-122 shareable view links"
```

- [ ] **Step 6: Inspect the final branch**

Run: `git diff --check; git status --short; git log --oneline -6`

Expected: no whitespace errors, no uncommitted source changes, and the branch
contains the independent PF-122 commits.

