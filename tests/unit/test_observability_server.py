from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from portflow.observability import server

_RUNS_SCHEMA = """
CREATE TABLE stream_runs (
    run_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    bronze_dir TEXT NOT NULL,
    batch_size INTEGER NOT NULL,
    max_messages INTEGER NOT NULL,
    allowed_lateness_seconds INTEGER NOT NULL,
    poll_timeout_seconds REAL NOT NULL,
    idle_timeout_seconds REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    consumed_count INTEGER,
    bronze_row_count INTEGER,
    committed_count INTEGER,
    batch_count INTEGER,
    duplicate_count INTEGER,
    late_count INTEGER,
    dead_letter_count INTEGER,
    error_type TEXT,
    error_message TEXT
)
"""


def create_state_db_with_one_success(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_RUNS_SCHEMA)
    connection.execute(
        """
        INSERT INTO stream_runs(
            run_id, topic, bronze_dir, batch_size, max_messages,
            allowed_lateness_seconds, poll_timeout_seconds, idle_timeout_seconds,
            status, started_at, finished_at, consumed_count, bronze_row_count,
            committed_count, batch_count, duplicate_count, late_count,
            dead_letter_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "server-fixture",
            "portflow.telemetry",
            "data/bronze-stream",
            2,
            12,
            300,
            1.0,
            30.0,
            "succeeded",
            "2026-09-19T11:00:00+00:00",
            "2026-09-19T11:00:10+00:00",
            1,
            1,
            1,
            1,
            0,
            0,
            0,
        ),
    )
    connection.commit()
    connection.close()
    return path


def start_test_server(
    state_path: Path,
) -> tuple[server.MetricsHTTPServer, threading.Thread]:
    metrics_server = server.create_metrics_server(
        state_path,
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(target=metrics_server.serve_forever, daemon=True)
    thread.start()
    return metrics_server, thread


def test_metrics_endpoint_returns_prometheus_text(tmp_path: Path) -> None:
    state_path = create_state_db_with_one_success(tmp_path / ".stream-state.sqlite3")
    metrics_server, thread = start_test_server(state_path)
    try:
        with urlopen(f"http://127.0.0.1:{metrics_server.server_port}/metrics") as response:
            status = response.status
            content_type = response.headers["Content-Type"]
            body = response.read().decode("utf-8")
    finally:
        metrics_server.shutdown()
        thread.join(timeout=2)
        metrics_server.server_close()

    assert status == 200
    assert content_type is not None
    assert content_type.startswith("text/plain")
    assert "portflow_stream_state_store_available 1" in body


def test_unknown_path_returns_not_found(tmp_path: Path) -> None:
    metrics_server, thread = start_test_server(tmp_path / ".stream-state.sqlite3")
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{metrics_server.server_port}/health")
    finally:
        metrics_server.shutdown()
        thread.join(timeout=2)
        metrics_server.server_close()

    assert error.value.code == 404


def test_main_reads_state_path_host_and_port_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFLOW_STREAM_STATE_PATH", "custom/state.sqlite3")
    monkeypatch.setenv("PORTFLOW_STREAM_METRICS_HOST", "127.0.0.1")
    monkeypatch.setenv("PORTFLOW_STREAM_METRICS_PORT", "9123")
    captured: dict[str, object] = {}

    def fake_serve(path: Path, *, host: str, port: int) -> None:
        captured.update(path=path, host=host, port=port)

    monkeypatch.setattr(server, "serve_metrics", fake_serve)

    server.main([])

    assert captured == {
        "path": Path("custom/state.sqlite3"),
        "host": "127.0.0.1",
        "port": 9123,
    }
