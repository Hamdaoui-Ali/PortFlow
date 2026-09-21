import pytest

from portflow.db.connection import get_database_url


def test_database_url_requires_explicit_configuration(monkeypatch) -> None:
    monkeypatch.delenv("PORTFLOW_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PORTFLOW_DATABASE_URL"):
        get_database_url()


def test_database_url_accepts_explicit_argument_or_environment(monkeypatch) -> None:
    explicit_url = "postgresql://test-database"
    monkeypatch.setenv("PORTFLOW_DATABASE_URL", "postgresql://environment-database")

    assert get_database_url(explicit_url) == explicit_url
    assert get_database_url() == "postgresql://environment-database"
