# PortFlow V1 Release Checklist

**Evidence date:** 2026-09-16
**Decision:** INCOMPLETE - local verification is green, but the expected GitHub Pages site is not published.

## Release identity

| Field | Value |
|---|---|
| Repository | `https://github.com/Hamdaoui-Ali/PortFlow` |
| Branch under review | `codex/pf-030-release-gate` |
| Base `HEAD` at evidence start | `401c3aae10e1c3e45671f7f0a2935708fc119e58` (`401c3aa`, 2026-09-11T16:04:49+01:00, `docs: record bounded local API verification`) |
| Working-tree state | Dirty by design: PF-030 plan, release records, responsive/focus hardening, focused tests, and deterministic gate scheduling changes are under review. No generated public-data diff remains. |
| Expected public URL | `https://hamdaoui-ali.github.io/PortFlow/` |
| Pages path | `/PortFlow/` |

The evidence below covers the base commit plus the candidate changes listed in the working-tree state. This record does not claim that the candidate has been merged or published.

## Automated evidence

| Check | Command | Date | Result | Evidence |
|---|---|---|---|---|
| Deterministic snapshot generation and committed public-data check | `$env:COMPOSE_PROJECT_NAME='portflow'; & .\scripts\verify_r2.ps1` | 2026-09-16 | PASS | The wrapper generated `demo-v2`; `git diff --exit-code -- web/public/data` passed. The existing healthy `portflow-postgres-1` service was reused. |
| Python test suite | Included in the same wrapper | 2026-09-16 | PASS | 69 tests passed on Python 3.12.4 in 158.43 seconds. |
| Ruff | Included in the same wrapper | 2026-09-16 | PASS | `All checks passed!` |
| mypy | Included in the same wrapper | 2026-09-16 | PASS | `Success: no issues found in 26 source files`. |
| Frontend tests, including failure states | Included in the same wrapper | 2026-09-16 | PASS | 32 files and 189 tests passed. The wrapper uses one worker after the two-worker setting reproduced nondeterministic focus/navigation failures under this Windows environment. |
| Frontend typecheck and production build | Included in the same wrapper | 2026-09-16 | PASS | `tsc --noEmit` and Vite build passed. |
| Performance budgets | Included in the same wrapper | 2026-09-16 | PASS | Public snapshot: 47,103 bytes; JS/CSS bundle: 376,918 bytes; startup: 284,706 bytes. Limits are 100,000, 400,000, and 400,000 bytes. |
| Lighthouse runtime budgets | Included in the same wrapper | 2026-09-16 | PASS | Three local runs completed and all configured assertions passed. |
| Pages-path build | `$env:VITE_BASE_PATH='/PortFlow/'; npm --prefix web run build` | 2026-09-16 | PASS | Vite produced `web/dist` with `/PortFlow/` asset URLs. |
| Pages-path asset/data verification | `npm --prefix web run verify:pages` | 2026-09-16 | PASS | `Verified /PortFlow/ asset and data paths.` |
| Diff whitespace check | `git diff --check` | 2026-09-16 | PASS | Exit code 0. Git emitted only its normal LF/CRLF advice for four modified files. |
| Trend-label regression | `npm test -- --run src/features/overview/AvailabilityTrend.test.tsx src/styles.test.ts` | 2026-09-16 | PASS | 2 files and 2 tests passed. All 24 hourly points remain in the DOM; seven checkpoint labels are visible. |
| Equipment return-focus regression | `npm test -- --run src/features/equipment/EquipmentPage.test.tsx --maxWorkers=1` | 2026-09-16 | PASS | 11 tests passed, including focus restoration to the originating equipment control. |

## Manual accessibility and responsive evidence

The built static artifact was served locally at `http://127.0.0.1:4173/PortFlow/` in Microsoft Edge through the available browser-control surface. The local URL is not the public deployment URL.

| Check | Viewport / browser | Observation | Result | Date |
|---|---|---|---|---|
| Tab from the address bar reaches the skip link and then primary content | 320px / Edge | Keyboard focus reached `Skip to main content`; activating it focused `main-content`. | PASS | 2026-09-16 |
| Tab from the address bar reaches the skip link and then primary content | 375px / Edge | Keyboard focus reached `Skip to main content`; activating it focused `main-content`. | PASS | 2026-09-16 |
| Focus indicators remain visible on links, selects, buttons, details, and table controls | 320px and 375px / Edge | Keyboard focus on the KPI disclosure produced a solid focus outline using `rgb(6, 79, 196)`; the stylesheet covers links, selects, buttons, details, and table controls. | PASS | 2026-09-16 |
| Focus indicators remain visible on links, selects, buttons, details, and table controls | 375px / Edge | Route and table controls remained keyboard reachable in the accessibility tree, with the same focus styling. | PASS | 2026-09-16 |
| Equipment detail back action returns focus to the relevant list context | 375px / Edge | After opening `QC-001` and returning, focus was on `#equipment-link-QC-001` (`Open equipment QC-001`). | PASS | 2026-09-16 |
| Incident detail back action returns focus to the relevant list context | 375px / Edge | After opening `inc-000001` and returning, focus was on `#incident-link-inc-000001`. | PASS | 2026-09-16 |
| No page-level horizontal scroll appears | 320px / Edge | `documentWidth=277`, `clientWidth=277`, `bodyWidth=277`, `hasOverflow=false`. | PASS | 2026-09-16 |
| No page-level horizontal scroll appears | 375px / Edge | `documentWidth=327`, `clientWidth=327`, `bodyWidth=327`, `hasOverflow=false`. | PASS | 2026-09-16 |
| Reduced motion removes animation/transition dependence without hiding state changes | 375px / Edge with reduced motion enabled | The checked-in reduced-motion CSS rule and replay tests passed. The available browser-control surface does not expose a reduced-motion emulation toggle, so live preference emulation was not performed. | LIMITED - tooling gap | 2026-09-16 |

