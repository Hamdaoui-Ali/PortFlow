import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from portflow.db.migrations import apply_migrations


@pytest.fixture
def database_url() -> str:
    return os.environ.get(
        "PORTFLOW_DATABASE_URL",
        "postgresql://portflow:portflow@localhost:5433/portflow",
    )


@pytest.fixture
def migrations_dir() -> Path:
    return Path(__file__).parents[2] / "db" / "migrations"


@pytest.fixture(autouse=True)
def clean_database(database_url: str, migrations_dir: Path) -> Iterator[None]:
    try:
        with psycopg.connect(database_url) as connection:
            apply_migrations(connection, migrations_dir)
            yield
            connection.execute(
                """
                truncate table
                    telemetry_events,
                    alarms,
                    incidents,
                    maintenance_orders,
                    container_movements,
                    equipment,
                    terminals
                restart identity cascade
                """
            )
    except psycopg.OperationalError:
        pytest.fail(
            "PostgreSQL is unavailable. Start it with "
            "docker compose up -d --wait postgres"
        )
