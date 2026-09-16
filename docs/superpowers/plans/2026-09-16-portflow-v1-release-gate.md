# PortFlow V1 Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an auditable PF-030 V1 release record for the existing PortFlow product, with fresh automated, responsive, accessibility, deployment, cost, and limitation evidence, including the bounded responsive and focus hardening found during the gate.

**Architecture:** This is a documentation-and-verification slice over the existing static PortFlow build, with a small UI hardening patch for the release blockers found at 320px and on equipment-detail return. The release record will reuse the checked-in verification scripts, approved UI specification, accessibility checklist, deployment runbook, cost ledger, and public snapshot; it will not introduce a runtime service.

**Tech Stack:** PowerShell, Python/uv, pytest, Ruff, mypy, npm, Vitest, TypeScript, Vite, Lighthouse CI, Chromium in the in-app browser, GitHub Pages.

**Spec:** `docs/product/BACKLOG.md` PF-030, `docs/design/PORTFLOW_UI_SPEC.md`, `docs/runbooks/accessibility-checklist.md`, `docs/runbooks/first-deployment.md`, `docs/product/cost-evidence.md`, and `docs/product/performance-budgets.md`.

## Global Constraints

- The public product remains static HTML, CSS, JavaScript, and versioned JSON with no production API, database, broker, or server process.
- Generated events and browser replay remain labelled as simulated data.
- The GitHub Pages path is `/PortFlow/`, and compiled assets plus versioned datasets must resolve below that path.
- The release record must distinguish a passing check from an environment-blocked check and must not claim V1 complete while a required PF-030 item is unresolved.
- Evidence is dated `2026-09-16` and identifies the exact release commit under review.
- No credentials, secrets, private customer data, paid services, or new dependencies may enter the repository.
- The frontend verification wrapper runs its existing browser-oriented suite with one worker because the two-worker setting reproduced nondeterministic focus/navigation failures under this Windows environment.

---

### Task 1: Establish the release evidence baseline

**Files:**
- Read: `docs/product/BACKLOG.md`, `docs/design/PORTFLOW_UI_SPEC.md`, `docs/runbooks/accessibility-checklist.md`, `docs/runbooks/first-deployment.md`, `docs/product/cost-evidence.md`, `docs/product/performance-budgets.md`
- Create: `docs/releases/v1-checklist.md`

**Interfaces:**
- Consumes: the current `HEAD`, the expected Pages URL `https://hamdaoui-ali.github.io/PortFlow/`, and the repository’s existing release commands.
- Produces: a checklist schema with release identity, dated command evidence, manual UX evidence, responsive screenshot references, deployment checks, cost review, known limitations, and an explicit release decision.

- [x] **Step 1: Capture the immutable repository identity**

Run from the isolated worktree:

```powershell
git status --short --branch
git rev-parse HEAD
git log -1 --format="%h %ad %s" --date=iso-strict
git remote get-url origin
```

Record the exact commit, branch, remote, and clean/dirty state in the checklist. If the worktree is dirty because of release evidence files, identify those files separately from the source tree under review.

- [x] **Step 2: Define the release checklist sections**

Use these section headings and required fields in `docs/releases/v1-checklist.md`:

```markdown
# PortFlow V1 Release Checklist

## Release identity
## Automated evidence
## Manual accessibility and responsive evidence
## Responsive screenshots
## Public deployment evidence
## Cost-evidence review
## Known limitations
## Release decision
```

Each automated row must include `Check`, `Command`, `Date`, `Result`, and `Evidence`. Each manual row must include `Check`, `Viewport/browser`, `Observation`, `Result`, and `Date`, matching `docs/runbooks/accessibility-checklist.md`.

- [x] **Step 3: Add the acceptance matrix before collecting results**

List the required PF-030 outcomes: complete Python/data/frontend verification, Pages-path verification, performance-budget verification, Lighthouse verification, `git diff --check`, keyboard/focus checks, detail return-focus checks, 320px/375px overflow checks, reduced-motion behavior, responsive screenshots, public URL/HTTP 200 checks, cost-evidence review, simulated-data disclosure, and known limitations.