The 320px hardening removes the document-wide minimum width, hides only repeated trend labels while retaining all hourly points, constrains narrow chart bars, stacks the KPI rail, and lets the fixed navigation items shrink to their available columns. The 375px layout retains the approved two-column mobile KPI treatment.

## Responsive screenshots

| Capture | Viewport / browser | Observation | Result | Date |
|---|---|---|---|---|
| Desktop overview | 1600x900 / Edge | Left navigation rail, quiet header, filter band, divider-based KPI rail, analytical region, and availability strip are visible. No gradient, glow, glass, or generic bento treatment appeared. | PASS | 2026-09-16 |
| Mobile overview | 375x812 / Edge | Header, filters, KPI content, disclosure controls, and fixed five-item navigation remain legible and usable. | PASS | 2026-09-16 |
| Narrow mobile overview | 320x812 / Edge | The screenshot showed the full shell without page-level horizontal overflow; the five-item navigation and two-column filters remain usable. | PASS | 2026-09-16 |

Screenshots were emitted as in-session Edge captures. The available browser-control surface does not provide a persisted local screenshot path, so no screenshot files are claimed in this repository.

## Public deployment evidence

The expected URL was checked with HTTP `HEAD` requests on 2026-09-16. Every requested endpoint returned `404`:

| Endpoint | Status | Result |
|---|---:|---|
| `/PortFlow/` | 404 | BLOCKED |
| `/PortFlow/assets/index-BhiVShsi.css` | 404 | BLOCKED |
| `/PortFlow/assets/index-B1Ov2rTn.js` | 404 | BLOCKED |
| `/PortFlow/data/manifest.json` | 404 | BLOCKED |
| `/PortFlow/data/snapshots/demo-v2/equipment.json` | 404 | BLOCKED |
| `/PortFlow/data/snapshots/demo-v2/event-replay.json` | 404 | BLOCKED |
| `/PortFlow/data/snapshots/demo-v2/incidents.json` | 404 | BLOCKED |
| `/PortFlow/data/snapshots/demo-v2/overview.json` | 404 | BLOCKED |
| `/PortFlow/data/snapshots/demo-v2/quality.json` | 404 | BLOCKED |
| `/PortFlow/brand/portflow-mark.png` | 404 | BLOCKED |

The response was GitHub's `There isn't a GitHub Pages site here` page. Because the public page is absent, its visible simulation disclosure and public HTTP 200 checks cannot be marked as passed. The local Pages-path artifact does visibly say `Simulated terminal operations data` and renders the committed `demo-v2` values: 4 moves, 94.4% availability, 63.8 minutes average dwell, 30 minutes MTTR, and 1 active incident.

## Cost-evidence review

The existing [cost-evidence ledger](../product/cost-evidence.md) was re-read on 2026-09-16. Its source verification date remains 2026-09-02 and it covers:

- [GitHub Free billing](https://docs.github.com/en/billing/get-started/how-billing-works);
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits);
- [GitHub-hosted runner limits](https://docs.github.com/en/actions/reference/runners/github-hosted-runners); and
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

The candidate diff adds no external service, paid runner, billing account, public API, database, broker, or new package. The ledger's documented free-host fallback and preserved local `web/dist` artifact path remain the recovery options. This is a ledger review, not a fresh vendor-policy re-verification.

## Known limitations

- The public product is a static snapshot. Its generated events and browser replay are simulated and not a live commercial terminal feed.
- There is no production API, database, broker, authentication layer, or server process in the public build.
- The local API is loopback-only and requires disposable local PostgreSQL state; it is never exposed to the public browser.
- `demo-v2` was generated on 2026-09-02 and is labelled stale by Data Health relative to the 2026-09-16 review date.
- The expected GitHub Pages site is not currently provisioned; no push, repository-settings change, or publication action was taken in this review.
- The local environment did not expose a `pwsh` executable, so the PowerShell wrapper was invoked through Windows PowerShell with `COMPOSE_PROJECT_NAME='portflow'` while reusing the healthy database container.
- Reduced-motion behavior was covered by source rules and tests, but the browser-control surface could not emulate the preference live.

## Release decision

**INCOMPLETE - do not call this PortFlow V1 released.**

The local build, deterministic data pipeline, frontend suite, Pages-path checks, performance budgets, Lighthouse assertions, responsive checks, keyboard skip-link behavior, and detail return focus all pass. PF-030 remains open because the expected public URL and every required public asset/data path return HTTP 404. The reduced-motion row is also limited by browser tooling.

Next release action: configure the repository's GitHub Pages source to **GitHub Actions**, run the reviewed publish workflow on `main`, and repeat the HTTP matrix plus visible-page checks from `docs/runbooks/first-deployment.md`. Leave PF-030 open in `docs/product/BACKLOG.md` until those checks return HTTP 200 and the page is visibly available.
