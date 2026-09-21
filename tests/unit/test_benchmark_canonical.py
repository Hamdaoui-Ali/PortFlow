from datetime import UTC, datetime, timedelta, timezone

import pytest
from benchmarks.portflow_benchmarks.canonical import canonicalize_rows, result_sha256
from benchmarks.portflow_benchmarks.models import WorkloadSpec


def test_canonicalizer_sorts_rows_rounds_numbers_and_hashes_stably() -> None:
    rows = [
        {
            "terminal_id": "TM-002",
            "state": "IDLE",
            "event_count": 2,
            "available_event_count": 2,
            "average_load_percent": 10.1234567,
            "average_temperature_c": -1.2345678,
        },
        {
            "terminal_id": "TM-001",
            "state": "ACTIVE",
            "event_count": 3,
            "available_event_count": 3,
            "average_load_percent": 42.5,
            "average_temperature_c": 18.0,
        },
    ]

    canonical = canonicalize_rows(rows)

    assert canonical == [
        {
            "terminal_id": "TM-001",
            "state": "ACTIVE",
            "event_count": 3,
            "available_event_count": 3,
            "average_load_percent": 42.5,
            "average_temperature_c": 18.0,
        },
        {
            "terminal_id": "TM-002",
            "state": "IDLE",
            "event_count": 2,
            "available_event_count": 2,
            "average_load_percent": 10.123457,
            "average_temperature_c": -1.234568,
        },
    ]
    assert result_sha256(rows) == result_sha256(list(reversed(rows)))
    assert len(result_sha256(rows)) == 64


def test_canonicalizer_rejects_missing_result_fields() -> None:
    with pytest.raises(ValueError, match="missing result fields"):
        canonicalize_rows([{ "terminal_id": "TM-001" }])


def test_workload_spec_requires_utc_and_a_forward_window() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=1)
    naive_start = datetime(2026, 1, 1)
    non_utc_start = start.astimezone(timezone(timedelta(hours=1)))

    assert WorkloadSpec(window_start=start, window_end=end).window_start == start
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        WorkloadSpec(window_start=naive_start, window_end=end)
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        WorkloadSpec(window_start=non_utc_start, window_end=end)
    with pytest.raises(ValueError, match="after window_start"):
        WorkloadSpec(window_start=start, window_end=start)
