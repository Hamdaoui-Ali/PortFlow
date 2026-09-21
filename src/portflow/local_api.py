"""Loopback-only HTTP API for the PortFlow local data workspace."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlsplit

import psycopg

from portflow.db.connection import DEFAULT_DATABASE_URL, get_connection
from portflow.db.migrations import apply_migrations
from portflow.local_data import (
    ImportValidationError,
    get_local_schema,
    import_records,
)
from portflow.pipeline import PipelineError, run_local_pipeline
from portflow.seed import seed_operational

LOGGER = logging.getLogger(__name__)
DEFAULT_ALLOWED_ORIGINS = frozenset({
    "http://localhost:5173",
    "http://127.0.0.1:5173",
})


@dataclass(frozen=True, slots=True)
class LocalApiConfig:
    """Runtime configuration for the loopback API."""

    database_url: str
    output_dir: Path
    port: int = 8000
    max_body_bytes: int = 2_000_000
    database_connect_timeout_seconds: int = 3
    allowed_origins: frozenset[str] = DEFAULT_ALLOWED_ORIGINS


class LocalDataService(Protocol):
    """Operations exposed by the HTTP boundary."""

    def status(self) -> dict[str, object]:
        raise NotImplementedError

    def schema(self) -> dict[str, object]:
        raise NotImplementedError

    def seed(self) -> dict[str, object]:
        raise NotImplementedError

    def import_payload(self, payload: Mapping[str, object]) -> dict[str, object]:
        raise NotImplementedError

    def refresh(self) -> dict[str, object]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class LocalApiResponse:
    """Small response object shared by dispatch tests and the HTTP handler."""

    status: int
    body: Mapping[str, object]


class InvalidRequestError(ValueError):
    """Raised when an API payload does not match its endpoint contract."""


class InvalidJsonError(InvalidRequestError):
    """Raised when a request body cannot be decoded as a JSON object."""


class RefreshBusyError(RuntimeError):
    """Raised when a second snapshot refresh starts before the first ends."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema_payload() -> dict[str, object]:
    return {
        "tables": [
            {
                "table_name": table.table_name,
                "primary_key": table.primary_key,
                "columns": [asdict(column) for column in table.columns],
            }
            for table in get_local_schema()
        ]
    }


