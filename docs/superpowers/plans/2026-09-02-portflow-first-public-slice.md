# PortFlow First Public Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one tested equipment-availability KPI from deterministic PortFlow data as a publicly accessible static page with no runtime backend.

**Architecture:** A seeded Python simulator produces typed telemetry records and calculates one Gold availability KPI. A versioned JSON snapshot is generated into the Vite public directory, validated by the React application, and deployed to GitHub Pages after tests pass.

**Tech Stack:** Python 3.12, Pydantic, pytest, React, TypeScript, Vite, Vitest, Testing Library, Zod, GitHub Actions, GitHub Pages

**Spec:** `docs/superpowers/specs/2026-09-02-portflow-zero-cost-web-product-design.md`

## Global Constraints

- The public product requires no billing account, payment card, public API, or running developer machine.
- The frontend consumes only a versioned public snapshot contract.
- Generated events and browser replay must be labelled as simulated data.
- All timestamps are UTC and serialized with a `Z` suffix.
- Identical input seeds must produce identical logical data and snapshot hashes.
- No Redpanda, Dagster, Prometheus, Grafana, PySpark, Terraform, or cloud lab enters this slice.
- Publication occurs only after Python, data-contract, frontend, and build checks pass.

## File map

```text
PORTFLOW_ENHANCED_PRODUCT_STUDY.md        authoritative product study
docs/product/cost-evidence.md             dated vendor-policy evidence
docs/adr/0001-static-public-product.md    public-hosting boundary
docs/adr/0002-snapshot-contract.md         data/UI interface decision
pyproject.toml                             Python package and test configuration
src/portflow/domain/models.py              typed telemetry and KPI models
src/portflow/simulator/equipment.py        deterministic event generator
src/portflow/analytics/availability.py     first Gold KPI calculation
src/portflow/export/snapshot.py            public JSON and hash writer
tests/unit/                                focused Python behavior tests
tests/integration/test_first_snapshot.py   source-to-export contract test
web/package.json                           frontend commands and dependencies
web/src/data/schema.ts                     runtime public-contract validation
web/src/data/loadSnapshot.ts               manifest and dataset loader
web/src/features/overview/                 first visible KPI slice
web/src/app/App.tsx                        application root
web/public/data/                            generated deterministic fixture
scripts/generate_first_snapshot.py         pipeline command entry point
scripts/verify.ps1                         cross-platform verification entry point
.github/workflows/ci.yml                   pull-request quality gate
.github/workflows/pages.yml                protected static deployment
```

---

### Task 1: Verify the permanent-$0 boundary (PF-001 and PF-002)

**Files:**
- Create: `docs/product/cost-evidence.md`
- Create: `docs/adr/0001-static-public-product.md`
- Create: `docs/adr/0002-snapshot-contract.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Official GitHub Free, Pages, and Actions documentation available on the verification date.
- Produces: A dated evidence row with fields `service`, `official_url`, `verified_at`, `billing_requirement`, `relevant_limit`, `risk`, and `fallback`.

- [ ] **Step 1: Create the evidence-table structure**

Add this header to `docs/product/cost-evidence.md`:

```markdown
# PortFlow Cost Evidence

This ledger validates only services required by the permanent V1 architecture.

| Service | Official URL | Verified at | Billing requirement | Relevant limit | Risk | Fallback |
|---|---|---|---|---|---|---|
```

- [ ] **Step 2: Verify each required service in Chrome**

Open the official GitHub documentation for GitHub Free, GitHub Pages, and GitHub Actions. Add one row per service using the exact policy text summarized in original words. Do not add search-result URLs or third-party sources.

- [ ] **Step 3: Apply the cost gate**

If any required service needs a billing account or payment card, stop this plan and revise the architecture. If quotas apply without billing, record the quota and a static-host fallback.

- [ ] **Step 4: Write the static-product ADR**

Record:

```markdown
# ADR 0001: Static public product

## Status
Accepted

## Decision
PortFlow V1 is published as static HTML, CSS, JavaScript, and versioned data assets. It has no production API, database, broker, or server process.

## Consequences
The product remains available without a running developer machine. Public writes, authentication, and genuine live streaming are outside V1.
```

- [ ] **Step 5: Write the snapshot-boundary ADR**

Record that Gold-to-JSON export is the only pipeline/UI interface, the manifest is versioned, and invalid exports cannot be published.

- [ ] **Step 6: Verify the documents**

Run:

```powershell
rg -n "official_url|T[B]D|T[O]DO|third-party" docs/product/cost-evidence.md docs/adr
```

Expected: official URLs are present and no incomplete-work marker appears.

- [ ] **Step 7: Commit**

```powershell
git add README.md docs/product/cost-evidence.md docs/adr/0001-static-public-product.md docs/adr/0002-snapshot-contract.md
git commit -m "docs: verify PortFlow zero-cost boundary"
```

---

### Task 2: Establish tested Python and frontend workspaces (PF-003)

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `src/portflow/__init__.py`
- Create: `tests/unit/test_package.py`
- Create: `web/package.json`
- Create: `web/package-lock.json`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/src/smoke.test.ts`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `scripts/verify.ps1`

