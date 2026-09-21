"""Data contracts shared by benchmark fixture, engines, and reports."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

EngineStatus = Literal["ok", "unavailable", "error"]


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    """Parameters that define one deterministic benchmark fixture."""

    seed: int
    rows: int
    generator_version: str = "1"
    compression: Literal["zstd"] = "zstd"

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be non-negative")
        if isinstance(self.rows, bool) or not isinstance(self.rows, int) or self.rows <= 0:
            raise ValueError("rows must be positive")
        if not self.generator_version:
            raise ValueError("generator_version must not be empty")
        if self.compression != "zstd":
            raise ValueError("compression must be zstd")


@dataclass(frozen=True, slots=True)
class FixtureMetadata:
    """Measured identity and physical metadata for a generated fixture."""

    seed: int
    rows: int
    generator_version: str
    compression: str
    fixture_dir: Path
    file_count: int
    bytes: int
    logical_sha256: str
    schema: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkloadSpec:
    """A half-open UTC time window for the shared benchmark workload."""

    window_start: datetime
    window_end: datetime

    def __post_init__(self) -> None:
        for name, value in (("window_start", self.window_start), ("window_end", self.window_end)):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{name} must be timezone-aware UTC")
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")


@dataclass(frozen=True, slots=True)
class EngineExecution:
    """One engine execution and its canonical result rows."""

    name: str
    version: str
    startup_seconds: float
    warmup_seconds: float
    timed_seconds: tuple[float, ...]
    rows_per_second: float
    result_sha256: str
    status: EngineStatus = "ok"
    reason_code: str | None = None
    result_rows: tuple[dict[str, object], ...] = ()