class PostgresLocalDataService:
    """Concrete local service backed by PostgreSQL and the existing pipeline."""

    def __init__(self, config: LocalApiConfig) -> None:
        self._config = config
        self._refresh_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._pipeline_state = "idle"
        self._pipeline_message: str | None = None

    def _pipeline_status(self) -> tuple[str, str | None]:
        with self._state_lock:
            return self._pipeline_state, self._pipeline_message

    def status(self) -> dict[str, object]:
        pipeline_state, pipeline_message = self._pipeline_status()
        try:
            with get_connection(
                self._config.database_url,
                connect_timeout=self._config.database_connect_timeout_seconds,
            ) as connection:
                row = connection.execute(
                    "select to_regclass('public.terminals')"
                ).fetchone()
            schema_ready = bool(row and row[0])
            response: dict[str, object] = {
                "api": "ready",
                "database": "connected",
                "schema": "ready" if schema_ready else "missing",
                "pipeline": pipeline_state,
            }
            if pipeline_message:
                response["message"] = pipeline_message
            return response
        except psycopg.Error:
            response = {
                "api": "ready",
                "database": "unavailable",
                "schema": "missing",
                "pipeline": pipeline_state,
                "message": "Local database unavailable",
            }
            return response

    def schema(self) -> dict[str, object]:
        return _schema_payload()

    def seed(self) -> dict[str, object]:
        repository_root = _repository_root()
        with get_connection(
            self._config.database_url,
            connect_timeout=self._config.database_connect_timeout_seconds,
        ) as connection:
            apply_migrations(connection, repository_root / "db" / "migrations")
            report = seed_operational(connection, seed=42)
        return {
            "seed": report.seed,
            "row_counts": report.row_counts,
            "digest_sha256": report.digest_sha256,
        }

    def import_payload(self, payload: Mapping[str, object]) -> dict[str, object]:
        if set(payload) != {"table", "records"}:
            raise InvalidRequestError("payload must contain only table and records")
        table_name = payload.get("table")
        records_value = payload.get("records")
        if not isinstance(table_name, str) or not isinstance(records_value, list):
            raise InvalidRequestError("table must be a string and records must be an array")
        if not all(isinstance(record, Mapping) for record in records_value):
            raise InvalidRequestError("every record must be an object")

        records = cast(list[Mapping[str, object]], records_value)
        repository_root = _repository_root()
        with get_connection(
            self._config.database_url,
            connect_timeout=self._config.database_connect_timeout_seconds,
        ) as connection:
            apply_migrations(connection, repository_root / "db" / "migrations")
            report = import_records(
                connection,
                table_name=table_name,
                records=records,
            )
        return asdict(report)

    def refresh(self) -> dict[str, object]:
        if not self._refresh_lock.acquire(blocking=False):
            raise RefreshBusyError("snapshot refresh is already running")
        with self._state_lock:
            self._pipeline_state = "running"
            self._pipeline_message = None
        try:
            manifest_path = run_local_pipeline(
                database_url=self._config.database_url,
                output_dir=self._config.output_dir,
                connect_timeout=self._config.database_connect_timeout_seconds,
            )
            with self._state_lock:
                self._pipeline_state = "idle"
                self._pipeline_message = None
            return {"manifest_path": manifest_path.as_posix()}
        except Exception:
            with self._state_lock:
                self._pipeline_state = "failed"
                self._pipeline_message = "Snapshot refresh failed"
            raise
        finally:
            self._refresh_lock.release()


def _parse_json_object(body: bytes) -> Mapping[str, object]:
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidJsonError("request body must be valid UTF-8 JSON") from error
    if not isinstance(decoded, dict):
        raise InvalidRequestError("request body must be a JSON object")
    return cast(Mapping[str, object], decoded)


def _validation_body(error: ImportValidationError) -> dict[str, object]:
    return {
        "error": "validation",
        "issues": [asdict(issue) for issue in error.issues],
    }


def _error_response(error: Exception) -> LocalApiResponse:
    if isinstance(error, InvalidJsonError):
        return LocalApiResponse(400, {"error": "invalid_json", "message": str(error)})
    if isinstance(error, InvalidRequestError):
        return LocalApiResponse(
            400,
            {"error": "invalid_request", "message": str(error)},
        )
    if isinstance(error, ImportValidationError):
        return LocalApiResponse(400, _validation_body(error))
    if isinstance(error, RefreshBusyError):
        return LocalApiResponse(
            409,
            {"error": "refresh_in_progress", "message": "Snapshot refresh is already running"},
        )
    if isinstance(error, psycopg.OperationalError):
        return LocalApiResponse(
            503,
            {"error": "database_unavailable", "message": "Local database unavailable"},
        )
    if isinstance(error, psycopg.Error):
        LOGGER.exception("Local database operation failed", exc_info=error)
        return LocalApiResponse(
            503,
            {"error": "database_error", "message": "Local database operation failed"},
        )
    if isinstance(error, PipelineError):
        LOGGER.exception("Local snapshot refresh failed", exc_info=error)
        return LocalApiResponse(
            500,
            {"error": "pipeline_failed", "message": "Snapshot refresh failed"},
        )
    LOGGER.exception("Unhandled local API failure", exc_info=error)
    return LocalApiResponse(
        500,
        {"error": "server_error", "message": "Local API request failed"},
    )


