"""Canonical encoding and validation for PortFlow telemetry messages."""

import json
from collections.abc import Sequence

from pydantic import ValidationError

from portflow.domain.models import TelemetryEvent

type Header = tuple[str, bytes | None]

_EVENT_TYPE_HEADER = "portflow-event-type"
_SCHEMA_VERSION_HEADER = "portflow-schema-version"


class StreamValidationError(ValueError):
    """Raised when a stream record is not a valid PortFlow telemetry message."""


def telemetry_headers() -> tuple[tuple[str, bytes], ...]:
    return (
        (_EVENT_TYPE_HEADER, b"telemetry"),
        (_SCHEMA_VERSION_HEADER, b"1"),
    )


def encode_telemetry_event(event: TelemetryEvent) -> bytes:
    payload = json.dumps(
        event.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return payload.encode("utf-8")


def decode_telemetry_event(
    payload: bytes | None,
    headers: Sequence[Header] | None,
) -> TelemetryEvent:
    _validate_headers(headers)
    if payload is None:
        raise StreamValidationError("telemetry payload must not be None")

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise StreamValidationError("telemetry payload is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise StreamValidationError("telemetry payload is not valid JSON") from exc

    if not isinstance(decoded, dict):
        raise StreamValidationError("telemetry payload must be a JSON object")

    try:
        return TelemetryEvent.model_validate(decoded)
    except ValidationError as exc:
        raise StreamValidationError("telemetry payload is not a valid TelemetryEvent") from exc


def _validate_headers(headers: Sequence[Header] | None) -> None:
    expected = dict(telemetry_headers())
    if headers is None or len(headers) != len(expected):
        raise StreamValidationError("telemetry headers are missing or malformed")

    seen: set[str] = set()
    for name, value in headers:
        if name in seen or name not in expected or value != expected[name]:
            raise StreamValidationError("telemetry headers are missing or malformed")
        seen.add(name)

    if seen != expected.keys():
        raise StreamValidationError("telemetry headers are missing or malformed")
