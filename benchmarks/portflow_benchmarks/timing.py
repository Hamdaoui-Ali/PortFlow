"""Timing aggregation for benchmark evidence."""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_WARMUPS = 1
DEFAULT_REPETITIONS = 3


@dataclass(frozen=True, slots=True)
class TimingSummary:
    """Summary statistics for timed samples only."""

    median_seconds: float
    p95_seconds: float


def summarize_timings(samples: Sequence[float]) -> TimingSummary:
    """Return median and nearest-rank p95 for finite non-negative samples."""
    if not samples or any(not math.isfinite(float(sample)) or sample < 0 for sample in samples):
        raise ValueError("timing samples must be non-empty, finite, and non-negative")
    ordered = sorted(float(sample) for sample in samples)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return TimingSummary(
        median_seconds=float(statistics.median(ordered)),
        p95_seconds=ordered[p95_index],
    )