def dispatch_request(
    service: LocalDataService,
    *,
    method: str,
    path: str,
    body: bytes = b"",
    origin: str | None = None,
    max_body_bytes: int = 2_000_000,
    allowed_origins: frozenset[str] = DEFAULT_ALLOWED_ORIGINS,
) -> LocalApiResponse:
    """Route one request without requiring a live socket, for tests and the handler."""
    if origin is not None and origin not in allowed_origins:
        return LocalApiResponse(403, {"error": "origin_not_allowed"})
    if len(body) > max_body_bytes:
        return LocalApiResponse(413, {"error": "request_too_large"})

    request_path = urlsplit(path).path
    get_routes = {"/api/status": service.status, "/api/schema": service.schema}
    post_routes = {
        "/api/seed": service.seed,
        "/api/refresh": service.refresh,
    }
    if request_path == "/api/import":
        if method != "POST":
            return LocalApiResponse(405, {"error": "method_not_allowed"})
        try:
            return LocalApiResponse(200, service.import_payload(_parse_json_object(body)))
        except Exception as error:
            return _error_response(error)

    if method == "GET" and request_path in get_routes:
        try:
            return LocalApiResponse(200, get_routes[request_path]())
        except Exception as error:
            return _error_response(error)

    if method == "POST" and request_path in post_routes:
        try:
            _parse_json_object(body)
            return LocalApiResponse(200, post_routes[request_path]())
        except Exception as error:
            return _error_response(error)

    if method == "OPTIONS" and request_path.startswith("/api/"):
        return LocalApiResponse(204, {})
    known_paths = {
        "/api/status",
        "/api/schema",
        "/api/seed",
        "/api/import",
        "/api/refresh",
    }
    if request_path in known_paths:
        return LocalApiResponse(405, {"error": "method_not_allowed"})
    return LocalApiResponse(404, {"error": "not_found"})


class _LocalHttpServer(ThreadingHTTPServer):
    service: LocalDataService
    config: LocalApiConfig


def _handler_for(
    service: LocalDataService,
    config: LocalApiConfig,
) -> type[BaseHTTPRequestHandler]:
    class LocalRequestHandler(BaseHTTPRequestHandler):
        def _respond(self, method: str) -> None:
            content_length_value = self.headers.get("Content-Length", "0")
            try:
                content_length = int(content_length_value)
            except ValueError:
                response = LocalApiResponse(400, {"error": "invalid_content_length"})
                self._write_response(response, None)
                return
            if content_length < 0 or content_length > config.max_body_bytes:
                response = LocalApiResponse(413, {"error": "request_too_large"})
                self._write_response(response, self.headers.get("Origin"))
                return
            body = self.rfile.read(content_length) if content_length else b""
            origin = self.headers.get("Origin")
            response = dispatch_request(
                service,
                method=method,
                path=self.path,
                body=body,
                origin=origin,
                max_body_bytes=config.max_body_bytes,
                allowed_origins=config.allowed_origins,
            )
            self._write_response(response, origin)

        def _write_response(self, response: LocalApiResponse, origin: str | None) -> None:
            response_body = json.dumps(response.body, separators=(",", ":")).encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            if origin is not None and origin in config.allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            if self.command == "OPTIONS":
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            if response.status != 204:
                self.wfile.write(response_body)

        def do_GET(self) -> None:
            self._respond("GET")

        def do_POST(self) -> None:
            self._respond("POST")

        def do_OPTIONS(self) -> None:
            self._respond("OPTIONS")

        def do_DELETE(self) -> None:
            self._respond("DELETE")

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

    return LocalRequestHandler


def create_server(
    config: LocalApiConfig,
    *,
    service: LocalDataService | None = None,
) -> ThreadingHTTPServer:
    """Create a server bound explicitly to the loopback interface."""
    effective_service = service or PostgresLocalDataService(config)
    handler = _handler_for(effective_service, config)
    server = _LocalHttpServer(("127.0.0.1", config.port), handler)
    server.service = effective_service
    server.config = config
    server.daemon_threads = True
    return server
