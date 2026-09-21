"""Static validation for the PF-107 Databricks source notebook."""

import hashlib
import re
from pathlib import Path

_COMMAND_SEPARATOR = "# COMMAND ----------"
_QUALIFIED_TABLE = re.compile(
    r"(?:\{?catalog\}?\s*\.\s*\{?schema\}?\s*\.\s*\{?(?:prefix|table_prefix)\}?)",
    re.IGNORECASE,
)
_SAVE_AS_TABLE = re.compile(r"saveAsTable\s*\(([^)]*)\)", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_PATTERNS = (
    re.compile(r"\brdd\b|\.toRDD\b", re.IGNORECASE),
    re.compile(r"\bsparkcontext\b|\.sparkcontext\b", re.IGNORECASE),
    re.compile(r"\b(?:udf|pandas_udf)\s*\(", re.IGNORECASE),
    re.compile(r"\bdbfs\b", re.IGNORECASE),
    re.compile(r"\bdbutils\.fs\b", re.IGNORECASE),
    re.compile(r"\bmaven\b|--packages\b|spark\.jars\.packages", re.IGNORECASE),
    re.compile(
        r"https?://|\b(?:requests|urllib|httpx|socket)\b|\b(?:jdbc|url)\s*[:=]",
        re.IGNORECASE,
    ),
    re.compile(r"\.(?:select|selectExpr)\s*\(\s*[\"']\s*\*[\"']", re.IGNORECASE),
)
_UNRENDERED_TEMPLATE = re.compile(r"\{\{.*?\}\}|\$\{.*?\}", re.DOTALL)
_MAGIC_SELECT_STAR = re.compile(r"^\s*#\s*MAGIC\s+SELECT\s+\*\s+FROM\b", re.IGNORECASE)
_SQL_WILDCARD_PROJECTION = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?\*", re.IGNORECASE)


class NotebookValidationError(ValueError):
    """Raised when the source notebook violates the PF-107 contract."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _require_contract(source: str) -> None:
    if "# Databricks notebook source" not in source:
        raise NotebookValidationError("notebook_contract_invalid")
    if source.count(_COMMAND_SEPARATOR) < 5:
        raise NotebookValidationError("notebook_contract_invalid")
    if not re.search(r"dbutils\.widgets\.[A-Za-z_]+\s*\(", source):
        raise NotebookValidationError("notebook_contract_invalid")
    if not re.search(r"dbutils\.widgets\.get\s*\(", source):
        raise NotebookValidationError("notebook_contract_invalid")
    parquet_read = r"spark\.read(?:\.format\s*\(\s*[\"']parquet[\"']\s*\)|\.parquet)\s*\("
    if not re.search(parquet_read, source, re.IGNORECASE):
        raise NotebookValidationError("notebook_contract_invalid")
    if not re.search(r"\.format\s*\(\s*[\"']delta[\"']\s*\)", source, re.IGNORECASE):
        raise NotebookValidationError("notebook_contract_invalid")
    if not _SAVE_AS_TABLE.search(source):
        raise NotebookValidationError("notebook_contract_invalid")


def _reject_unsupported_apis(source: str) -> None:
    if _UNRENDERED_TEMPLATE.search(source):
        raise NotebookValidationError("unsupported_api")
    for line in source.splitlines():
        if _MAGIC_SELECT_STAR.match(line):
            continue
        if _SQL_WILDCARD_PROJECTION.search(line) or any(
            pattern.search(line) for pattern in _FORBIDDEN_PATTERNS
        ):
            raise NotebookValidationError("unsupported_api")


def _validate_table_contract(source: str) -> None:
    table_calls = _SAVE_AS_TABLE.findall(source)
    if not table_calls or any(not _QUALIFIED_TABLE.search(call) for call in table_calls):
        raise NotebookValidationError("table_contract")
    if not re.search(r"(?:_|\b)gold_overview_kpis\b", source, re.IGNORECASE):
        raise NotebookValidationError("table_contract")


def validate_notebook_source(source: str) -> None:
    """Validate the complete UTF-8 source text, including comments and strings."""
    if not isinstance(source, str):
        raise NotebookValidationError("notebook_contract_invalid")
    _require_contract(source)
    _reject_unsupported_apis(source)
    _validate_table_contract(source)


def validate_notebook_file(path: Path) -> None:
    """Read and validate a notebook without exposing filesystem error details."""
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise NotebookValidationError("notebook_contract_invalid") from None
    validate_notebook_source(source)


def notebook_sha256(source: str) -> str:
    """Return the SHA-256 digest of the exact UTF-8 notebook source."""
    if not isinstance(source, str):
        raise NotebookValidationError("notebook_contract_invalid")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