### Task 2: Run the release-equivalent automated gates

**Files:**
- Modify: `docs/releases/v1-checklist.md`
- Modify: `scripts/verify_r2.ps1`, `tests/unit/test_ci_quality_gate.py`
- Inspect: `scripts/verify_r2.ps1`, `scripts/check_budgets.py`, `web/scripts/verify-pages-build.mjs`, `.github/workflows/ci.yml`, `.github/workflows/pages.yml`

**Interfaces:**
- Consumes: the existing seeded PostgreSQL pipeline and committed public snapshot.
- Produces: fresh exit-code evidence for the complete release gate and a clear environment limitation if Docker or another required dependency is unavailable.

- [x] **Step 1: Run the complete release gate**

Run:

```powershell
pwsh ./scripts/verify_r2.ps1
```

Record each named stage and its final exit code. The command must generate the snapshot, assert no public-data diff, run Python tests/lint/types, run frontend tests including failure states, typecheck, build, performance budgets, and Lighthouse. If it stops before a stage, record the exact blocker and do not convert that result to `PASS`.

- [x] **Step 2: Run the standalone static checks**

Run:

```powershell
git diff --check
$env:VITE_BASE_PATH = "/PortFlow/"
npm --prefix web run build
npm --prefix web run verify:pages
Remove-Item Env:VITE_BASE_PATH -ErrorAction SilentlyContinue
```

Record exit codes and the generated artifact path. Preserve the current working-tree snapshot; if a build or pipeline rewrites checked-in data, explain the diff before continuing.

- [x] **Step 3: Reconcile any blocked environment evidence**

If the complete gate cannot run because Docker Desktop’s Linux engine is unavailable, run the non-container checks that are safe in the isolated worktree, record the Docker command and exact error as `BLOCKED`, and keep the V1 decision `INCOMPLETE` until the complete gate is rerun in an environment with the required PostgreSQL service.

Docker was available for the final run, so the complete gate passed and no container-blocked result was recorded. The separate public deployment blocker is recorded in `docs/releases/v1-checklist.md`.

### Task 3: Capture visual and manual product evidence

**Files:**
- Read: `docs/design/portflow-overview-desktop-concept.png`, `docs/design/portflow-overview-mobile-concept.png`
- Modify: `docs/releases/v1-checklist.md`
- Modify: `web/src/features/overview/AvailabilityTrend.tsx`, `web/src/features/equipment/EquipmentPage.tsx`, `web/src/features/equipment/EquipmentTable.tsx`, `web/src/styles.css`, and their focused tests

**Interfaces:**
- Consumes: the production `web/dist` artifact served below `/PortFlow/` and the approved desktop/mobile visual references.
- Produces: viewport-specific observations and screenshot references covering the first viewport hierarchy, disclosure, KPI focus, tables, navigation, and responsive behavior.

- [x] **Step 1: Serve the built Pages-path artifact**

Start the checked-in server from `web` with:

```powershell
$env:VITE_BASE_PATH = "/PortFlow/"
node scripts/lighthouse-server.mjs
```

Open `http://127.0.0.1:4173/PortFlow/` in the in-app Chromium browser and keep the same tab for the manual checks. Do not present this local URL as the public deployment URL.

- [x] **Step 2: Inspect desktop composition**

At `1600×960`, record whether the page preserves the approved left rail, quiet header, filter band, KPI rail, analytical region, and data-health strip; confirm no generic bento cards, gradients, glow, or translucent overlays appear. Capture a screenshot for the release evidence directory if the browser surface supports local capture.

- [x] **Step 3: Inspect mobile composition**

At `375×812` and `320×812`, record whether the mobile header, two-column filters, KPI rail, stacked content, bounded tables, and fixed bottom navigation remain usable without page-level overflow. Capture both viewport states and reference the files from the checklist.

