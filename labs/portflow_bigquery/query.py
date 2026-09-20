"""Rendering and offline validation for the committed GoogleSQL contract."""

import hashlib
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_DATASET = re.compile(r"^[A-Za-z0-9_]+$")
_TOKENS = ("{{ project_id }}", "{{ dataset }}")
_FORBIDDEN_DUCKDB = re.compile(r"\b(?:read_parquet|date_diff|filter)\s*\(", re.IGNORECASE)
_SELECT_STAR = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?\*", re.IGNORECASE)
_OUTPUT_FIELDS = (
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


class QueryValidationError(ValueError):
    """Raised when a query does not meet the offline portability contract."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def render_query(template: str, *, project_id: str, dataset: str) -> str:
    """Render validated project and dataset identifiers into the SQL template."""
    if not _PROJECT_ID.fullmatch(project_id):
        raise QueryValidationError("invalid_project_id")
    if not _DATASET.fullmatch(dataset):
        raise QueryValidationError("invalid_dataset")
    return template.replace(_TOKENS[0], project_id).replace(_TOKENS[1], dataset)


def _validate_output_fields(statement: exp.Expr) -> None:
    select = statement if isinstance(statement, exp.Select) else statement.find(exp.Select)
    if select is None:
        raise QueryValidationError("missing_output_field")
    for projection in select.expressions:
        expression = projection.this if isinstance(projection, exp.Alias) else projection
        if isinstance(expression, exp.Star) or (
            isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star)
        ):
            raise QueryValidationError("implicit_select_star")
    output_fields = tuple(expression.alias_or_name for expression in select.expressions)
    if output_fields != _OUTPUT_FIELDS:
        raise QueryValidationError("missing_output_field")


def validate_google_sql(sql: str) -> None:
    """Reject nonportable SQL and parse the rendered query as BigQuery GoogleSQL."""
    if "{{" in sql or "}}" in sql:
        raise QueryValidationError("unrendered_template")
    if _FORBIDDEN_DUCKDB.search(sql):
        raise QueryValidationError("forbidden_duckdb_construct")
    if _SELECT_STAR.search(sql):
        raise QueryValidationError("implicit_select_star")
    try:
        statement = sqlglot.parse_one(sql, read="bigquery")
    except ParseError as error:
        raise QueryValidationError("invalid_google_sql") from error
    _validate_output_fields(statement)


def query_sha256(sql: str) -> str:
    """Return the SHA-256 digest of the UTF-8 query text."""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()
