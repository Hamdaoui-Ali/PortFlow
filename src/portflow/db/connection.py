"""PostgreSQL connection configuration."""

import os

import psycopg


def get_database_url(database_url: str | None = None) -> str:
    """Return an explicit database URL or fail before using an unsafe default."""
    resolved_url = database_url or os.environ.get("PORTFLOW_DATABASE_URL")
    if not resolved_url:
        raise RuntimeError("PORTFLOW_DATABASE_URL must be set before connecting to PostgreSQL")
    return resolved_url


def get_connection(
    database_url: str | None = None,
    *,
    connect_timeout: int | None = None,
) -> psycopg.Connection:
    """Open a PostgreSQL connection using an explicit or configured URL."""
    resolved_url = get_database_url(database_url)
    if connect_timeout is None:
        return psycopg.connect(resolved_url)
    return psycopg.connect(resolved_url, connect_timeout=connect_timeout)