- [x] **Step 4: Run the manual accessibility checklist**

Complete every row in `docs/runbooks/accessibility-checklist.md` against Chromium. Use keyboard-only navigation for skip link, primary content, controls, detail-page return focus, and visible focus outlines. Enable reduced motion and confirm the Live Demo keeps the same logical state/content without animation dependence. Record `PASS` only when the observation is directly verified.

- [x] **Step 5: Verify the core routes and disclosure**

Visit `#overview`, `#equipment`, `#incidents`, `#live-demo`, and `#data-health`. Confirm the simulation disclosure remains visible where required, route navigation is deterministic, the availability and operational status are text-readable, and each page remains within the approved visual system.

### Task 4: Record deployment, cost, and known-limit evidence

**Files:**
- Modify: `docs/releases/v1-checklist.md`
- Create: `CHANGELOG.md`

**Interfaces:**
- Consumes: the exact public Pages URL, the cost ledger’s dated official sources, and the known integration limitation recorded in PF-029.
- Produces: a reviewable release record and a changelog that does not overstate an incomplete release.

- [x] **Step 1: Verify the public deployment URL**

Check `https://hamdaoui-ali.github.io/PortFlow/` and the expected asset/data paths with HTTP requests. Record status codes for `index.html`, hashed CSS/JavaScript, `data/manifest.json`, all manifest datasets, and `brand/portflow-mark.png`. Confirm the page visibly says `Simulated terminal operations data` and the committed snapshot values match the release record.

- [x] **Step 2: Review the cost ledger**

Re-read `docs/product/cost-evidence.md` and record its verification date, GitHub Free/Pages/Actions sources, no-billing boundary, and fallback host/local-artifact path. If a policy source cannot be rechecked, record that limitation instead of inventing a current policy claim.

- [x] **Step 3: Write the changelog**

Create `CHANGELOG.md` with an `Unreleased` entry dated `2026-09-16`. Summarize the static control-tower views, deterministic local pipeline, replay/demo, Data Health/local workspace, accessibility/responsive hardening, Pages-path safety, and the exact PF-030 gate status. Use `V1` wording only when the checklist’s release decision is `PASS`; otherwise label the entry as unreleased and name the blocking evidence.

- [x] **Step 4: Record known limitations**

Include the documented simulated-data boundary, no live commercial feed, no production runtime backend, local API loopback-only scope, disposable PostgreSQL requirement, and any fresh environment/deployment limitation observed during this gate.

### Task 5: Perform the final evidence review

**Files:**
- Modify: `docs/releases/v1-checklist.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: every result collected in Tasks 1–4.
- Produces: a consistent release decision with no unverified completion language.

- [x] **Step 1: Check every required row**

Verify each PF-030 acceptance row has a dated observation, result, and evidence reference. A missing, blocked, or failed required row forces `INCOMPLETE`.

- [x] **Step 2: Validate documentation quality**

Run:

```powershell
rg -n "T[D]B|TO[D]O|FIX[M]E|PLACE[H]OLDER" docs/releases/v1-checklist.md CHANGELOG.md
git diff --check
```

The search must return no placeholder markers, and `git diff --check` must exit `0`.

- [x] **Step 3: Review the final diff**

Run:

```powershell
git status --short
git diff -- docs/releases/v1-checklist.md CHANGELOG.md
```

Confirm that only the PF-030 plan/release artifacts changed and that no generated private data, credentials, build output, or unrelated source edits are present.

- [x] **Step 4: Commit the release record**

After fresh verification, commit:

```powershell
git add docs/superpowers/plans/2026-09-16-portflow-v1-release-gate.md docs/releases/v1-checklist.md CHANGELOG.md
git commit -m "docs: record PortFlow V1 release gate"
```

If the release decision is `INCOMPLETE`, keep the commit as an auditable evidence checkpoint and leave the backlog’s PF-030 status unchanged.
