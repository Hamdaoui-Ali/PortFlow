import math

import pytest
from benchmarks.portflow_benchmarks.timing import summarize_timings


def test_summarize_timings_returns_median_and_nearest_rank_p95() -> None:
    summary = summarize_timings([3.0, 1.0, 2.0])

    assert summary.median_seconds == 2.0
    assert summary.p95_seconds == 3.0


@pytest.mark.parametrize("samples", [[], [-0.1, 0.2], [math.nan, 0.2], [math.inf]])
def test_summarize_timings_rejects_invalid_samples(samples: list[float]) -> None:
    with pytest.raises(ValueError, match="timing samples"):
        summarize_timings(samples)
