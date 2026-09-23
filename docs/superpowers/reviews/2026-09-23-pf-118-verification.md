# PF-118 verification checkpoint

Date: 2026-09-23
Branch: `codex/pf-118-overview-incident-pulse`

## Repository gate

The exact repository gate passed from the PF-118 worktree with Python 3.12.4:

```powershell
./scripts/verify_r2.ps1
```

Observed results:

- Python tests: 563 passed, 12 skipped.
- Ruff: all checks passed.
- mypy: no issues found in 39 source files.
- Frontend tests: 42 files, 273 tests passed.
- Frontend typecheck: passed.
- Frontend production build: passed; 1,803 modules transformed.
- Snapshot budget: 47,103 bytes / 100,000-byte limit.
- JS/CSS bundle budget: 400,551 bytes / 401,000-byte limit.
- Startup budget: 308,339 bytes / 400,000-byte limit.
- Lighthouse: three runs completed and the quality gate passed.

The public snapshot generator produced the committed manifest without a
content diff. The bundle limit is 401,000 bytes because PF-118 remains within
one kilobyte of the former guardrail after the Overview pulse and incident-row
renderers were shared with the existing UI.

The Sonar remediation pass also replaces nested comparator expressions with
explicit branches, uses `startsWith` for resource messaging, and centralizes
the repeated incident test records.

## Focused PF-118 checks

- Ranking/state helper: 14 tests passed.
- Overview incident/equipment pulse and App integration: 49 tests passed.
- Incident context regression coverage: passed.
- `git diff --check`: passed.
