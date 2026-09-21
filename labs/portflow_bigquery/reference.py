"""Safe local dbt/DuckDB runner for the BigQuery portability reference."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .canonical import RESULT_FIELDS, canonicalize_rows, result_sha256


class ReferenceExecutionError(ValueError):
    """Raised when the local reference cannot produce a trustworthy result."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class ReferenceResult:
    """Canonical local Gold output and its deterministic result hash."""

    rows: tuple[dict[str, object], ...]
    result_sha256: str


def run_local_reference(
    *, repository_root: Path, fixture_root: Path, gold_db: Path
) -> ReferenceResult:
    """Build local Gold from a fixture and return its canonical KPI reference."""
    if not fixture_root.is_dir():
        raise ReferenceExecutionError("fixture_missing")

    try:
        result = subprocess.run(
            [
                "dbt",
                "build",
                "--project-dir",
                str(repository_root / "analytics"),
                "--profiles-dir",
                str(repository_root / "analytics"),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=repository_root,
            env={
                **os.environ,
                "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
                "PORTFLOW_SILVER_DIR": fixture_root.as_posix(),
                "PORTFLOW_GOLD_DB": gold_db.as_posix(),
            },
        )
    except OSError:
        raise ReferenceExecutionError("dbt_reference_failed") from None
    if result.returncode != 0:
        raise ReferenceExecutionError("dbt_reference_failed")
    if not gold_db.is_file():
        raise ReferenceExecutionError("gold_output_missing")

    projection = ", ".join(RESULT_FIELDS)
    with duckdb.connect(str(gold_db), read_only=True) as connection:
        records = connection.execute(
            f"SELECT {projection} FROM overview_kpis ORDER BY terminal_id"
        ).fetchall()
    rows = [dict(zip(RESULT_FIELDS, record, strict=True)) for record in records]
    canonical_rows = canonicalize_rows(rows)
    return ReferenceResult(
        rows=tuple(canonical_rows),
        result_sha256=result_sha256(rows),
    )
