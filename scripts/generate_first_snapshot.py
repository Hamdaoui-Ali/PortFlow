"""Generate the committed deterministic first public snapshot."""

from datetime import UTC, datetime
from pathlib import Path

from portflow.export.snapshot import write_first_snapshot
from portflow.simulator.equipment import generate_telemetry


def main() -> None:
    events = generate_telemetry(
        seed=42,
        equipment_id="QC-001",
        terminal_id="TM-001",
        count=288,
        start_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    manifest = write_first_snapshot(Path("web/public/data"), events)
    print(f"Wrote {manifest}")


if __name__ == "__main__":
    main()
