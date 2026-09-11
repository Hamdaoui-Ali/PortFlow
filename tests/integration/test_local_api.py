"""Real loopback API checks against the disposable PostgreSQL service."""

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import psycopg

from portflow.local_api import LocalApiConfig, PostgresLocalDataService, create_server


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: object | None = None,
) -> dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def test_loopback_api_reports_schema_and_imports_terminal(
    database_url: str,
    tmp_path: Path,
) -> None:
    config = LocalApiConfig(
        database_url=database_url,
        output_dir=tmp_path / "public-data",
        port=0,
    )
    server = create_server(config, service=PostgresLocalDataService(config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        status = request_json(base_url, "/api/status")
        assert status["database"] == "connected"
        assert "database_url" not in status

        schema = request_json(base_url, "/api/schema")
        assert len(schema["tables"]) == 7

        result = request_json(
            base_url,
            "/api/import",
            method="POST",
            payload={
                "table": "terminals",
                "records": [{
                    "terminal_id": "TM-101",
                    "name": "Loopback Terminal",
                    "timezone_name": "UTC",
                    "created_at": "2026-09-02T00:00:00Z",
                    "updated_at": "2026-09-02T00:00:00Z",
                }],
            },
        )
        assert result["inserted_count"] == 1

        with psycopg.connect(database_url) as connection:
            terminal = connection.execute(
                "select name from terminals where terminal_id = %s",
                ("TM-101",),
            ).fetchone()
        assert terminal == ("Loopback Terminal",)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_loopback_api_rejects_hosted_origin(
    database_url: str,
    tmp_path: Path,
) -> None:
    config = LocalApiConfig(
        database_url=database_url,
        output_dir=tmp_path / "public-data",
        port=0,
    )
    server = create_server(config, service=PostgresLocalDataService(config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        request = Request(
            f"{base_url}/api/status",
            headers={"Origin": "https://portflow.example"},
        )
        try:
            urlopen(request, timeout=10)
        except Exception as error:
            assert getattr(error, "code", None) == 403
        else:
            raise AssertionError("hosted origin was unexpectedly accepted")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
