from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
PAGES_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pages.yml"


def _load_pages_workflow() -> dict:
    return yaml.safe_load(PAGES_WORKFLOW.read_text(encoding="utf-8"))


def _workflow_triggers(workflow: dict) -> dict:
    if "on" in workflow:
        return workflow["on"]
    return workflow[True]


def test_pages_build_uses_base_path_and_one_validated_artifact() -> None:
    workflow = _load_pages_workflow()
    build_job = workflow["jobs"]["build"]
    steps = build_job["steps"]

    triggers = _workflow_triggers(workflow)
    assert triggers["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in triggers
    assert workflow["concurrency"] == {
        "group": "github-pages",
        "cancel-in-progress": False,
    }
    assert build_job["timeout-minutes"] == 15

    quality_step = next(step for step in steps if step["name"] == "Run complete R2 quality gate")
    assert quality_step["env"]["VITE_BASE_PATH"] == "/PortFlow/"
    assert quality_step["run"] == "./scripts/verify_r2.ps1"

    verify_step = next(step for step in steps if step["name"] == "Verify Pages artifact")
    assert verify_step["run"] == "npm --prefix web run verify:pages"

    upload_steps = [
        step for step in steps if step.get("uses") == "actions/upload-pages-artifact@v4"
    ]
    assert len(upload_steps) == 1
    assert upload_steps[0]["with"]["path"] == "web/dist"


def test_pages_quality_gate_installs_optional_orchestration_dependencies() -> None:
    workflow = _load_pages_workflow()
    install_step = next(
        step
        for step in workflow["jobs"]["build"]["steps"]
        if step["name"] == "Install locked dependencies"
    )

    assert "python -m uv sync --extra dev --extra orchestration --frozen" in install_step["run"]


def test_pages_deploy_requires_main_and_pages_environment_protection() -> None:
    workflow = _load_pages_workflow()
    deploy_job = workflow["jobs"]["deploy"]

    assert deploy_job["if"] == "github.ref == 'refs/heads/main'"
    assert deploy_job["needs"] == "build"
    assert deploy_job["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert deploy_job["environment"]["name"] == "github-pages"
    deployment_step = next(step for step in deploy_job["steps"] if step["id"] == "deployment")
    assert deployment_step["uses"] == "actions/deploy-pages@v4"
