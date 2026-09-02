"""Typed metadata for the versioned public snapshot contract."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class PublicSnapshotMetadata:
    """Stable source and generation boundaries written to manifest.json."""

    snapshot_id: str
    generated_at: datetime
    source_period_start: datetime
    source_period_end: datetime

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id must not be empty")
        timestamps = (
            self.generated_at,
            self.source_period_start,
            self.source_period_end,
        )
        if any(
            timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0)
            for timestamp in timestamps
        ):
            raise ValueError("snapshot timestamps must use UTC")
        if self.source_period_end < self.source_period_start:
            raise ValueError("source_period_end must not precede source_period_start")
        if self.generated_at < self.source_period_end:
            raise ValueError("generated_at must not precede source_period_end")
