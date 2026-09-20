import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest
from labs.portflow_bigquery import paths, runner
from labs.portflow_bigquery.manifest import ManifestVerificationError
from labs.portflow_bigquery.runner import RunSpec, run_bundle, verify_bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bundle_parent() -> Iterator[Path]:
    # The amended plan requires this worktree-local test root. Override only
    # the test default; retain the real containment/reparse checks everywhere.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(paths, "DEFAULT_ARTIFACT_ROOT", Path(".portability/test-bigquery"))
        patch.setenv("DBT_SEND_ANONYMOUS_USAGE_STATS", "false")
        root = paths.resolve_artifact_root(repository_root=ROOT)
        root.mkdir(parents=True, exist_ok=True)
        # Task 8 owns the repository ignore rule; keep these test artifacts ignored now.
        ignore = paths.resolve_artifact_path(root, ".gitignore")
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        with TemporaryDirectory(prefix="task6-", dir=root) as temporary:
            yield Path(temporary)


def _protected_files() -> dict[str, bytes]:
    files = [
        path
        for name in ("analytics/models", "web/public/data", "data")
        for path in (ROOT / name).rglob("*")
        if path.is_file()
    ]
    files.extend(ROOT.glob("*compose*.y*ml"))
    return {str(path.relative_to(ROOT)): path.read_bytes() for path in files}


@pytest.fixture(scope="module")
def original(bundle_parent: Path) -> Path:
    protected = _protected_files()
    output = bundle_parent / "original"
    manifest = run_bundle(RunSpec(repository_root=ROOT, output_root=output))
    assert manifest["task"] == "PF-106"
    assert manifest["cloud_execution"] == "not_run"
    assert manifest["verification"] == {
        "status": "ok",
        "reason_code": None,
        "verifier_version": "1",
    }
    assert _protected_files() == protected
    return output


@pytest.fixture
def bundle(original: Path, bundle_parent: Path) -> Iterator[Path]:
    with TemporaryDirectory(prefix="copy-", dir=bundle_parent) as temporary:
        output = Path(temporary)
        shutil.copytree(original, output, dirs_exist_ok=True)
        yield output


def test_real_bundle_is_repeatable_and_has_exact_hashes(
    original: Path, bundle_parent: Path
) -> None:
    second = bundle_parent / "repeat"
    run_bundle(RunSpec(repository_root=ROOT, output_root=second))
    for name in (
        "manifest.json",
        "overview_kpis.sql",
        "schema.json",
        "expected-result.json",
        "input-fingerprint.json",
    ):
        assert (original / name).read_bytes() == (second / name).read_bytes()
    manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    for section, name in (("query", "overview_kpis.sql"), ("schema", "schema.json")):
        assert (
            manifest[section]["sha256"]
            == hashlib.sha256((original / name).read_bytes()).hexdigest()
        )
    rows = json.loads((original / "expected-result.json").read_text(encoding="utf-8"))
    assert rows[0]["critical_alarms"] == 1
    assert rows[0]["availability"] == 0.75
    assert rows[0]["utilization"] == 0.666667
    assert rows[0]["source_period_start"] == "2026-01-01T00:00:00Z"
    canonical_bytes = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    assert manifest["reference"]["result_sha256"] == hashlib.sha256(canonical_bytes).hexdigest()
    text = (original / "manifest.json").read_text(encoding="utf-8")
    assert str(ROOT) not in text
    assert ROOT.as_posix() not in text
    assert "traceback" not in text.lower()
    verify_bundle(original / "manifest.json", repository_root=ROOT)


@pytest.mark.parametrize(
    ("name", "reason"),
    [("overview_kpis.sql", "query_hash_mismatch"), ("schema.json", "schema_hash_mismatch")],
)
def test_text_tamper_has_specific_reason(bundle: Path, name: str, reason: str) -> None:
    artifact = bundle / name
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    with pytest.raises(ManifestVerificationError) as error:
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)
    assert error.value.reason_code == reason


def test_result_value_tamper_is_rejected(bundle: Path) -> None:
    path = bundle / "expected-result.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["critical_alarms"] = 999
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^result_hash_mismatch$"):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)