**Interfaces:**
- Consumes: None.
- Produces: `python -m pytest`, `npm --prefix web test -- --run`, `npm --prefix web run build`, and `pwsh ./scripts/verify.ps1`.

- [ ] **Step 1: Write the failing Python smoke test**

```python
from portflow import APP_NAME


def test_package_name() -> None:
    assert APP_NAME == "PortFlow"
```

- [ ] **Step 2: Run the Python test and observe the import failure**

Run: `python -m pytest tests/unit/test_package.py -v`

Expected: FAIL because `portflow` or `APP_NAME` does not exist.

- [ ] **Step 3: Create the minimal Python package**

`src/portflow/__init__.py`:

```python
APP_NAME = "PortFlow"
```

Configure `pyproject.toml` with the `src` package layout, Python 3.12 minimum, Pydantic, pytest, Ruff, mypy, and PyYAML. Configure pytest to use `tests` and strict markers. Generate and commit `uv.lock`.

- [ ] **Step 4: Run the Python check**

Run: `python -m pytest tests/unit/test_package.py -v`

Expected: PASS.

- [ ] **Step 5: Write the failing frontend smoke test**

`web/src/smoke.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { APP_NAME } from "./app/constants";

describe("application identity", () => {
  it("uses the PortFlow name", () => {
    expect(APP_NAME).toBe("PortFlow");
  });
});
```

- [ ] **Step 6: Run the frontend test and observe the missing module**

Run: `npm --prefix web test -- --run`

Expected: FAIL because `./app/constants` does not exist.

- [ ] **Step 7: Create the frontend constant and configuration**

`web/src/app/constants.ts`:

```typescript
export const APP_NAME = "PortFlow" as const;
```

Configure Vite, React, TypeScript strict mode, Vitest with jsdom, Testing Library, Zod, and build/test/typecheck scripts. Generate and commit `web/package-lock.json`.

- [ ] **Step 8: Create the verification entry point**

`scripts/verify.ps1`:

```powershell
$ErrorActionPreference = "Stop"
python -m pytest
python -m ruff check .
python -m mypy src
npm --prefix web test -- --run
npm --prefix web run typecheck
npm --prefix web run build
```

- [ ] **Step 9: Run all foundation checks**

Run: `pwsh ./scripts/verify.ps1`

Expected: every command exits `0`.

- [ ] **Step 10: Commit**

```powershell
git add pyproject.toml src tests web .gitignore .env.example scripts/verify.ps1
git commit -m "build: establish tested PortFlow workspaces"
```

---

### Task 3: Define and generate deterministic telemetry (PF-004 and PF-005)

**Files:**
- Create: `src/portflow/domain/models.py`
- Create: `src/portflow/simulator/equipment.py`
- Create: `tests/unit/test_telemetry_contract.py`
- Create: `tests/unit/test_equipment_simulator.py`

**Interfaces:**
- Consumes: `seed: int`, `equipment_id: str`, `terminal_id: str`, `count: int`, `start_at: datetime`.
- Produces: `generate_telemetry(...) -> list[TelemetryEvent]`; `TelemetryEvent` includes `event_id`, `schema_version`, `equipment_id`, `terminal_id`, `event_timestamp`, `ingestion_timestamp`, `state`, `available`, `load_percent`, and `temperature_c`.

- [ ] **Step 1: Write contract tests**

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from portflow.domain.models import EquipmentState, TelemetryEvent


def test_telemetry_requires_utc_and_valid_ranges() -> None:
    event = TelemetryEvent(
        event_id="evt-000001",
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
        ingestion_timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=75.0,
        temperature_c=60.0,
    )
    assert event.schema_version == 1


def test_telemetry_rejects_load_above_one_hundred() -> None:
    with pytest.raises(ValidationError):
        TelemetryEvent(
            event_id="evt-000001",
            equipment_id="QC-001",
            terminal_id="TM-001",
            event_timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
            state=EquipmentState.ACTIVE,
            available=True,
            load_percent=101.0,
            temperature_c=60.0,
        )
