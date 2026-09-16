# PortFlow V1 Release Checklist

**Evidence date:** 2026-09-16
**Decision:** PASS - PortFlow V1 is published and the PF-030 acceptance evidence is complete.

## Release identity

| Field | Value |
|---|---|
| Repository | `https://github.com/Hamdaoui-Ali/PortFlow` |
| Released commit | `c735701aefe9769a207c24300beb610f1868aa92` (`c735701`, merged release commit) |
| Source release commit | `4156222f35d291e9f589951ac0d921e105b6bc32` (`4156222`, `docs: record PortFlow V1 release gate`) |
| Branch under review | `main` |
| Working-tree state | The release-gate changes are merged. GitHub Actions run #16 published the static artifact, and run #17 passed CI for the merged commit. |
| Expected public URL | `https://hamdaoui-ali.github.io/PortFlow/` |
| Pages path | `/PortFlow/` |
| Pages source | GitHub Actions |
| `github-pages` deployment branch | `main` |

The evidence below covers the merged release commit and the publication follow-up. The public site is now
available at the expected Pages URL.

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
| CI on merged `main` | [GitHub Actions run #17](https://github.com/Hamdaoui-Ali/PortFlow/actions/runs/35089136861) | 2026-09-16 | PASS | The merged commit completed the `verify` job successfully in 3m 12s; 32 frontend files and 189 frontend tests passed. |
| Publish PortFlow on merged `main` | [GitHub Actions run #16](https://github.com/Hamdaoui-Ali/PortFlow/actions/runs/35089136870) | 2026-09-16 | PASS | The `build` job passed in 2m 46s and the `deploy` job passed in 8s. The Pages artifact was 361 KB with digest `sha256:fe0d87e3b366aeebfe9c19ca2396261c8b43f9abdf3cb3dbef684d93a44e594a`. |
| Public HTTP 200 matrix | PowerShell `Invoke-WebRequest -Method Head` against the expected URL and required asset/data paths | 2026-09-16 | PASS | The root, `index.html`, hashed assets, manifest, all `demo-v2` datasets, and brand mark returned HTTP 200 after publication. |
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
| Reduced motion removes animation/transition dependence without hiding state changes | 375px / Edge with `prefers-reduced-motion: reduce` emulated through Puppeteer | `matchMedia` matched the reduced-motion preference, no live motion nodes remained (`activeMotionNodes=0`), the skip-link transition was `none`, and activating Start replay produced `Replay playing`. | PASS | 2026-09-16 |

The 320px hardening removes the document-wide minimum width, hides only repeated trend labels while retaining all hourly points, constrains narrow chart bars, stacks the KPI rail, and lets the fixed navigation items shrink to their available columns. The 375px layout retains the approved two-column mobile KPI treatment.

## Responsive screenshots

| Capture | Viewport / browser | Observation | Result | Date |
|---|---|---|---|---|
| Desktop overview | 1600x900 / Edge | Left navigation rail, quiet header, filter band, divider-based KPI rail, analytical region, and availability strip are visible. No gradient, glow, glass, or generic bento treatment appeared. | PASS | 2026-09-16 |
| Mobile overview | 375x812 / Edge | Header, filters, KPI content, disclosure controls, and fixed five-item navigation remain legible and usable. | PASS | 2026-09-16 |
| Narrow mobile overview | 320x812 / Edge | The screenshot showed the full shell without page-level horizontal overflow; the five-item navigation and two-column filters remain usable. | PASS | 2026-09-16 |

Screenshots were emitted as in-session Edge captures. The available browser-control surface does not provide a persisted local screenshot path, so no screenshot files are claimed in this repository.

## Public deployment evidence

The repository Pages source is set to **GitHub Actions**. The `github-pages` environment allows the `main` branch,
and the [Publish PortFlow run #16](https://github.com/Hamdaoui-Ali/PortFlow/actions/runs/35089136870) completed both
build and deploy jobs successfully.

The expected URL was checked with HTTP `HEAD` requests after deployment on 2026-09-16. Every requested endpoint
returned `200`:

| Endpoint | Status | Result |
|---|---:|---|
| `/PortFlow/` | 200 | PASS |
| `/PortFlow/index.html` | 200 | PASS |
| `/PortFlow/assets/index-BhiVShsi.css` | 200 | PASS |
| `/PortFlow/assets/index-B1Ov2rTn.js` | 200 | PASS |
| `/PortFlow/data/manifest.json` | 200 | PASS |
| `/PortFlow/data/snapshots/demo-v2/equipment.json` | 200 | PASS |
| `/PortFlow/data/snapshots/demo-v2/event-replay.json` | 200 | PASS |
| `/PortFlow/data/snapshots/demo-v2/incidents.json` | 200 | PASS |
| `/PortFlow/data/snapshots/demo-v2/overview.json` | 200 | PASS |
| `/PortFlow/data/snapshots/demo-v2/quality.json` | 200 | PASS |
| `/PortFlow/brand/portflow-mark.png` | 200 | PASS |

The public page visibly says `Simulated terminal operations data` and renders the committed `demo-v2` values:
4 moves, 94.4% availability, 63.8 minutes average dwell, 30 minutes MTTR, and 1 active incident.

## Public visible-page evidence

The deployed site was opened in Microsoft Edge after the HTTP matrix passed. Route navigation and the core
published content were directly visible:

| Route | Observation | Result | Date |
|---|---|---|---|
| `#overview` | `Terminal Operations Control Tower`, simulation disclosure, and `94.4%` equipment availability are visible. | PASS | 2026-09-16 |
| `#equipment` | `Equipment fleet` is visible with the published `QC-001` record and `94.4%` availability. | PASS | 2026-09-16 |
| `#incidents` | `Incident exploration` and `Operational incidents` are visible with two incidents and one open incident. | PASS | 2026-09-16 |
| `#live-demo` | `Live Demo` is visible with the simulation disclosure, replay controls, and `Snapshot availability 94.4%`. | PASS | 2026-09-16 |
| `#data-health` | `Data Health` is visible with `Stale`, `PASS` pipeline status, and zero quarantined/rejected records. | PASS | 2026-09-16 |

## Cost-evidence review

The existing [cost-evidence ledger](../product/cost-evidence.md) was re-read on 2026-09-16. Its source verification date remains 2026-09-02 and it covers:

- [GitHub Free billing](https://docs.github.com/en/billing/get-started/how-billing-works);
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits);
- [GitHub-hosted runner limits](https://docs.github.com/en/actions/reference/runners/github-hosted-runners); and
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

The published product uses GitHub Pages and GitHub-hosted Actions under the existing documented free boundary. The
release adds no paid runner, billing account, public API, database, broker, or new package. The ledger's documented
free-host fallback and preserved local `web/dist` artifact path remain the recovery options. This is a ledger review,
not a fresh vendor-policy re-verification.

## Known limitations

- The public product is a static snapshot. Its generated events and browser replay are simulated and not a live commercial terminal feed.
- There is no production API, database, broker, authentication layer, or server process in the public build.
- The local API is loopback-only and requires disposable local PostgreSQL state; it is never exposed to the public browser.
- `demo-v2` was generated on 2026-09-02 and is labelled stale by Data Health relative to the 2026-09-16 review date.
- The repository's `main` branch protection rules are not configured; the `github-pages` environment is restricted to `main` and the deploy job is also guarded to `refs/heads/main`. Configure the documented pull-request and green-CI rules before the next production change.
- The local environment did not expose a `pwsh` executable, so the PowerShell wrapper was invoked through Windows PowerShell with `COMPOSE_PROJECT_NAME='portflow'` while reusing the healthy database container.

## Release decision

**PASS - PortFlow V1 is published at `https://hamdaoui-ali.github.io/PortFlow/`.**

The local build, deterministic data pipeline, frontend suite, Pages-path checks, performance budgets, Lighthouse
assertions, responsive checks, keyboard skip-link behavior, detail return focus, reduced-motion probe, public HTTP
matrix, simulated-data disclosure, and core route checks all pass. PF-030 is complete. Main branch protection is a
separate repository-hardening follow-up and does not change the published static product or this PF-030 acceptance
decision.

Next action: configure the documented pull-request and green-CI protection rule for `main`, then begin the post-V1
backlog with PF-101.