def test_result_formatting_and_parquet_layout_do_not_change_logical_hashes(bundle: Path) -> None:
    result = bundle / "expected-result.json"
    rows = json.loads(result.read_text(encoding="utf-8"))
    result.write_text(json.dumps(rows, indent=4), encoding="utf-8")
    table = bundle / "fixture" / "telemetry_events"
    frame = pl.read_parquet(table / "part-000000.parquet")
    frame.tail(2).write_parquet(table / "part-000000.parquet")
    frame.head(2).reverse().write_parquet(table / "other.parquet")
    verify_bundle(bundle / "manifest.json", repository_root=ROOT)


def test_fixture_value_tamper_is_rejected(bundle: Path) -> None:
    path = bundle / "fixture" / "telemetry_events" / "part-000000.parquet"
    pl.read_parquet(path).with_columns(pl.lit(False).alias("available")).write_parquet(path)
    with pytest.raises(ManifestVerificationError, match="^fixture_hash_mismatch$"):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("overview_kpis.sql", "query_hash_mismatch"),
        ("schema.json", "schema_hash_mismatch"),
        ("expected-result.json", "result_hash_mismatch"),
        ("fixture/alarms/part-000000.parquet", "fixture_hash_mismatch"),
    ],
)
def test_missing_or_corrupt_artifact_is_bounded(bundle: Path, name: str, reason: str) -> None:
    artifact = bundle / name
    for corrupt in (True, False):
        if corrupt:
            artifact.write_bytes(b"\xffnot an artifact")
        else:
            artifact.unlink()
        with pytest.raises(ManifestVerificationError) as error:
            verify_bundle(bundle / "manifest.json", repository_root=ROOT)
        assert error.value.reason_code == reason


def test_parser_runs_even_when_query_hash_matches(bundle: Path) -> None:
    query = bundle / "overview_kpis.sql"
    query.write_bytes(b"SELECT * FROM private_table")
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["query"]["sha256"] = hashlib.sha256(query.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        verify_bundle(path, repository_root=ROOT)


@pytest.mark.parametrize("kind", ["query", "schema", "fixture", "result", "manifest"])
def test_verifier_rejects_linked_artifacts(bundle: Path, original: Path, kind: str) -> None:
    name = {
        "query": "overview_kpis.sql",
        "schema": "schema.json",
        "fixture": "fixture/alarms/part-000000.parquet",
        "result": "expected-result.json",
        "manifest": "manifest.json",
    }[kind]
    target = bundle / name
    target.unlink()
    try:
        target.symlink_to(original / name)
    except OSError:
        pytest.skip("host cannot create symbolic links")
    with pytest.raises(ManifestVerificationError, match="^artifact_path_invalid$"):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)


def test_failed_run_replaces_success_with_bounded_error(
    bundle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gold_paths: list[Path] = []

    def fail(*, repository_root: Path, fixture_root: Path, gold_db: Path) -> None:
        gold_paths.append(gold_db)
        assert repository_root == gold_db.parent
        assert (repository_root / "analytics" / "selectors.yml").is_file()
        model = Path("analytics/models/marts/overview_kpis.sql")
        assert (repository_root / model).read_bytes() == (ROOT / model).read_bytes()
        assert fixture_root == bundle / "fixture"
        assert gold_db.parent.exists()
        assert not gold_db.is_relative_to(bundle)
        assert (bundle / "overview_kpis.sql").is_file()
        assert (bundle / "schema.json").is_file()
        raise ValueError("dbt_reference_failed private traceback C:/secret")

    monkeypatch.setattr(runner, "run_local_reference", fail)
    spec = RunSpec(repository_root=ROOT, output_root=bundle)
    with pytest.raises(ValueError, match="dbt_reference_failed"):
        run_bundle(spec)
    text = (bundle / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert manifest["verification"] == {
        "status": "error",
        "reason_code": "run_failed",
        "verifier_version": "1",
    }
    assert "dbt_reference_failed" not in text
    assert "private" not in text
    assert not gold_paths[0].parent.exists()
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)