```

- [ ] **Step 2: Run the contract tests**

Run: `python -m pytest tests/unit/test_telemetry_contract.py -v`

Expected: FAIL because the models do not exist.

- [ ] **Step 3: Implement the typed contract**

Use a string enum for `IDLE`, `ACTIVE`, `WARNING`, `UNAVAILABLE`, and `MAINTENANCE`. Use Pydantic constrained floats for `load_percent` from 0 through 100 and validate that both timestamps have UTC offsets.

- [ ] **Step 4: Run contract tests**

Run: `python -m pytest tests/unit/test_telemetry_contract.py -v`

Expected: PASS.

- [ ] **Step 5: Write deterministic simulator tests**

```python
from datetime import datetime, timezone

from portflow.simulator.equipment import generate_telemetry


def test_same_seed_produces_same_events() -> None:
    arguments = {
        "seed": 42,
        "equipment_id": "QC-001",
        "terminal_id": "TM-001",
        "count": 20,
        "start_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
    }
    first = generate_telemetry(**arguments)
    second = generate_telemetry(**arguments)
    assert first == second
    assert len({event.event_id for event in first}) == 20
```

- [ ] **Step 6: Run the simulator test**

Run: `python -m pytest tests/unit/test_equipment_simulator.py -v`

Expected: FAIL because `generate_telemetry` does not exist.

- [ ] **Step 7: Implement the minimal deterministic generator**

Use `random.Random(seed)`, five-minute UTC increments, stable event IDs derived from seed and sequence, and a transition table keyed by the current state. Calculate load first and derive temperature from state and load so the values remain correlated.

- [ ] **Step 8: Verify and commit**

Run: `python -m pytest tests/unit/test_telemetry_contract.py tests/unit/test_equipment_simulator.py -v`

Expected: PASS.

```powershell
git add src/portflow/domain src/portflow/simulator tests/unit
git commit -m "feat: generate deterministic equipment telemetry"
```

---

### Task 4: Calculate and export the first Gold KPI (PF-006)

**Files:**
- Create: `src/portflow/analytics/availability.py`
- Create: `src/portflow/export/snapshot.py`
- Create: `scripts/generate_first_snapshot.py`
- Create: `tests/unit/test_availability.py`
- Create: `tests/integration/test_first_snapshot.py`
- Generate: `web/public/data/manifest.json`
- Generate: `web/public/data/snapshots/demo-v1/overview.json`

**Interfaces:**
- Consumes: `calculate_availability(events: Sequence[TelemetryEvent])`.
- Produces: `AvailabilityKpi(available_intervals: int, scheduled_intervals: int, value: float | None)` and `write_first_snapshot(output_dir: Path, events: Sequence[TelemetryEvent]) -> Path` returning the manifest path.

- [ ] **Step 1: Write the failing KPI tests**

```python
from datetime import datetime, timedelta, timezone

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.analytics.availability import calculate_availability


def build_events(available: list[bool]) -> list[TelemetryEvent]:
    start = datetime(2026, 9, 2, tzinfo=timezone.utc)
    return [
        TelemetryEvent(
            event_id=f"evt-{index:06d}",
            equipment_id="QC-001",
            terminal_id="TM-001",
            event_timestamp=start + timedelta(minutes=5 * index),
            ingestion_timestamp=start + timedelta(minutes=5 * index),
            state=EquipmentState.ACTIVE if value else EquipmentState.UNAVAILABLE,
            available=value,
            load_percent=75.0 if value else 0.0,
            temperature_c=60.0 if value else 30.0,
        )
        for index, value in enumerate(available)
    ]


def test_availability_uses_available_over_scheduled() -> None:
    events = build_events([True, True, False, True])
    result = calculate_availability(events)
    assert result.available_intervals == 3
    assert result.scheduled_intervals == 4
    assert result.value == 0.75


def test_availability_is_unavailable_without_scheduled_intervals() -> None:
    result = calculate_availability([])
    assert result.value is None
```

- [ ] **Step 2: Run the KPI tests**

Run: `python -m pytest tests/unit/test_availability.py -v`

Expected: FAIL because the analytics module does not exist.

- [ ] **Step 3: Implement the KPI**

Count every telemetry fixture interval as scheduled for this first slice. Return `None` instead of zero when no interval exists. Keep presentation formatting out of Python.

- [ ] **Step 4: Write the failing export integration test**

```python
import json
from datetime import datetime, timezone

from portflow.export.snapshot import write_first_snapshot
from portflow.simulator.equipment import generate_telemetry


