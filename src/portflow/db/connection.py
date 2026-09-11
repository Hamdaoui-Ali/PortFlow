"""PostgreSQL connection configuration."""

import os

import psycopg

DEFAULT_DATABASE_URL = "postgresql://portflow:portflow@localhost:5433/portflow"


def get_connection(
    database_url: str | None = None,
    *,
    connect_timeout: int | None = None,
) -> psycopg.Connection:
    """Open a PostgreSQL connection using an explicit URL or environment default."""
    resolved_url = database_url or os.environ.get("PORTFLOW_DATABASE_URL", DEFAULT_DATABASE_URL)
    if connect_timeout is None:
        return psycopg.connect(resolved_url)
    return psycopg.connect(resolved_url, connect_timeout=connect_timeout)
