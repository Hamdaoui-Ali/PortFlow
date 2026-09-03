"""Validate Bronze partitions, retain accepted rows, and quarantine rejects."""

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS, TableSpec
from portflow.quality.rules import (
    VALID_REASON_CODES,
    ReferenceSet,
    ValidationIssue,
    validate_row,
)

_METADATA_COLUMNS = ("source_table", "extraction_run_id", "source_updated_at", "extracted_at")
_MIN_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SilverRunReport:
    """Reconciliation and quarantine counts for a Silver transform run."""

    bronze_rows: int
    silver_rows: int
    quarantine_rows: int
    quarantine_reason_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class _InputRow:
    table_name: str
    row: dict[str, object]
    path: Path
    ordinal: int
    issues: tuple[ValidationIssue, ...]
    primary_key: str | None


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo is not None else value
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _normalize_row(row: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, datetime) and value.tzinfo is not None:
            normalized[key] = value.astimezone(UTC)
        else:
            normalized[key] = value
    return normalized


def _metadata_issues(table_name: str, row: dict[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    source_table = row.get("source_table")
    if not isinstance(source_table, str) or source_table != table_name:
        issues.append(
            ValidationIssue(
                "SCHEMA_INVALID",
                f"source_table must equal {table_name!r}",
            )
        )
    run_id = row.get("extraction_run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        issues.append(ValidationIssue("SCHEMA_INVALID", "extraction_run_id must be non-empty"))
    for column in ("source_updated_at", "extracted_at"):
        value = row.get(column)
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            issues.append(ValidationIssue("SCHEMA_INVALID", f"{column} must be a UTC datetime"))
    return issues


def _read_input_rows(bronze_dir: Path) -> list[tuple[str, dict[str, object], Path, int]]:
    inputs: list[tuple[str, dict[str, object], Path, int]] = []
    if not bronze_dir.exists():
        return inputs
    for path in sorted(bronze_dir.rglob("*.parquet")):
        relative_parts = path.relative_to(bronze_dir).parts
        if ".staging" in relative_parts:
            continue
        table_name = relative_parts[0] if relative_parts else ""
        frame = pl.read_parquet(path)
        for ordinal, raw_row in enumerate(frame.to_dicts()):
            inputs.append((table_name, dict(raw_row), path, ordinal))
    return inputs


def _references(rows: Iterable[tuple[str, dict[str, object], Path, int]]) -> ReferenceSet:
    terminal_ids: set[str] = set()
    equipment_ids: set[str] = set()
    for table_name, row, _, _ in rows:
        if table_name == "terminals" and isinstance(row.get("terminal_id"), str):
            terminal_ids.add(str(row["terminal_id"]))
        if table_name == "equipment" and isinstance(row.get("equipment_id"), str):
            equipment_ids.add(str(row["equipment_id"]))
    return ReferenceSet(frozenset(terminal_ids), frozenset(equipment_ids))


def _winner_key(item: _InputRow) -> tuple[datetime, str, str, int]:
    updated_at = item.row.get("source_updated_at")
    if not isinstance(updated_at, datetime):
        updated_at = _MIN_TIMESTAMP
    run_id = item.row.get("extraction_run_id")
    if not isinstance(run_id, str):
        run_id = ""
    return updated_at, run_id, item.path.as_posix(), item.ordinal


def _ordered_unique_issues(issues: Iterable[ValidationIssue]) -> list[ValidationIssue]:
    by_code: dict[str, ValidationIssue] = {}
    for issue in issues:
        by_code.setdefault(issue.code, issue)
    return [by_code[code] for code in VALID_REASON_CODES if code in by_code]


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path, compression="zstd")


def _quarantine_row(item: _InputRow, issues: Sequence[ValidationIssue]) -> dict[str, object]:
    spec = TABLE_SPECS.get(item.table_name)
    key = item.row.get(spec.primary_key) if spec is not None else None
    return {
        "raw_payload": json.dumps(_jsonable(item.row), sort_keys=True, separators=(",", ":")),
        "source_table": item.table_name,
        "primary_key": key if isinstance(key, str) else "",
        "reason_codes": [issue.code for issue in issues],
        "reason_details": [issue.detail for issue in issues],
    }


def transform_bronze_to_silver(
    *,
    bronze_dir: Path,
    silver_dir: Path,
    quarantine_dir: Path,
) -> SilverRunReport:
    """Transform every Bronze row exactly once into Silver or quarantine."""
    raw_inputs = _read_input_rows(bronze_dir)
    references = _references(raw_inputs)
    candidates: list[_InputRow] = []
    for table_name, row, path, ordinal in raw_inputs:
        spec: TableSpec | None = TABLE_SPECS.get(table_name)
        if spec is None:
            invalid_issues = (
                ValidationIssue("SCHEMA_INVALID", f"unsupported table {table_name!r}"),
            )
            candidates.append(_InputRow(table_name, row, path, ordinal, invalid_issues, None))
            continue
        row_issues = _ordered_unique_issues(
            [*_metadata_issues(table_name, row), *validate_row(table_name, row, references)]
        )
        primary_key = row.get(spec.primary_key)
        candidates.append(
            _InputRow(
                table_name,
                row,
                path,
                ordinal,
                tuple(row_issues),
                primary_key if isinstance(primary_key, str) else None,
            )
        )

    grouped: dict[tuple[str, str], list[_InputRow]] = defaultdict(list)
    for item in candidates:
        if item.primary_key is not None and item.table_name in TABLE_SPECS:
            grouped[(item.table_name, item.primary_key)].append(item)

    winners: set[tuple[Path, int]] = set()
    duplicate_keys: set[tuple[Path, int]] = set()
    for group in grouped.values():
        winner = max(group, key=_winner_key)
        winners.add((winner.path, winner.ordinal))
        for item in group:
            if item is not winner:
                duplicate_keys.add((item.path, item.ordinal))

    accepted_by_table: dict[str, list[dict[str, object]]] = defaultdict(list)
    quarantine_by_table: dict[str, list[dict[str, object]]] = defaultdict(list)
    reason_counts: dict[str, int] = {code: 0 for code in VALID_REASON_CODES}
    silver_rows = 0
    quarantine_rows = 0

    for item in candidates:
        item_key = (item.path, item.ordinal)
        if item_key in duplicate_keys:
            row_issues = [
                ValidationIssue("DUPLICATE_KEY", "row was superseded by a newer source row")
            ]
        elif item.issues:
            row_issues = list(item.issues)
        else:
            row_issues = []
        if row_issues:
            quarantine_by_table[item.table_name].append(_quarantine_row(item, row_issues))
            quarantine_rows += 1
            for issue in row_issues:
                reason_counts[issue.code] += 1
        elif item_key in winners or item.primary_key is None:
            accepted_by_table[item.table_name].append(_normalize_row(item.row))
            silver_rows += 1

    for table_name, rows in accepted_by_table.items():
        spec = TABLE_SPECS.get(table_name)
        if spec is not None:
            rows.sort(key=lambda row: str(row.get(spec.primary_key, "")))
        _write_rows(silver_dir / table_name / "part.parquet", rows)
    for table_name, rows in quarantine_by_table.items():
        rows.sort(key=lambda row: (str(row["primary_key"]), str(row["reason_codes"])))
        _write_rows(quarantine_dir / table_name / "part.parquet", rows)

    return SilverRunReport(
        bronze_rows=len(raw_inputs),
        silver_rows=silver_rows,
        quarantine_rows=quarantine_rows,
        quarantine_reason_counts={
            code: count for code, count in reason_counts.items() if count
        },
    )
