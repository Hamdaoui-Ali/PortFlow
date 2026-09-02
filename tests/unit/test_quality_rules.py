from tests.unit.factories import references, valid_telemetry_row

from portflow.quality.rules import validate_row


def test_bad_load_gets_range_invalid() -> None:
    row = valid_telemetry_row(load_percent=101)
    issues = validate_row("telemetry_events", row, references())
    assert [issue.code for issue in issues] == ["RANGE_INVALID"]


def test_unknown_equipment_gets_reference_missing() -> None:
    row = valid_telemetry_row(equipment_id="QC-999")
    issues = validate_row("telemetry_events", row, references())
    assert [issue.code for issue in issues] == ["REFERENCE_MISSING"]


def test_duplicate_identifier_gets_duplicate_key() -> None:
    row = valid_telemetry_row(event_id="evt-000042-000001")
    issues = validate_row(
        "telemetry_events",
        row,
        references(),
        seen_keys={"evt-000042-000001"},
    )
    assert [issue.code for issue in issues] == ["DUPLICATE_KEY"]
