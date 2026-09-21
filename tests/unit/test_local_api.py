import json
from collections.abc import Mapping
from pathlib import Path

import psycopg

from portflow.local_api import (
    LocalApiConfig,
    PostgresLocalDataService,
    dispatch_request,
)


class FakeLocalDataService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def status(self) -> dict[str, object]:
        self.calls.append(("status", None))
        return {
            "api": "ready",
            "database": "connected",
            "schema": "ready",
            "pipeline": "idle",
        }

    def schema(self) -> dict[str, object]:
        self.calls.append(("schema", None))
        return {"tables": [{"table_name": "terminals"}]}

    def stream_runs(self) -> dict[str, object]:
        self.calls.append(("stream_runs", None))
        return {"status": "ready", "limit": 10, "runs": []}

    def seed(self) -> dict[str, object]:
        self.calls.append(("seed", None))
        return {"seed": 42, "row_counts": {"terminals": 1}}

    def import_payload(self, payload: Mapping[str, object]) -> dict[str, object]:
        self.calls.append(("import", payload))
        return {"table_name": payload["table"], "inserted_count": 1, "updated_count": 0}

    def refresh(self) -> dict[str, object]:
        self.calls.append(("refresh", None))
        return {"manifest_path": "data/manifest.json"}


def test_dispatches_status_and_schema() -> None:
    service = FakeLocalDataService()

    status = dispatch_request(service, method="GET", path="/api/status")
    schema = dispatch_request(service, method="GET", path="/api/schema")

    assert status.status == 200
    assert status.body["database"] == "connected"
    assert schema.status == 200
    assert schema.body["tables"] == [{"table_name": "terminals"}]
    assert service.calls == [("status", None), ("schema", None)]


def test_stream_runs_route_returns_read_model() -> None:
    service = FakeLocalDataService()

    response = dispatch_request(service, method="GET", path="/api/stream-runs")

    assert response.status == 200
    assert response.body == {
        "status": "ready",
        "limit": 10,
        "runs": [],
    }
    assert service.calls == [("stream_runs", None)]


def test_stream_runs_route_rejects_non_get_methods() -> None:
    response = dispatch_request(
        FakeLocalDataService(),
        method="POST",
        path="/api/stream-runs",
        body=b"{}",
    )

    assert response.status == 405
    assert response.body["error"] == "method_not_allowed"


class UnavailableStreamRunsService(FakeLocalDataService):
    def stream_runs(self) -> dict[str, object]:
        self.calls.append(("stream_runs", None))
        return {"status": "unavailable", "limit": 10, "runs": []}


def test_stream_runs_unavailable_response_is_bounded() -> None:
    response = dispatch_request(
        UnavailableStreamRunsService(),
        method="GET",
        path="/api/stream-runs",
    )

    assert response.status == 200
    assert set(response.body) == {"status", "limit", "runs"}
    assert response.body == {
        "status": "unavailable",
        "limit": 10,
        "runs": [],
    }


def test_dispatches_seed_import_and_refresh() -> None:
    service = FakeLocalDataService()
    payload = {
        "table": "terminals",
        "records": [{"terminal_id": "TM-101"}],
    }

    seed = dispatch_request(service, method="POST", path="/api/seed", body=b"{}")
    imported = dispatch_request(
        service,
        method="POST",
        path="/api/import",
        body=json.dumps(payload).encode("utf-8"),
    )
    refreshed = dispatch_request(service, method="POST", path="/api/refresh", body=b"{}")

    assert seed.status == 200
    assert imported.status == 200
    assert imported.body["table_name"] == "terminals"
    assert refreshed.status == 200
    assert service.calls[1] == ("import", payload)


def test_rejects_unknown_path_and_method() -> None:
    service = FakeLocalDataService()

    unknown = dispatch_request(service, method="GET", path="/api/not-supported")
    method = dispatch_request(service, method="DELETE", path="/api/status")

    assert unknown.status == 404
    assert method.status == 405


def test_rejects_malformed_json() -> None:
    response = dispatch_request(
        FakeLocalDataService(),
        method="POST",
        path="/api/import",
        body=b"{not-json",
    )

    assert response.status == 400
    assert response.body["error"] == "invalid_json"


def test_rejects_oversized_body() -> None:
    response = dispatch_request(
        FakeLocalDataService(),
        method="POST",
        path="/api/seed",
        body=b"12345",
        max_body_bytes=4,
    )

    assert response.status == 413
    assert response.body["error"] == "request_too_large"


def test_rejects_non_local_origin() -> None:
    response = dispatch_request(
        FakeLocalDataService(),
        method="GET",
        path="/api/status",
        origin="https://example.com",
    )

    assert response.status == 403
    assert response.body["error"] == "origin_not_allowed"


def test_postgres_status_uses_bounded_connection(monkeypatch) -> None:
    calls: list[tuple[str, int | None]] = []

    def fail_get_connection(
        database_url: str,
        *,
        connect_timeout: int | None = None,
    ) -> object:
        calls.append((database_url, connect_timeout))
        raise psycopg.OperationalError("offline")

    monkeypatch.setattr("portflow.local_api.get_connection", fail_get_connection)
    service = PostgresLocalDataService(
        LocalApiConfig(
            database_url="postgresql://offline",
            output_dir=Path("data"),
        )
    )

    response = service.status()

    assert response["database"] == "unavailable"
    assert calls == [("postgresql://offline", 3)]


def test_postgres_service_stream_runs_uses_configured_state_path(tmp_path: Path) -> None:
    service = PostgresLocalDataService(
        LocalApiConfig(
            database_url="postgresql://unused",
            output_dir=tmp_path / "public",
            stream_state_path=tmp_path / ".stream-state.sqlite3",
        )
    )

    response = service.stream_runs()

    assert response["status"] == "absent"
