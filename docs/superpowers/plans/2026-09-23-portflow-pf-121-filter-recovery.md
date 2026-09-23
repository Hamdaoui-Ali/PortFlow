# PF-121 Implementation Plan — Consistent Filter Recovery

**Worktree:** `.worktrees/pf-121-filter-recovery`
**Branch:** `codex/pf-121-filter-recovery`
**Base:** `origin/main` after PF-120 merge (`a17f144`)

## Architecture

Keep the recovery contract in the web layer. Extend `SnapshotFilterScope` with
the validated terminal ID, add a pure support predicate, and render one shared
`FilterRecoveryState` from Overview, Equipment, and Incidents. Pass the already
derived scope and existing `resetFilters` callback through `AppContent`.

The reset remains owned by `AppShell`, so URL semantics, hash preservation,
and focus recovery stay centralized. No snapshot, API, database, or pipeline
changes are required.

## Commit sequence

1. Add this design and implementation record.
2. Add RED tests for the terminal ID and supported-scope predicate.
3. Implement the scope predicate and terminal ID field.
4. Add RED tests for the shared recovery state and Overview copy parity.
5. Implement the shared recovery state.
6. Add RED tests for Equipment and Incidents unsupported terminal/range states
   and reset behavior.
7. Wire the shared scope and reset callback into Equipment and Incidents.
8. Refactor Overview to use the shared recovery state.
9. Add responsive styling only where the shared state needs it.
10. Update the backlog with the PF-121 review checkpoint and verification
    evidence.

## Test-first checkpoints

### Scope contract

- Run `npm --prefix web test -- --run src/app/filterScope.test.ts`.
- Expected RED: the scope lacks `terminalId` and the predicate is absent.
- Implement the smallest pure change, then rerun the focused tests and
  `npm --prefix web run typecheck`.

### Shared recovery state

- Add tests asserting stable heading, published scope, reset button, and no
  route data for an unsupported selection.
- Run the focused component tests before implementing the shared component.
- Keep the Overview wording stable so existing user-facing assertions remain
  meaningful.

### Operational routes

- Start with a failing Equipment test for `TM-002` and `7d`.
- Add the equivalent Incident test.
- Assert reset clears query parameters, preserves `#equipment` or `#incidents`,
  restores `all`/`24h`, and returns focus to main.
- Implement route wiring only after the failures are observed.

## Verification gate

From the worktree, run:

```powershell
npm --prefix web test -- --run
npm --prefix web run typecheck
npm --prefix web run build
python scripts/check_budgets.py
./scripts/verify_r2.ps1
```

Also verify the rendered mismatch state at desktop and mobile widths. Before
opening a PR, run `git diff --check`, confirm the worktree is clean apart from
intended commits, push the feature branch, and request the repository's normal
CI/SonarCloud/CodeRabbit checks.
