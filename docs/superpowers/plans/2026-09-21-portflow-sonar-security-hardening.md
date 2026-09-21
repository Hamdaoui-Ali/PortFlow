# PortFlow Sonar Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the hard-coded credential and unsafe dependency-install findings that give the repository an E Security Rating on new code, and add a repository-local CodeRabbit review policy.

**Architecture:** Runtime code will no longer contain a PostgreSQL password. Local and CI callers provide `PORTFLOW_DATABASE_URL` and/or a per-run `PORTFLOW_POSTGRES_PASSWORD`; the disposable Compose service consumes that value through environment substitution. GitHub Actions will pin the uv installer to a binary-only version and install npm dependencies with lifecycle scripts disabled. CodeRabbit will review the Python, frontend, workflow, Compose, and test boundaries with security-focused path instructions and static-analysis tools enabled.

**Tech Stack:** Python 3.12, pytest, PowerShell, Docker Compose, GitHub Actions, npm, CodeRabbit YAML configuration, JSON Schema validation.

## Global Constraints

- No database password literal may remain in runtime source, Compose, CI workflow, scripts, example environment files, or active runbooks.
- CI must keep a working PostgreSQL service and deterministic public snapshot.
- Per-run CI credentials must not be committed, echoed, or reused between runs.
- `uv` installation must use a pinned version and binary-only wheels.
- `npm ci` in GitHub Actions must use `--ignore-scripts`.
- CodeRabbit configuration must not enable autonomous commits or broaden review scope to generated artifacts and lockfiles.
- Existing local API, pipeline, streaming, Pages, and test contracts must remain intact.

## Review Focus

- A clean clone with no database environment must fail with an actionable configuration message rather than silently using a committed credential.
- CI and Pages must pass the same generated password to PostgreSQL and PortFlow without exposing it in logs.
- Compose interpolation must reject an unset password before starting a database with unsafe defaults.
- Package installation must remain reproducible and avoid arbitrary build/lifecycle scripts.
- CodeRabbit YAML must validate against the published schema and focus security review on database, workflow, Compose, Python, and frontend paths.

---

### Task 1: Pin the security regression tests and CodeRabbit contract tests

**Files:**
- Modify: `tests/unit/test_ci_quality_gate.py`
- Modify: `tests/unit/test_pages_workflow.py`
- Create: `tests/unit/test_security_configuration.py`

- [ ] **Step 1: Write failing tests**

Add assertions that runtime defaults contain no password, Compose uses an environment-only PostgreSQL password, CI and Pages define a non-literal per-run password and matching database URL, all GitHub Actions install `uv` with `--only-binary=:all:` and an exact version, npm installs use `--ignore-scripts`, and `.coderabbit.yaml` enables the required tools/path instructions without auto-commit settings.

- [ ] **Step 2: Run the new tests and observe the intended failures**

Run:

```powershell
python -m uv run --frozen pytest -q tests/unit/test_security_configuration.py tests/unit/test_ci_quality_gate.py tests/unit/test_pages_workflow.py
```

Expected: failures identify the committed database password, unpinned uv install, lifecycle-script install, and missing CodeRabbit policy.

- [ ] **Step 3: Commit the failing contract tests**

```powershell
git add tests/unit/test_security_configuration.py tests/unit/test_ci_quality_gate.py tests/unit/test_pages_workflow.py
git commit -m "test: define Sonar security hardening contracts"
```

### Task 2: Remove committed PostgreSQL credentials from runtime and local boundaries

**Files:**
- Modify: `src/portflow/db/connection.py`
- Modify: `src/portflow/local_api.py`
- Modify: `scripts/run_local_pipeline.py`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `docs/runbooks/local-development.md`
- Modify: `docs/runbooks/local-streaming.md`
- Modify: `tests/integration/conftest.py`
- Modify: `tests/e2e/conftest.py`
- Modify: `tests/resilience/conftest.py`

- [ ] **Step 1: Implement password-free defaults**

Use a credential-free PostgreSQL URL default (`postgresql://portflow@localhost:5433/portflow`) and require callers to set `PORTFLOW_DATABASE_URL` or a local password through the documented environment. Make `local_api.py` reuse the connection module’s default instead of duplicating a URL.

- [ ] **Step 2: Require Compose credentials through environment substitution**

Replace the literal `POSTGRES_PASSWORD` and Grafana fallback password with required environment substitutions. Keep ports loopback/local and update the runbooks and `.env.example` to show how to generate disposable local values without committing them.

- [ ] **Step 3: Update test fixtures and run focused tests**

Use the credential-free URL fallback in integration, resilience, and e2e fixtures; CI will provide the authenticated URL. Run:

```powershell
python -m uv run --frozen pytest -q tests/unit/test_security_configuration.py tests/unit/test_local_api.py tests/unit/test_ci_quality_gate.py tests/unit/test_pages_workflow.py
```

- [ ] **Step 4: Commit the runtime boundary**

```powershell
git add src scripts compose.yaml .env.example docs/runbooks tests/integration/conftest.py tests/e2e/conftest.py tests/resilience/conftest.py
git commit -m "fix: remove committed database credentials"
```

### Task 3: Generate and propagate per-run CI credentials

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/pages.yml`
- Modify: `scripts/verify_r2.ps1`

- [ ] **Step 1: Add the environment propagation test**

Assert both workflows expose the same ephemeral password expression to the service and job, and that the verification script preserves/restores existing `PORTFLOW_DATABASE_URL` and `PORTFLOW_POSTGRES_PASSWORD` values while generating a random password only when absent.

- [ ] **Step 2: Implement CI and local script propagation**

Use the GitHub run identifier as the disposable service password in CI, build the matching URL from that value, and set `POSTGRES_PASSWORD` from the same expression. In `verify_r2.ps1`, generate a local random value with `Guid.NewGuid()` when needed before `docker compose up`, then restore both environment variables in `finally`.

- [ ] **Step 3: Run workflow/script contract tests**

```powershell
python -m uv run --frozen pytest -q tests/unit/test_security_configuration.py tests/unit/test_ci_quality_gate.py tests/unit/test_pages_workflow.py
```

- [ ] **Step 4: Commit the CI credential propagation**

```powershell
git add .github/workflows/ci.yml .github/workflows/pages.yml scripts/verify_r2.ps1 tests/unit/test_security_configuration.py
git commit -m "ci: generate disposable database credentials per run"
```

### Task 4: Harden dependency installation and add CodeRabbit review policy

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/pages.yml`
- Modify: `.github/workflows/streaming.yml`
- Create: `.coderabbit.yaml`
- Modify: `tests/unit/test_security_configuration.py`

- [ ] **Step 1: Implement pinned installation**

Pin `uv` to the repository’s verified version with `python -m pip install --only-binary=:all: uv==0.12.12`, and change every workflow’s frontend install to `npm --prefix web ci --ignore-scripts`.

- [ ] **Step 2: Add CodeRabbit configuration**

Enable assertive automatic reviews on `main`, disable review of lockfiles/generated output, enable Ruff, Semgrep, TruffleHog, Gitleaks, actionlint, zizmor, Checkov, yamllint, and ESLint, and add path instructions for Python/database code, tests, workflows/Compose, and React/TypeScript. Do not configure automatic commits.

- [ ] **Step 3: Validate YAML and CodeRabbit schema**

Run the repository contract tests plus a JSON Schema validation of `.coderabbit.yaml` against `https://coderabbit.ai/integrations/schema.v2.json` using the locked Python environment.

- [ ] **Step 4: Commit the tooling hardening**

```powershell
git add .github/workflows .coderabbit.yaml tests/unit/test_security_configuration.py
git commit -m "ci: harden installs and configure CodeRabbit security review"
```

### Task 5: Run all gates and review the branch

- [ ] **Step 1: Run targeted tests and static checks**

```powershell
python -m uv run --frozen pytest -q tests/unit/test_security_configuration.py tests/unit/test_ci_quality_gate.py tests/unit/test_pages_workflow.py
python -m uv run --frozen ruff check .
python -m uv run --frozen mypy src
git diff --check
```

- [ ] **Step 2: Scan the changed tree for credential/install regressions**

```powershell
rg -n "postgresql://[^\s]*:[^\s@]+@|POSTGRES_PASSWORD:\s*[^\$]|pip install uv(\s|$)|npm --prefix web ci(\s|$)" .github src scripts compose.yaml .env.example docs/runbooks
```

Expected: no committed PostgreSQL password, no unpinned uv install, and no npm install without `--ignore-scripts`.

- [ ] **Step 3: Run the full repository quality gate**

Run `./scripts/verify_r2.ps1` with Docker available, then inspect the SonarCloud analysis and CodeRabbit review on the PR.

- [ ] **Step 4: Self-review the complete diff**

Confirm local development remains documented, CI and Pages use matching database credentials, no public data changes are introduced, and CodeRabbit has no autonomous write configuration.

- [ ] **Step 5: Push, create the PR, fix remote failures, and merge**

Push `codex/sonar-security-hardening`, create a PR against `main`, wait for CI/SonarCloud/CodeRabbit, apply one focused commit per finding, and merge only after every required check is green.
