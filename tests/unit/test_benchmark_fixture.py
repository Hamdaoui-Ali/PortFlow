from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest
from benchmarks.portflow_benchmarks.fixture import FixtureSpec, generate_fixture

from portflow.domain.models import EquipmentState

EXPECTED_COLUMNS = [
    "event_id",
    "equipment_id",
    "terminal_id",
    "event_timestamp",
    "state",
    "available",
    "load_percent",
    "temperature_c",
]


def test_fixture_is_deterministic_and_matches_telemetry_contract(tmp_path: Path) -> None:
    spec = FixtureSpec(seed=42, rows=32)
    first = generate_fixture(spec, tmp_path / "first")
    second = generate_fixture(spec, tmp_path / "second")

    assert first.rows == second.rows == 32
    assert first.logical_sha256 == second.logical_sha256
    assert first.schema == second.schema
    assert first.file_count == second.file_count == 1

    first_frame = pl.read_parquet(next((tmp_path / "first").glob("*.parquet")))
    second_frame = pl.read_parquet(next((tmp_path / "second").glob("*.parquet")))
    assert first_frame.columns == EXPECTED_COLUMNS
    assert first_frame.equals(second_frame)
    assert first_frame.height == 32
    assert first_frame.schema["event_timestamp"].time_zone == "UTC"
    assert first_frame.get_column("event_id").str.contains(r"^evt-\d{6}-\d{6}$").all()
    assert first_frame.get_column("equipment_id").str.contains(r"^[A-Z]{2,4}-\d{3}$").all()
    assert first_frame.get_column("terminal_id").str.contains(r"^TM-\d{3}$").all()
    assert first_frame.get_column("load_percent").min() >= 0.0
    assert first_frame.get_column("load_percent").max() <= 100.0
    assert first_frame.get_column("temperature_c").min() >= -20.0
    assert first_frame.get_column("temperature_c").max() <= 150.0

    unavailable_states = {
        EquipmentState.UNAVAILABLE.value,
        EquipmentState.MAINTENANCE.value,
    }
    expected_available = ~first_frame.get_column("state").is_in(list(unavailable_states))
    assert first_frame.get_column("available").equals(expected_available)
    assert first_frame.get_column("event_timestamp")[0].utcoffset() == timedelta(0)


@pytest.mark.parametrize("rows", [0, -1])
def test_fixture_rejects_non_positive_row_count(rows: int) -> None:
    with pytest.raises(ValueError, match="rows must be positive"):
        FixtureSpec(seed=42, rows=rows)


def test_fixture_rejects_negative_seed() -> None:
    with pytest.raises(ValueError, match="seed must be non-negative"):
        FixtureSpec(seed=-1, rows=1)


def test_fixture_rejects_unsupported_compression() -> None:
    with pytest.raises(ValueError, match="compression must be zstd"):
        FixtureSpec(seed=42, rows=1, compression="snappy")


def test_fixture_rejects_symlinked_output_root(tmp_path: Path) -> None:
    target_root = tmp_path / "target-fixture"
    target_root.mkdir()
    linked_root = tmp_path / "fixture"
    try:
        linked_root.symlink_to(target_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ValueError, match="fixture output path"):
        generate_fixture(FixtureSpec(seed=42, rows=1), linked_root)