def test_snapshot_contains_version_hash_and_kpi(tmp_path) -> None:
    events = generate_telemetry(
        seed=42,
        equipment_id="QC-001",
        terminal_id="TM-001",
        count=20,
        start_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    manifest_path = write_first_snapshot(tmp_path, events)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    overview_path = tmp_path / manifest["datasets"]["overview"]["path"]
    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert len(manifest["datasets"]["overview"]["sha256"]) == 64
    assert overview["availability"]["value"] is not None
```

- [ ] **Step 5: Run the export test**

Run: `python -m pytest tests/integration/test_first_snapshot.py -v`

Expected: FAIL because the exporter does not exist.

- [ ] **Step 6: Implement canonical snapshot output**

Serialize JSON with sorted keys, UTF-8, compact separators, and a terminal newline. Calculate SHA-256 from the exact overview bytes. Derive `generated_at` from the maximum fixture ingestion timestamp so repeated generation is stable. Use snapshot ID `demo-v1` for the committed deterministic fixture. The manifest dataset path is `snapshots/demo-v1/overview.json`.

- [ ] **Step 7: Add the generation command**

`scripts/generate_first_snapshot.py` calls `generate_telemetry` with seed `42`, terminal `TM-001`, equipment `QC-001`, 288 five-minute events, and UTC start `2026-09-01T00:00:00Z`, then writes to `web/public/data`.

- [ ] **Step 8: Verify deterministic output**

Run the generator twice and compare repository state:

```powershell
python -m uv run python scripts/generate_first_snapshot.py
git diff --exit-code -- web/public/data
python -m pytest tests/unit/test_availability.py tests/integration/test_first_snapshot.py -v
```

Expected: the second generation creates no diff and all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add src/portflow/analytics src/portflow/export scripts/generate_first_snapshot.py tests web/public/data
git commit -m "feat: export deterministic availability snapshot"
```

---

### Task 5: Render the first public KPI page (PF-007)

**Files:**
- Create: `web/src/data/schema.ts`
- Create: `web/src/data/loadSnapshot.ts`
- Create: `web/src/features/overview/AvailabilityCard.tsx`
- Create: `web/src/features/overview/AvailabilityCard.test.tsx`
- Create: `web/src/app/App.tsx`
- Create: `web/src/app/App.test.tsx`
- Create: `web/src/main.tsx`
- Create: `web/index.html`
- Create: `web/src/styles.css`

**Interfaces:**
- Consumes: `${import.meta.env.BASE_URL}data/manifest.json` and the manifest's `datasets.overview.path` resolved under the same base URL.
- Produces: `loadSnapshot(fetcher?: typeof fetch): Promise<{ manifest: ManifestV1; overview: OverviewV1 }>` and `<AvailabilityCard value: number | null generatedAt: string />`.

- [ ] **Step 1: Define runtime schemas**

Create Zod schemas that require manifest schema version `1`, a 64-character lowercase hexadecimal SHA-256 value, an overview relative path, and an availability value between 0 and 1 or `null`. Export inferred `ManifestV1` and `OverviewV1` types.

- [ ] **Step 2: Write the failing card test**

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AvailabilityCard } from "./AvailabilityCard";

