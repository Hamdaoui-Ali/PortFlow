import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from tests.integration.test_gold import prepare_silver, run_dbt

from portflow.db.migrations import apply_migrations


@pytest.fixture
def database_url() -> str:
    return os.environ.get(
        "PORTFLOW_DATABASE_URL",
        "postgresql://portflow:portflow@localhost:5433/portflow",
    )


@pytest.fixture
def database_ready(database_url: str) -> Iterator[None]:
    migrations_dir = Path(__file__).parents[2] / "db" / "migrations"
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


@pytest.fixture
def gold_db(database_url: str, database_ready: None, tmp_path: Path) -> Path:
    silver_dir = prepare_silver(database_url, tmp_path)
    gold_db_path = tmp_path / "gold" / "portflow.duckdb"
    result = run_dbt(silver_dir, gold_db_path)
    assert result.returncode == 0, f"dbt failed:\n{result.stdout}\n{result.stderr}"
    return gold_db_path
