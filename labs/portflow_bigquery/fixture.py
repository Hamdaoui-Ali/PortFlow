"""Deterministic, local multi-table fixture generation for PF-106."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from .schema import SchemaField, load_schema

_FIXTURE_START = datetime(2026, 1, 1, tzinfo=UTC)
_GENERATOR_VERSION = "1"
_EXTRACTION_RUN_ID = "portability-run-000042"


@dataclass(frozen=True)
class FixtureSpec:
    """Inputs for the fixed, reproducible portability fixture."""

    seed: int = 42


@dataclass(frozen=True)
class FixtureMetadata:
    """Fingerprint and shape of a generated deterministic fixture."""

    seed: int
    generator_version: str
    rows_by_table: dict[str, int]
    logical_sha256: str
    schema_sha256: str
    schema: dict[str, tuple[str, ...]]

    def as_json(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "generator_version": self.generator_version,
            "rows_by_table": self.rows_by_table,
            "logical_sha256": self.logical_sha256,
            "schema_sha256": self.schema_sha256,
            "schema": {table: list(columns) for table, columns in self.schema.items()},
        }


def _at(minutes: int) -> datetime:
    return _FIXTURE_START + timedelta(minutes=minutes)


def _metadata(table_name: str, timestamp: datetime) -> dict[str, object]:
    return {
        "created_at": timestamp,
        "updated_at": timestamp,
        "source_table": table_name,
        "extraction_run_id": _EXTRACTION_RUN_ID,
        "source_updated_at": timestamp,
        "extracted_at": timestamp,
    }


def _row(table_name: str, timestamp: datetime, **values: object) -> dict[str, object]:
    return {**values, **_metadata(table_name, timestamp)}


def _fixture_rows() -> dict[str, tuple[dict[str, object], ...]]:
    return {
        "telemetry_events": (
            _row(
                "telemetry_events",
                _at(0),
                event_id="evt-000042-000001",
                schema_version=1,
                equipment_id="QC-001",
                terminal_id="TM-001",
                event_timestamp=_at(0),
                ingestion_timestamp=_at(0),
                state="ACTIVE",
                available=True,
                load_percent=75.0,
                temperature_c=40.0,
            ),
            _row(
                "telemetry_events",
                _at(5),
                event_id="evt-000042-000002",
                schema_version=1,
                equipment_id="QC-001",
                terminal_id="TM-001",
                event_timestamp=_at(5),
                ingestion_timestamp=_at(5),
                state="IDLE",
                available=True,
                load_percent=0.0,
                temperature_c=35.0,
            ),
            _row(
                "telemetry_events",
                _at(10),
                event_id="evt-000042-000003",
                schema_version=1,
                equipment_id="QC-001",
                terminal_id="TM-001",
                event_timestamp=_at(10),
                ingestion_timestamp=_at(10),
                state="UNAVAILABLE",
                available=False,
                load_percent=0.0,
                temperature_c=30.0,
            ),
            _row(
                "telemetry_events",
                _at(15),
                event_id="evt-000042-000004",
                schema_version=1,
                equipment_id="QC-001",
                terminal_id="TM-001",
                event_timestamp=_at(15),
                ingestion_timestamp=_at(15),
                state="ACTIVE",
                available=True,
                load_percent=80.0,
                temperature_c=45.0,
            ),
        ),
        "container_movements": (
            _row(
                "container_movements",
                _at(0),
                movement_id="mov-000001",
                terminal_id="TM-001",
                equipment_id="QC-001",
                movement_type="GATE_IN",
                container_ref="CONT-000001",
                event_timestamp=_at(0),
            ),
            _row(
                "container_movements",
                _at(5),
                movement_id="mov-000002",
                terminal_id="TM-001",
                equipment_id="QC-001",
                movement_type="LOAD",
                container_ref="CONT-000001",
                event_timestamp=_at(5),
            ),
            _row(
                "container_movements",
                _at(20),
                movement_id="mov-000003",
                terminal_id="TM-001",
                equipment_id="QC-001",
                movement_type="DISCHARGE",
                container_ref="CONT-000001",
                event_timestamp=_at(20),
            ),
            _row(
                "container_movements",
                _at(30),
                movement_id="mov-000004",
                terminal_id="TM-001",
                equipment_id="QC-001",
                movement_type="GATE_OUT",
                container_ref="CONT-000001",
                event_timestamp=_at(30),
            ),
            _row(
                "container_movements",
                _at(10),
                movement_id="mov-000005",
                terminal_id="TM-001",
                equipment_id="QC-001",
                movement_type="GATE_IN",
                container_ref="CONT-000002",
                event_timestamp=_at(10),
            ),
        ),
        "incidents": (
            _row(
                "incidents",
                _at(5),
                incident_id="inc-000001",
                equipment_id="QC-001",
                severity="CRITICAL",
                status="RESOLVED",
                opened_at=_at(5),
                resolved_at=_at(15),
                root_cause="HYDRAULIC",
            ),
            _row(
                "incidents",
                _at(10),
                incident_id="inc-000002",
                equipment_id="QC-001",
                severity="WARNING",
                status="OPEN",
                opened_at=_at(10),
                resolved_at=None,
                root_cause="SENSOR",
            ),
        ),
        "alarms": (
            _row(
                "alarms",
                _at(10),
                alarm_id="alm-000001",
                equipment_id="QC-001",
                severity="CRITICAL",
                code="HYDRAULIC_PRESSURE",
                opened_at=_at(10),
                cleared_at=None,
            ),
            _row(
                "alarms",
                _at(20),
                alarm_id="alm-000002",
                equipment_id="QC-001",
                severity="WARNING",
                code="TEMPERATURE",
                opened_at=_at(20),
                cleared_at=None,
            ),
        ),
    }


def _table_columns(fields: tuple[SchemaField, ...]) -> list[str]:
    return [field.name for field in fields]


def logical_fixture_hash(
    output_root: Path, schema: dict[str, tuple[SchemaField, ...]]
) -> str:
    """Hash sorted logical table rows independently from their Parquet layout."""
    digest = hashlib.sha256()
    for table_name in sorted(schema):
        table_root = output_root / table_name
        parquet_paths = sorted(table_root.glob("*.parquet"))
        if not parquet_paths:
            raise ValueError("fixture must contain one Parquet file per logical table")
        columns = _table_columns(schema[table_name])
        frame = (
            pl.concat([pl.read_parquet(path) for path in parquet_paths])
            .select(columns)
            .sort(columns)
        )
        for values in frame.iter_rows():
            row = dict(zip(columns, values, strict=True))
            payload = json.dumps(
                {"table": table_name, "row": row},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            digest.update(payload.encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def generate_fixture(
    spec: FixtureSpec, output_root: Path, *, schema_path: Path
) -> FixtureMetadata:
    """Write one deterministic Parquet part per mapped Silver logical table."""
    schema = load_schema(schema_path)
    fixture_rows = _fixture_rows()
    rows_by_table: dict[str, int] = {}
    schema_columns: dict[str, tuple[str, ...]] = {}

    for table_name in sorted(schema):
        table_root = output_root / table_name
        table_root.mkdir(parents=True, exist_ok=True)
        for parquet_path in table_root.glob("*.parquet"):
            parquet_path.unlink()
        columns = _table_columns(schema[table_name])
        frame = pl.DataFrame(fixture_rows[table_name]).select(columns)
        frame.write_parquet(table_root / "part-000000.parquet")
        rows_by_table[table_name] = frame.height
        schema_columns[table_name] = tuple(columns)

    return FixtureMetadata(
        seed=spec.seed,
        generator_version=_GENERATOR_VERSION,
        rows_by_table=rows_by_table,
        logical_sha256=logical_fixture_hash(output_root, schema),
        schema_sha256=hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        schema=schema_columns,
    )
