import pytest

from portflow.analytics.formulas import calculate_fixture_case
from tests.unit.factories import load_case


@pytest.mark.parametrize(
    ("case_name", "expected"),
    [
        (
            "normal",
            {
                "availability": 0.75,
                "utilization": 2 / 3,
                "mttr_minutes": 30.0,
                "mtbf_hours": 4.0,
            },
        ),
        (
            "empty_denominators",
            {
                "availability": None,
                "utilization": None,
                "mttr_minutes": None,
                "mtbf_hours": None,
            },
        ),
        (
            "boundary_timestamps",
            {"throughput": 2, "average_dwell_minutes": 45.0},
        ),
    ],
)
def test_kpi_fixture(
    case_name: str,
    expected: dict[str, float | int | None],
) -> None:
    assert calculate_fixture_case(load_case(case_name)) == expected
