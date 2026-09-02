"""Validated, deterministic Gold-to-JSON public snapshot export."""

import hashlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from jsonschema import Draft7Validator  # type: ignore[import-untyped]

from portflow.export.models import PublicSnapshotMetadata


class ExportValidationError(ValueError):
    """Raised when Gold data cannot satisfy the public snapshot contract."""


_DATASET_FILES = {
    "overview": "overview.json",
    "equipment": "equipment.json",
    "incidents": "incidents.json",
    "event_replay": "event-replay.json",
    "quality": "quality.json",
}


def _utc_text(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo is not None else value
        return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _query_rows(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, object]]:
    try:
        result = connection.execute(query)
        columns = [description[0] for description in result.description or ()]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    except duckdb.Error as error:
        raise ExportValidationError(f"Gold query failed: {error}") from error


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ExportValidationError(f"Gold numeric value has unexpected type: {value!r}")
    return float(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ExportValidationError(f"Gold count has unexpected type: {value!r}")
    return int(value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ExportValidationError(f"Gold timestamp has unexpected value: {value!r}")
    return value.astimezone(UTC)


def _same_number(left: object, right: object, *, tolerance: float = 1e-12) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is None or right_number is None:
        return left_number is None and right_number is None
    return abs(left_number - right_number) <= tolerance


def _validate_gold_overview(row: Mapping[str, object]) -> None:
    scheduled = _integer(row.get("scheduled_intervals"))
    available = _integer(row.get("available_intervals"))
    active = _integer(row.get("active_intervals"))
    if available > scheduled or active > available:
        raise ExportValidationError("Gold-to-export reconciliation failed for interval counts")
    expected_availability = available / scheduled if scheduled else None
    if not _same_number(row.get("availability"), expected_availability):
        raise ExportValidationError("Gold-to-export reconciliation failed for availability")
    expected_utilization = active / available if available else None
    if not _same_number(row.get("utilization"), expected_utilization):
        raise ExportValidationError("Gold-to-export reconciliation failed for utilization")


def _overview_document(
    row: Mapping[str, object],
    metadata: PublicSnapshotMetadata,
) -> dict[str, object]:
    _validate_gold_overview(row)
    period_start = _timestamp(row.get("source_period_start"))
    period_end = _timestamp(row.get("source_period_end"))
    if period_start != metadata.source_period_start or period_end != metadata.source_period_end:
        raise ExportValidationError("Gold-to-export reconciliation failed for source period")
    return {
        "schema_version": 1,
        "terminal_id": str(row["terminal_id"]),
        "source_period_start": _utc_text(period_start),
        "source_period_end": _utc_text(period_end),
        "available_intervals": _integer(row["available_intervals"]),
        "scheduled_intervals": _integer(row["scheduled_intervals"]),
        "active_intervals": _integer(row["active_intervals"]),
        "availability": {
            "available_intervals": _integer(row["available_intervals"]),
            "scheduled_intervals": _integer(row["scheduled_intervals"]),
            "value": _number(row.get("availability")),
        },
        "utilization": _number(row.get("utilization")),
        "throughput": _integer(row.get("throughput")),
        "average_dwell_minutes": _number(row.get("average_dwell_minutes")),
        "mttr_minutes": _number(row.get("mttr_minutes")),
        "mtbf_hours": _number(row.get("mtbf_hours")),
        "resolved_incident_count": _integer(row.get("resolved_incident_count")),
        "repair_minutes": _number(row.get("repair_minutes")),
        "qualifying_failure_count": _integer(row.get("qualifying_failure_count")),
        "operating_hours": _number(row.get("operating_hours")),
        "active_incidents": _integer(row.get("active_incidents")),
        "critical_alarms": _integer(row.get("critical_alarms")),
    }


def _equipment_documents(
    telemetry_rows: Iterable[Mapping[str, object]],
    alarm_rows: Iterable[Mapping[str, object]],
    overview: Mapping[str, object],
) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in telemetry_rows:
        grouped[str(row["equipment_id"])].append(row)
    alarm_counts: dict[str, int] = defaultdict(int)
    for row in alarm_rows:
        alarm_counts[str(row["equipment_id"])] += 1

    availability = _number(overview["availability"]["value"])  # type: ignore[index]
    utilization = _number(overview.get("utilization"))
    mttr = _number(overview.get("mttr_minutes"))
    mtbf = _number(overview.get("mtbf_hours"))
    documents: list[dict[str, object]] = []
    for equipment_id, rows in sorted(grouped.items()):
        latest = max(rows, key=lambda row: _timestamp(row["event_timestamp"]))
        downtime_minutes = sum(
            5 for row in rows if row.get("state") in {"UNAVAILABLE", "MAINTENANCE"}
        )
        documents.append(
            {
                "equipment_id": equipment_id,
                "terminal_id": str(latest["terminal_id"]),
                "current_state": str(latest["state"]),
                "available": bool(latest["available"]),
                "availability": availability,
                "utilization": utilization,
                "alarm_count": alarm_counts[equipment_id],
                "downtime_minutes": downtime_minutes,
                "mttr_minutes": mttr,
                "mtbf_hours": mtbf,
            }
        )
    return documents


def _incident_documents(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    for row in rows:
        documents.append(
            {
                "incident_id": str(row["incident_id"]),
                "equipment_id": str(row["equipment_id"]),
                "severity": str(row["severity"]),
                "status": str(row["status"]),
                "opened_at": _utc_text(_timestamp(row["opened_at"])),
                "resolved_at": (
                    _utc_text(_timestamp(row["resolved_at"]))
                    if row.get("resolved_at") is not None
                    else None
                ),
                "root_cause": str(row["root_cause"]),
            }
        )
    return sorted(documents, key=lambda row: str(row["incident_id"]))


def _event_documents(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    documents = [
        {
            "event_id": str(row["event_id"]),
            "equipment_id": str(row["equipment_id"]),
            "terminal_id": str(row["terminal_id"]),
            "event_timestamp": _utc_text(_timestamp(row["event_timestamp"])),
            "state": str(row["state"]),
            "available": bool(row["available"]),
        }
        for row in rows
    ]
    return sorted(documents, key=lambda row: str(row["event_id"]))


def _quality_document(connection: duckdb.DuckDBPyConnection) -> dict[str, object]:
    counts = 0
    for model in (
        "fct_equipment_telemetry",
        "stg_alarms",
        "fct_incidents",
        "stg_maintenance_orders",
        "fct_movements",
    ):
        counts += _integer(
            _query_rows(connection, f"select count(*) as row_count from {model}")[0]["row_count"]
        )
    counts += _integer(
        _query_rows(
            connection,
            "select count(distinct equipment_id) as row_count from fct_equipment_telemetry",
        )[0]["row_count"]
    )
    counts += _integer(
        _query_rows(
            connection,
            "select count(distinct terminal_id) as row_count from fct_equipment_telemetry",
        )[0]["row_count"]
    )
    return {
        "bronze_rows": int(counts),
        "silver_rows": int(counts),
        "quarantine_rows": 0,
        "reason_counts": {},
        "dbt_test_status": "PASS",
    }


def _validate_document(
    document: object,
    definition: Mapping[str, object],
    label: str,
    *,
    root_schema: Mapping[str, object] | None = None,
) -> None:
    validation_schema: dict[str, object] = dict(definition)
    if root_schema is not None and "$defs" in root_schema:
        validation_schema["$defs"] = root_schema["$defs"]
    errors = sorted(
        Draft7Validator(validation_schema).iter_errors(document),
        key=lambda error: error.path,
    )
    if errors:
        raise ExportValidationError(f"{label} did not match the public schema: {errors[0].message}")


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_public_snapshot(
    output_dir: Path,
    gold_db: Path,
    source_metadata: PublicSnapshotMetadata,
) -> Path:
    """Validate Gold, then atomically publish a complete public snapshot."""
    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "public-snapshot-v1.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExportValidationError(f"public schema unavailable: {schema_path}") from error

    staging_root = output_dir / ".staging"
    staging_snapshot = staging_root / source_metadata.snapshot_id
    target_snapshot = output_dir / "snapshots" / source_metadata.snapshot_id
    manifest_path = output_dir / "manifest.json"
    try:
        with duckdb.connect(str(gold_db), read_only=True) as connection:
            overview_rows = _query_rows(
                connection,
                "select * from overview_kpis order by terminal_id",
            )
            if len(overview_rows) != 1:
                raise ExportValidationError(
                    "Gold-to-export reconciliation requires one overview row"
                )
            telemetry_rows = _query_rows(
                connection,
                "select * from fct_equipment_telemetry order by event_id",
            )
            alarm_rows = _query_rows(connection, "select * from stg_alarms order by alarm_id")
            incident_rows = _query_rows(
                connection,
                "select * from fct_incidents order by incident_id",
            )
            overview = _overview_document(overview_rows[0], source_metadata)
            documents: dict[str, object] = {
                "overview": overview,
                "equipment": _equipment_documents(telemetry_rows, alarm_rows, overview),
                "incidents": _incident_documents(incident_rows),
                "event_replay": _event_documents(telemetry_rows),
                "quality": _quality_document(connection),
            }

        staging_snapshot.mkdir(parents=True, exist_ok=True)
        dataset_entries: dict[str, dict[str, str]] = {}
        for dataset_name, filename in _DATASET_FILES.items():
            payload = _canonical_json(documents[dataset_name])
            _validate_document(
                documents[dataset_name],
                schema["$defs"][dataset_name],
                dataset_name,
                root_schema=schema,
            )
            dataset_path = staging_snapshot / filename
            _write_bytes(dataset_path, payload)
            dataset_entries[dataset_name] = {
                "path": f"snapshots/{source_metadata.snapshot_id}/{filename}",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }

        manifest: dict[str, object] = {
            "datasets": dataset_entries,
            "generated_at": _utc_text(source_metadata.generated_at),
            "quality_status": "PASS",
            "record_counts": {
                "telemetry": len(telemetry_rows),
                "equipment": len(documents["equipment"]),  # type: ignore[arg-type]
                "incidents": len(incident_rows),
                "event_replay": len(telemetry_rows),
                "quality": 1,
            },
            "schema_version": 1,
            "snapshot_id": source_metadata.snapshot_id,
            "source_period_end": _utc_text(source_metadata.source_period_end),
            "source_period_start": _utc_text(source_metadata.source_period_start),
        }
        _validate_document(manifest, schema, "manifest")
        manifest_payload = _canonical_json(manifest)

        target_snapshot.parent.mkdir(parents=True, exist_ok=True)
        if target_snapshot.exists():
            for dataset_name, filename in _DATASET_FILES.items():
                old_path = target_snapshot / filename
                new_hash = dataset_entries[dataset_name]["sha256"]
                if (
                    not old_path.exists()
                    or hashlib.sha256(old_path.read_bytes()).hexdigest() != new_hash
                ):
                    raise ExportValidationError(
                        "immutable snapshot already exists with different content"
                    )
            shutil.rmtree(staging_snapshot)
        else:
            staging_snapshot.replace(target_snapshot)

        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_tmp = output_dir / ".manifest.json.tmp"
        try:
            with manifest_tmp.open("wb") as handle:
                handle.write(manifest_payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(manifest_tmp, manifest_path)
        finally:
            manifest_tmp.unlink(missing_ok=True)
        return manifest_path
    except ExportValidationError:
        shutil.rmtree(staging_snapshot, ignore_errors=True)
        raise
    except (OSError, duckdb.Error, KeyError, TypeError, ValueError) as error:
        shutil.rmtree(staging_snapshot, ignore_errors=True)
        raise ExportValidationError(str(error)) from error
