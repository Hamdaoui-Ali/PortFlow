"""HTTP entry point for local stream metrics."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from portflow.observability.metrics import collect_stream_metrics, render_prometheus

_DEFAULT_STATE_PATH = "data/bronze-stream/.stream-state.sqlite3"
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 9108


class MetricsHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server carrying the read-only state path."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], state_path: Path) -> None:
        self.state_path = state_path
        super().__init__(server_address, _MetricsRequestHandler)


class _MetricsRequestHandler(BaseHTTPRequestHandler):
    """Serve one scrape snapshot and reject all other paths."""

    server_version = "PortFlowMetrics/1.0"

    def do_GET(self) -> None:
        if self.path != "/metrics":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        metrics_server = cast(MetricsHTTPServer, self.server)
        snapshot = collect_stream_metrics(
            metrics_server.state_path,
            now=datetime.now(UTC),
        )
        body = render_prometheus(snapshot).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep periodic Prometheus scrapes out of the local terminal."""


def create_metrics_server(
    state_path: Path,
    *,
    host: str,
    port: int,
) -> MetricsHTTPServer:
    """Create a metrics server without starting its serving loop."""
    return MetricsHTTPServer((host, port), state_path)


def serve_metrics(
    state_path: Path,
    *,
    host: str,
    port: int,
) -> None:
    """Serve metrics until the process receives a shutdown signal."""
    with create_metrics_server(state_path, host=host, port=port) as metrics_server:
        metrics_server.serve_forever()


def main(argv: Sequence[str] | None = None) -> None:
    """Parse local configuration and start the metrics server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-path",
        type=Path,
        default=Path(os.environ.get("PORTFLOW_STREAM_STATE_PATH", _DEFAULT_STATE_PATH)),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("PORTFLOW_STREAM_METRICS_HOST", _DEFAULT_HOST),
    )
    parser.add_argument(
        "--port",
        type=_parse_port,
        default=os.environ.get("PORTFLOW_STREAM_METRICS_PORT", str(_DEFAULT_PORT)),
    )
    args = parser.parse_args(argv)
    serve_metrics(args.state_path, host=args.host, port=args.port)


def _parse_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


if __name__ == "__main__":
    main()