describe("AvailabilityCard", () => {
  it("renders the percentage, definition, and snapshot time", () => {
    render(<AvailabilityCard value={0.75} generatedAt="2026-09-02T00:00:00Z" />);
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText(/available intervals divided by scheduled intervals/i)).toBeInTheDocument();
    expect(screen.getByText(/2 September 2026/i)).toBeInTheDocument();
  });

  it("does not invent a value", () => {
    render(<AvailabilityCard value={null} generatedAt="2026-09-02T00:00:00Z" />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the card test**

Run: `npm --prefix web test -- --run src/features/overview/AvailabilityCard.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 4: Implement the accessible card**

Render a semantic section with heading `Equipment availability`, formatted percentage or `Unavailable`, the fixed definition, and a `<time dateTime={generatedAt}>` element. Avoid status meaning through color alone.

- [ ] **Step 5: Write loader and app tests**

Test a successful manifest and overview request, invalid manifest rejection, invalid KPI rejection, loading UI, successful UI, and an error message with no fabricated KPI.

- [ ] **Step 6: Run the app tests**

Run: `npm --prefix web test -- --run src/app/App.test.tsx`

Expected: FAIL until loader and application states exist.

- [ ] **Step 7: Implement loader and application states**

Fetch the manifest from `${import.meta.env.BASE_URL}data/manifest.json` with `cache: "no-cache"`, resolve the overview relative path under `${import.meta.env.BASE_URL}data/`, validate both responses, and expose loading, success, and unavailable states. Pass `manifest.generated_at` to the card's `generatedAt` property. Use the heading `PortFlow Operations Control Tower` and text `Simulated terminal operations data`.

- [ ] **Step 8: Verify frontend behavior**

Run:

```powershell
npm --prefix web test -- --run
npm --prefix web run typecheck
npm --prefix web run build
```

Expected: all commands exit `0`; `web/dist/index.html` and copied data assets exist.

- [ ] **Step 9: Commit**

```powershell
git add web
git commit -m "feat: render first PortFlow operations KPI"
```

---

### Task 6: Add CI and GitHub Pages deployment (PF-007)

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/pages.yml`
- Modify: `web/vite.config.ts`
- Create: `docs/runbooks/first-deployment.md`

**Interfaces:**
- Consumes: `pwsh ./scripts/verify.ps1` and the `web/dist` artifact.
- Produces: A tested Pages deployment from protected `main` with repository-relative asset paths.

- [ ] **Step 1: Add the CI workflow**

Trigger on pull requests and pushes to `main`. Check out code, install Python 3.12 and Node 22, install from `uv.lock` and `web/package-lock.json`, run the snapshot generator, assert `git diff --exit-code -- web/public/data`, and execute `pwsh ./scripts/verify.ps1`.

- [ ] **Step 2: Run equivalent commands locally**

Run:

```powershell
python -m uv run python scripts/generate_first_snapshot.py
git diff --exit-code -- web/public/data
pwsh ./scripts/verify.ps1
```

Expected: no generated diff and exit code `0`.

- [ ] **Step 3: Configure the Pages base path**

Configure Vite with `base: process.env.VITE_BASE_PATH ?? "/"`. Set `VITE_BASE_PATH` to `/PortFlow/` in the deployment workflow and keep `/` for local development. Add a build test that confirms the production asset URLs and data requests use `/PortFlow/`.

- [ ] **Step 4: Add the deployment workflow**

Use official GitHub checkout, Pages configuration, artifact upload, and Pages deployment actions. Grant only `contents: read`, `pages: write`, and `id-token: write`. Use the `github-pages` environment and a deployment concurrency group that does not cancel an in-progress production deployment.

- [ ] **Step 5: Document repository settings**

In `docs/runbooks/first-deployment.md`, record how to select GitHub Actions as the Pages source, set main-branch protection, locate the published URL, verify assets, and revert by redeploying the last good commit.

- [ ] **Step 6: Validate workflow syntax and build artifact**

Parse both workflow files with PyYAML, then run the same install, generation, verification, and build commands declared in the workflows:

```powershell
python -c "import pathlib, yaml; [yaml.safe_load(path.read_text(encoding='utf-8')) for path in pathlib.Path('.github/workflows').glob('*.yml')]"
pwsh ./scripts/verify.ps1
```

Expected: workflow files parse and `web/dist` contains `index.html`, hashed assets, `data/manifest.json`, and the overview snapshot.

- [ ] **Step 7: Commit**

```powershell
git add .github web/vite.config.ts docs/runbooks/first-deployment.md
git commit -m "ci: publish tested PortFlow site to Pages"
```

---

### Task 7: Run the first-slice release gate

**Files:**
- Create: `docs/releases/first-public-slice.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Results from Tasks 1–6 and the public Pages URL.
- Produces: A dated evidence record for the first working vertical slice.

- [ ] **Step 1: Run clean verification**

From a clean clone or isolated worktree, install locked dependencies and run:

```powershell
python -m uv run python scripts/generate_first_snapshot.py
pwsh ./scripts/verify.ps1
git diff --exit-code
```

Expected: all checks pass and deterministic generation leaves no diff.

- [ ] **Step 2: Verify the public site**

Open the production URL in Chrome at desktop and mobile widths. Confirm the title, KPI, definition, generated time, simulation label, keyboard focus, refresh behavior, and absence of console or network errors.

- [ ] **Step 3: Verify failure behavior**

In a local preview, intercept `manifest.json` with an invalid schema version. Confirm the application shows an explicit unavailable state and no KPI value.

- [ ] **Step 4: Record release evidence**

In `docs/releases/first-public-slice.md`, record the commit, public URL, cost-evidence verification date, commands and exit codes, tested viewport sizes, accessibility observations, and known scope limits.

- [ ] **Step 5: Update the README**

Add the public URL, a two-sentence product description, local verification command, architecture link, and an explicit statement that this release uses simulated data and no public runtime backend.

- [ ] **Step 6: Commit**

```powershell
git add README.md docs/releases/first-public-slice.md
git commit -m "docs: record first public PortFlow release"
```

## Completion checkpoint

Stop after Task 7 and review the deployed vertical slice before starting PF-008. The next implementation plan should cover R2, **Trusted local pipeline**, and must preserve the snapshot interfaces established here.
