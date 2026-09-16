from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
CI_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
QUALITY_GATE = REPOSITORY_ROOT / "scripts" / "verify_r2.ps1"

REQUIRED_COMMANDS = (
    "scripts/run_local_pipeline.py",
    "git diff --exit-code -- web/public/data",
    "pytest",
    "ruff check .",
    "mypy src",
    "npm --prefix web test -- --run --maxWorkers=1",
    "npm --prefix web run typecheck",
    "npm --prefix web run build",
    "scripts/check_budgets.py",
    "npm --prefix web run lighthouse",
)

REQUIRED_STAGE_LABELS = (
    "==> Generate deterministic public snapshot",
    "==> Verify generated public data is committed",
    "==> Run Python tests",
    "==> Run Ruff",
    "==> Run mypy",
    "==> Run frontend tests (including failure states)",
    "==> Typecheck frontend",
    "==> Build frontend",
    "==> Check performance budgets",
    "==> Run Lighthouse",
)


def test_ci_quality_gate_runs_required_stages_and_failure_suite() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    verify_job = workflow["jobs"]["verify"]
    quality_step = next(
        step for step in verify_job["steps"] if step["name"] == "Run complete R2 quality gate"
    )
    script = QUALITY_GATE.read_text(encoding="utf-8")

    assert verify_job["timeout-minutes"] == 15
    assert quality_step["shell"] == "pwsh"
    assert quality_step["run"] == "./scripts/verify_r2.ps1"
    assert '$env:PORTFLOW_FAILURE_TESTS = "1"' in script

    command_positions = [script.index(command) for command in REQUIRED_COMMANDS]
    assert command_positions == sorted(command_positions)
    for stage_label in REQUIRED_STAGE_LABELS:
        assert stage_label in script
