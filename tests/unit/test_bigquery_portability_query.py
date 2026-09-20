from pathlib import Path

import pytest
from labs.portflow_bigquery.query import (
    QueryValidationError,
    render_query,
    validate_google_sql,
)

ROOT = Path(__file__).parents[2]
TEMPLATE = (ROOT / "analytics" / "portability" / "bigquery" / "overview_kpis.sql").read_text(
    encoding="utf-8"
)


def test_rendered_contract_uses_bigquery_functions_and_no_tokens() -> None:
    sql = render_query(TEMPLATE, project_id="demo-project", dataset="portflow")

    assert "`demo-project.portflow.fct_equipment_telemetry`" in sql
    assert "COUNTIF" in sql
    assert "TIMESTAMP_DIFF" in sql
    assert "SAFE_DIVIDE" in sql
    assert "{{" not in sql
    assert "}}" not in sql
    validate_google_sql(sql)


@pytest.mark.parametrize(
    ("project_id", "dataset", "reason_code"),
    [
        ("", "portflow", "invalid_project_id"),
        ("demo-project", "bad.dataset", "invalid_dataset"),
    ],
)
def test_render_rejects_invalid_identifiers(
    project_id: str,
    dataset: str,
    reason_code: str,
) -> None:
    with pytest.raises(QueryValidationError) as error:
        render_query(TEMPLATE, project_id=project_id, dataset=dataset)

    assert error.value.reason_code == reason_code


@pytest.mark.parametrize(
    ("fragment", "reason_code"),
    [
        ("read_parquet('x')", "forbidden_duckdb_construct"),
        ("date_diff('second', a, b)", "forbidden_duckdb_construct"),
        ("COUNT(*) FILTER (WHERE ok)", "forbidden_duckdb_construct"),
        ("SELECT * FROM t", "implicit_select_star"),
    ],
)
def test_validator_rejects_nonportable_sql(fragment: str, reason_code: str) -> None:
    with pytest.raises(QueryValidationError) as error:
        validate_google_sql(fragment)

    assert error.value.reason_code == reason_code


def test_validator_reports_invalid_google_sql() -> None:
    with pytest.raises(QueryValidationError) as error:
        validate_google_sql("SELECT FROM")

    assert error.value.reason_code == "invalid_google_sql"
