import re
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
WORKFLOW_ROOT = REPOSITORY_ROOT / ".github" / "workflows"


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_database_defaults_do_not_embed_passwords() -> None:
    paths = (
        "src/portflow/db/connection.py",
        "src/portflow/local_api.py",
        "scripts/run_local_pipeline.py",
        "scripts/run_local_api.py",
        ".env.example",
        "compose.yaml",
        "docs/runbooks/local-development.md",
        "docs/runbooks/local-streaming.md",
    )

    for relative_path in paths:
        content = _read(relative_path)
        assert not re.search(r"postgresql://[^\s]+:[^\s@]+@", content), relative_path
        assert "POSTGRES_PASSWORD: portflow" not in content, relative_path
        assert "PORTFLOW_GRAFANA_ADMIN_PASSWORD:-portflow" not in content, relative_path


def test_compose_requires_environment_supplied_credentials() -> None:
    compose = yaml.safe_load(_read("compose.yaml"))
    services = compose["services"]

    assert "PORTFLOW_POSTGRES_PASSWORD" in services["postgres"]["environment"]["POSTGRES_PASSWORD"]
    assert "PORTFLOW_GRAFANA_ADMIN_PASSWORD" in services["grafana"]["environment"][
        "GF_SECURITY_ADMIN_PASSWORD"
    ]


def test_database_workflows_use_one_ephemeral_password_source() -> None:
    for relative_path in (".github/workflows/ci.yml", ".github/workflows/pages.yml"):
        workflow = yaml.safe_load(_read(relative_path))
        job = workflow["jobs"]["verify" if relative_path.endswith("ci.yml") else "build"]
        password = "${{ github.run_id }}"

        assert job["env"]["PORTFLOW_POSTGRES_PASSWORD"] == password
        assert job["env"]["PORTFLOW_DATABASE_URL"] == (
            "postgresql://portflow:${{ github.run_id }}@localhost:5432/portflow"
        )
        assert job["services"]["postgres"]["env"]["POSTGRES_PASSWORD"] == password


def test_workflows_harden_python_and_frontend_installation() -> None:
    for relative_path in (
        ".github/workflows/ci.yml",
        ".github/workflows/pages.yml",
        ".github/workflows/streaming.yml",
    ):
        content = _read(relative_path)
        assert "python -m pip install --only-binary=:all: uv==0.12.12" in content
        assert "npm --prefix web ci --ignore-scripts" in content or "npm --prefix web ci" not in content
        assert "python -m pip install uv\n" not in content

    for relative_path in (".github/workflows/ci.yml", ".github/workflows/pages.yml"):
        content = _read(relative_path)
        assert "npm --prefix web ci\n" not in content


def test_verify_script_generates_and_restores_local_database_password() -> None:
    content = _read("scripts/verify_r2.ps1")

    assert "PORTFLOW_POSTGRES_PASSWORD" in content
    assert "[Guid]::NewGuid().ToString(\"N\")" in content
    assert "Remove-Item Env:PORTFLOW_POSTGRES_PASSWORD" in content


def test_coderabbit_is_configured_for_security_review_without_auto_commits() -> None:
    config = yaml.safe_load(_read(".coderabbit.yaml"))
    reviews = config["reviews"]

    assert reviews["profile"] == "assertive"
    assert reviews["auto_review"] == {
        "enabled": True,
        "auto_incremental_review": True,
        "drafts": False,
    }
    assert "!**/*.lock" in reviews["path_filters"]
    assert "!web/dist/**" in reviews["path_filters"]

    required_tools = {"ruff", "semgrep", "trufflehog", "gitleaks", "actionlint", "zizmor", "checkov", "yamllint", "eslint"}
    assert required_tools <= set(reviews["tools"])
    assert {item["path"] for item in reviews["path_instructions"]} >= {
        "**/*.py",
        ".github/workflows/**/*.{yml,yaml}",
        "web/**/*.{ts,tsx}"
    }
    assert "finishing_touches" not in reviews or "auto_commit" not in str(reviews["finishing_touches"])
