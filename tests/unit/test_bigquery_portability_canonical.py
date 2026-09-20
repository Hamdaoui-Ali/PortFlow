import hashlib
from datetime import UTC, datetime, timedelta, timezone

import pytest
from labs.portflow_bigquery.canonical import (
    RESULT_FIELDS,
    canonicalize_rows,
    result_sha256,
)


def _row(terminal_id: str = "TM-001") -> dict[str, object]:
    return {
        "terminal_id": terminal_id,
        "source_period_start": datetime(2026, 1, 1, tzinfo=UTC),
        "source_period_end": datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        "available_intervals": 3,
        "scheduled_intervals": 4,
        "active_intervals": 2,
        "available_time_minutes": 15,
        "resolved_incident_count": 1,
        "repair_minutes": 10.0,
        "qualifying_failure_count": 1,
        "operating_hours": 1 / 3,
        "throughput": 1,
        "average_dwell_minutes": 30.0,
        "availability": 0.75,
        "utilization": 2 / 3,
        "mttr_minutes": 10.0,
        "mtbf_hours": 1 / 3,
        "active_incidents": 1,
        "critical_alarms": 1,
    }


def test_result_fields_match_the_task_3_projection_contract() -> None:
    assert RESULT_FIELDS == (
        "terminal_id",
        "source_period_start",
        "source_period_end",
        "available_intervals",
        "scheduled_intervals",
        "active_intervals",
        "available_time_minutes",
        "resolved_incident_count",
        "repair_minutes",
        "qualifying_failure_count",
        "operating_hours",
        "throughput",
        "average_dwell_minutes",
        "availability",
        "utilization",
        "mttr_minutes",
        "mtbf_hours",
        "active_incidents",
        "critical_alarms",
    )


def test_canonicalizer_normalizes_aware_timestamps_and_float_precision() -> None:
    row = _row()
    row["source_period_start"] = datetime(
        2026,
        1,
        1,
        1,
        tzinfo=timezone(timedelta(hours=1)),
    )

    result = canonicalize_rows([row])

    assert result[0]["source_period_start"] == "2026-01-01T00:00:00Z"
    assert result[0]["operating_hours"] == 0.333333
    assert result[0]["utilization"] == 0.666667


def test_canonicalizer_preserves_allowed_null_metrics() -> None:
    row = _row()
    row["average_dwell_minutes"] = None
    row["mttr_minutes"] = None

    result = canonicalize_rows([row])

    assert result[0]["average_dwell_minutes"] is None
    assert result[0]["mttr_minutes"] is None


def test_canonicalizer_sorts_rows_by_terminal_id() -> None:
    result = canonicalize_rows([_row("TM-002"), _row("TM-001")])

    assert [row["terminal_id"] for row in result] == ["TM-001", "TM-002"]


def test_result_hash_is_independent_of_input_order() -> None:
    first = [_row("TM-002"), _row("TM-001")]
    second = list(reversed(first))

    assert result_sha256(first) == result_sha256(second)


def test_result_hash_uses_sorted_key_json_with_a_final_newline() -> None:
    payload = (
        '[{"active_incidents":1,"active_intervals":2,"availability":0.75,'
        '"available_intervals":3,"available_time_minutes":15,'
        '"average_dwell_minutes":30.0,"critical_alarms":1,"mtbf_hours":0.333333,'
        '"mttr_minutes":10.0,"operating_hours":0.333333,'
        '"qualifying_failure_count":1,"repair_minutes":10.0,'
        '"resolved_incident_count":1,"scheduled_intervals":4,'
        '"source_period_end":"2026-01-01T00:15:00Z",'
        '"source_period_start":"2026-01-01T00:00:00Z","terminal_id":"TM-001",'
        '"throughput":1,"utilization":0.666667}]\n'
    )

    assert result_sha256([_row()]) == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_canonicalizer_rejects_missing_and_unexpected_fields() -> None:
    missing = _row()
    del missing["throughput"]

    with pytest.raises(ValueError, match="missing result fields"):
        canonicalize_rows([missing])

    unexpected = _row()
    unexpected["unexpected"] = 1

    with pytest.raises(ValueError, match="unexpected result fields"):
        canonicalize_rows([unexpected])


def test_canonicalizer_rejects_boolean_integer_fields() -> None:
    row = _row()
    row["throughput"] = True

    with pytest.raises(ValueError, match="integer"):
        canonicalize_rows([row])


def test_canonicalizer_rejects_naive_timestamps() -> None:
    row = _row()
    row["source_period_start"] = datetime(2026, 1, 1)

    with pytest.raises(ValueError, match="timezone-aware"):
        canonicalize_rows([row])


def test_canonicalizer_rejects_non_finite_metrics() -> None:
    row = _row()
    row["availability"] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        canonicalize_rows([row])


def test_canonicalizer_rejects_nulls_outside_nullable_metrics() -> None:
    row = _row()
    row["repair_minutes"] = None

    with pytest.raises(ValueError, match="null"):
        canonicalize_rows([row])
