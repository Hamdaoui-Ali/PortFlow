from datetime import UTC, datetime
from pathlib import Path

import pytest

from portflow.ingestion.cursor import CursorStore, SourceCursor


def test_equal_timestamps_are_ordered_by_primary_key() -> None:
    cursor = SourceCursor(datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000010")
    candidates = [
        (datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000011"),
        (datetime(2026, 9, 2, 1, tzinfo=UTC), "evt-000042-000009"),
    ]
    assert max(candidates) > (cursor.updated_at, cursor.primary_key)


def test_failed_cursor_write_keeps_previous_state(tmp_path: Path) -> None:
    store = CursorStore(tmp_path / "cursors.json")
    original = SourceCursor(datetime(2026, 9, 2, tzinfo=UTC), "evt-000042-000001")
    store.save({"telemetry_events": original})
    original_bytes = (tmp_path / "cursors.json").read_bytes()
    with pytest.raises(OSError):
        store.save(
            {
                "telemetry_events": SourceCursor(
                    datetime(2026, 9, 2, tzinfo=UTC), "evt-000042-000002"
                )
            },
            replace=lambda *_: (_ for _ in ()).throw(OSError("disk full")),
        )
    assert (tmp_path / "cursors.json").read_bytes() == original_bytes
    assert store.load()["telemetry_events"] == original
