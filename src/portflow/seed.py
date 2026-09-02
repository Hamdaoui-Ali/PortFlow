"""Deterministic operational fixture for the local PortFlow pipeline."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from portflow.simulator.equipment import generate_telemetry

FIXTURE_START = datetime(2026, 9, 2, tzinfo=UTC)
TERMINAL_ID = "TM-001"
EQUIPMENT_ID = "QC-001"

_TABLE_PRIMARY_KEYS: tuple[tuple[str, str], ...] = (
    ("alarms", "alarm_id"),
    ("container_movements", "movement_id"),
    ("equipment", "equipment_id"),
    ("incidents", "incident_id"),
    ("maintenance_orders", "maintenance_order_id"),
    ("telemetry_events", "event_id"),
    ("terminals", "terminal_id"),
)


@dataclass(frozen=True, slots=True)
class SeedReport:
    """Counts and content digest produced by a deterministic seed run."""

    seed: int
    row_counts: dict[str, int]
    digest_sha256: str


def _canonical_value(value: object) -> object:
    """Convert PostgreSQL values to stable JSON-compatible representations."""
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo is not None else value
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _digest_source(connection: psycopg.Connection[Any]) -> tuple[dict[str, int], str]:
    """Return source row counts and a canonical digest in table/key order."""
    digest_input: list[bytes] = []
    row_counts: dict[str, int] = {}
    with connection.cursor(row_factory=dict_row) as cursor:
        for table_name, primary_key in _TABLE_PRIMARY_KEYS:
            statement = SQL("select * from {} order by {}").format(
                Identifier(table_name),
                Identifier(primary_key),
            )
            cursor.execute(statement)
            rows = cursor.fetchall()
            row_counts[table_name] = len(rows)
            for row in rows:
                canonical_row = {
                    key: _canonical_value(value) for key, value in row.items()
                }
                digest_input.append(
                    (
                        json.dumps(
                            {"table": table_name, "row": canonical_row},
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
    return row_counts, hashlib.sha256(b"".join(digest_input)).hexdigest()


def _upsert(
    connection: psycopg.Connection[Any],
    statement: str,
    rows: Sequence[tuple[object, ...]],
) -> None:
    """Execute a deterministic batch upsert."""
    with connection.cursor() as cursor:
        cursor.executemany(statement, rows)


def seed_operational(
    connection: psycopg.Connection[Any],
    *,
    seed: int,
) -> SeedReport:
    """Insert the connected operational fixture and return its stable digest."""
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    if not 0 <= seed <= 999_999:
        raise ValueError("seed must be between 0 and 999999")

    telemetry = generate_telemetry(
        seed=seed,
        equipment_id=EQUIPMENT_ID,
        terminal_id=TERMINAL_ID,
        count=288,
        start_at=FIXTURE_START,
    )
    source_created_at = FIXTURE_START

    try:
        with connection.transaction():
            _upsert(
                connection,
                """
                insert into terminals
                    (terminal_id, name, timezone_name, created_at, updated_at)
                values (%s, %s, %s, %s, %s)
                on conflict (terminal_id) do update set
                    name = excluded.name,
                    timezone_name = excluded.timezone_name,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    (
                        TERMINAL_ID,
                        "PortFlow Demo Terminal",
                        "UTC",
                        source_created_at,
                        source_created_at,
                    ),
                ),
            )
            _upsert(
                connection,
                """
                insert into equipment
                    (equipment_id, terminal_id, equipment_type, commissioning_date,
                     created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (equipment_id) do update set
                    terminal_id = excluded.terminal_id,
                    equipment_type = excluded.equipment_type,
                    commissioning_date = excluded.commissioning_date,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                ((
                    EQUIPMENT_ID,
                    TERMINAL_ID,
                    "QUAY_CRANE",
                    date(2024, 1, 1),
                    source_created_at,
                    source_created_at,
                ),),
            )
            _upsert(
                connection,
                """
                insert into telemetry_events
                    (event_id, schema_version, equipment_id, terminal_id,
                     event_timestamp, ingestion_timestamp, state, available,
                     load_percent, temperature_c, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (event_id) do update set
                    schema_version = excluded.schema_version,
                    equipment_id = excluded.equipment_id,
                    terminal_id = excluded.terminal_id,
                    event_timestamp = excluded.event_timestamp,
                    ingestion_timestamp = excluded.ingestion_timestamp,
                    state = excluded.state,
                    available = excluded.available,
                    load_percent = excluded.load_percent,
                    temperature_c = excluded.temperature_c,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                tuple(
                    (
                        event.event_id,
                        event.schema_version,
                        event.equipment_id,
                        event.terminal_id,
                        event.event_timestamp,
                        event.ingestion_timestamp,
                        event.state.value,
                        event.available,
                        event.load_percent,
                        event.temperature_c,
                        event.ingestion_timestamp,
                        event.ingestion_timestamp,
                    )
                    for event in telemetry
                ),
            )

            alarm_rows = (
                (
                    "alm-000001",
                    EQUIPMENT_ID,
                    "WARNING",
                    "TEMP_HIGH",
                    FIXTURE_START + timedelta(hours=1),
                    FIXTURE_START + timedelta(hours=1, minutes=20),
                ),
                (
                    "alm-000002",
                    EQUIPMENT_ID,
                    "CRITICAL",
                    "HYDRAULIC_PRESSURE",
                    FIXTURE_START + timedelta(hours=12),
                    None,
                ),
                (
                    "alm-000003",
                    EQUIPMENT_ID,
                    "INFO",
                    "SENSOR_RESET",
                    FIXTURE_START + timedelta(hours=18),
                    FIXTURE_START + timedelta(hours=18, minutes=5),
                ),
            )
            _upsert(
                connection,
                """
                insert into alarms
                    (alarm_id, equipment_id, severity, code, opened_at, cleared_at,
                     created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (alarm_id) do update set
                    equipment_id = excluded.equipment_id,
                    severity = excluded.severity,
                    code = excluded.code,
                    opened_at = excluded.opened_at,
                    cleared_at = excluded.cleared_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                tuple(
                    row + (row[4], row[5] if row[5] is not None else row[4])
                    for row in alarm_rows
                ),
            )

            incident_rows = (
                (
                    "inc-000001",
                    EQUIPMENT_ID,
                    "MAJOR",
                    "RESOLVED",
                    FIXTURE_START + timedelta(hours=3),
                    FIXTURE_START + timedelta(hours=3, minutes=30),
                    "Hydraulic leak",
                ),
                (
                    "inc-000002",
                    EQUIPMENT_ID,
                    "CRITICAL",
                    "OPEN",
                    FIXTURE_START + timedelta(hours=20),
                    None,
                    "Motor overload",
                ),
            )
            _upsert(
                connection,
                """
                insert into incidents
                    (incident_id, equipment_id, severity, status, opened_at, resolved_at,
                     root_cause, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (incident_id) do update set
                    equipment_id = excluded.equipment_id,
                    severity = excluded.severity,
                    status = excluded.status,
                    opened_at = excluded.opened_at,
                    resolved_at = excluded.resolved_at,
                    root_cause = excluded.root_cause,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                tuple(
                    row + (row[4], row[5] if row[5] is not None else row[4])
                    for row in incident_rows
                ),
            )

            maintenance_rows = (
                (
                    "mnt-000001",
                    EQUIPMENT_ID,
                    "COMPLETED",
                    FIXTURE_START + timedelta(hours=4),
                    FIXTURE_START + timedelta(hours=5),
                ),
                (
                    "mnt-000002",
                    EQUIPMENT_ID,
                    "IN_PROGRESS",
                    FIXTURE_START + timedelta(hours=21),
                    None,
                ),
            )
            _upsert(
                connection,
                """
                insert into maintenance_orders
                    (maintenance_order_id, equipment_id, status, started_at, completed_at,
                     created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (maintenance_order_id) do update set
                    equipment_id = excluded.equipment_id,
                    status = excluded.status,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                tuple(
                    row + (row[3], row[4] if row[4] is not None else row[3])
                    for row in maintenance_rows
                ),
            )

            movement_rows = (
                ("mov-000001", "GATE_IN", "CONT-0001", timedelta(hours=1)),
                ("mov-000002", "GATE_OUT", "CONT-0001", timedelta(hours=1, minutes=30)),
                ("mov-000003", "GATE_IN", "CONT-0002", timedelta(hours=6)),
                ("mov-000004", "GATE_OUT", "CONT-0002", timedelta(hours=7)),
                ("mov-000005", "GATE_IN", "CONT-0003", timedelta(hours=10)),
                ("mov-000006", "GATE_OUT", "CONT-0003", timedelta(hours=11, minutes=15)),
                ("mov-000007", "LOAD", "CONT-0004", timedelta(hours=15)),
                ("mov-000008", "DISCHARGE", "CONT-0004", timedelta(hours=16, minutes=30)),
            )
            _upsert(
                connection,
                """
                insert into container_movements
                    (movement_id, terminal_id, equipment_id, movement_type, container_ref,
                     event_timestamp, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (movement_id) do update set
                    terminal_id = excluded.terminal_id,
                    equipment_id = excluded.equipment_id,
                    movement_type = excluded.movement_type,
                    container_ref = excluded.container_ref,
                    event_timestamp = excluded.event_timestamp,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                tuple(
                    (
                        movement_id,
                        TERMINAL_ID,
                        EQUIPMENT_ID,
                        movement_type,
                        container_ref,
                        FIXTURE_START + offset,
                        FIXTURE_START + offset,
                        FIXTURE_START + offset,
                    )
                    for movement_id, movement_type, container_ref, offset in movement_rows
                ),
            )
            row_counts, digest_sha256 = _digest_source(connection)
    except Exception:
        connection.rollback()
        raise

    return SeedReport(seed=seed, row_counts=row_counts, digest_sha256=digest_sha256)
