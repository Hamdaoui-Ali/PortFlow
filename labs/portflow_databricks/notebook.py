"""Static validation for the PF-107 Databricks source notebook."""

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_COMMAND_SEPARATOR = "# COMMAND ----------"
_SAVE_AS_TABLE = re.compile(r"saveAsTable\s*\(([^)]*)\)", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_PATTERNS = (
    re.compile(r"\brdd\b|\.toRDD\b", re.IGNORECASE),
    re.compile(r"\bsparkcontext\b|\.sparkcontext\b", re.IGNORECASE),
    re.compile(r"\b(?:udf|pandas_udf)\s*\(", re.IGNORECASE),
    re.compile(r"\bdbfs\b", re.IGNORECASE),
    re.compile(r"\bdbutils\.fs\b", re.IGNORECASE),
    re.compile(r"\bmaven\b|--packages\b|spark\.jars\.packages", re.IGNORECASE),
    re.compile(
        r"https?://|\bjdbc\b|\bhttp\.client\b|"
        r"\b(?:ftplib|smtplib|imaplib|poplib|nntplib|telnetlib|socket|"
        r"requests|urllib|urllib3|httpx|aiohttp|websocket|websockets|"
        r"paramiko|grpc|boto3|botocore|importlib|runpy|subprocess)\b|"
        r"\b(?:FTP|SMTP|HTTPConnection|HTTPSConnection|IMAP4|POP3|Telnet)\b|"
        r"\b(?:url)\s*[:=]|\bos\.(?:system|popen|spawn|exec\w*)\b|"
        r"\b(?:eval|exec|compile|__import__)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\.(?:select|selectExpr)\s*\(\s*[\"']\s*\*[\"']", re.IGNORECASE),
)
_UNRENDERED_TEMPLATE = re.compile(r"\{\{.*?\}\}|\$\{.*?\}", re.DOTALL)
_MAGIC_SQL_PREFIX = re.compile(r"^\s*#\s*MAGIC\b", re.IGNORECASE)
_MAGIC_SQL_LANGUAGE = re.compile(r"^\s*#\s*MAGIC\s+%sql\s*$", re.IGNORECASE)
_MAGIC_INSPECTION = re.compile(
    r"^\s*#\s*MAGIC\s+SELECT\s+\*\s+FROM\s+"
    r"catalog\.schema\.prefix_gold_overview_kpis\s*$",
    re.IGNORECASE,
)
_SQL_WILDCARD_PROJECTION = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?\*", re.IGNORECASE)
# Deliberately enumerated: importing functions does not approve every Spark
# function (expr, call_function, java_method, UDFs, etc. are escape surfaces).
_SQL_FUNCTIONS = frozenset(
    [
        "col",
        "column",
        "lit",
        "when",
        "coalesce",
        "count",
        "count_distinct",
        "countDistinct",
        "sum",
        "avg",
        "mean",
        "min",
        "max",
        "first",
        "last",
        "abs",
        "round",
        "bround",
        "greatest",
        "least",
        "isnan",
        "isnull",
        "lower",
        "upper",
        "trim",
        "ltrim",
        "rtrim",
        "length",
        "concat",
        "concat_ws",
        "substring",
        "regexp_replace",
        "to_timestamp",
        "to_date",
        "date_trunc",
        "datediff",
        "date_add",
        "date_sub",
        "unix_timestamp",
        "from_unixtime",
        "year",
        "month",
        "dayofmonth",
        "hour",
        "minute",
        "second",
        "lag",
        "lead",
        "row_number",
        "rank",
        "dense_rank",
        "sum_distinct",
    ]
)
_FRAME_METHODS = frozenset(
    [
        "select",
        "withColumn",
        "withColumns",
        "withColumnRenamed",
        "drop",
        "dropDuplicates",
        "distinct",
        "join",
        "crossJoin",
        "union",
        "unionByName",
        "orderBy",
        "sort",
        "limit",
        "alias",
        "fillna",
    ]
)
_COLUMN_METHODS = frozenset(
    [
        "alias",
        "cast",
        "astype",
        "when",
        "otherwise",
        "isNull",
        "isNotNull",
        "isin",
        "between",
        "asc",
        "desc",
        "asc_nulls_first",
        "asc_nulls_last",
        "desc_nulls_first",
        "desc_nulls_last",
        "over",
        "startswith",
        "endswith",
        "contains",
    ]
)
_WINDOW_METHODS = frozenset({"partitionBy", "orderBy", "rowsBetween", "rangeBetween"})
_DATA_KINDS = frozenset({"scalar", "sequence", "mapping", "frame", "column", "window"})
_PARAMETERS = frozenset({"input_root", "catalog", "schema", "table_prefix"})
_INPUT_TABLES = "(?:telemetry_events|container_movements|incidents|alarms)"
_VOLUME_ROOT = r"/Volumes/[A-Za-z0-9_]+/[A-Za-z0-9_]+/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*"
_INPUT_PATH = re.compile(r"(?:\{input_root\}|" + _VOLUME_ROOT + ")/" + _INPUT_TABLES + r"/?")
_TABLE_NAME = re.compile(
    r"(?:\{catalog\}\.\{schema\}\.\{(?:prefix|table_prefix)\}|catalog\.schema\.prefix)"
    r"_(?:(?:bronze|silver)_" + _INPUT_TABLES + r"|gold_overview_kpis)"
)


@dataclass(frozen=True)
class _Value:
    """Static provenance, never a live Python/Spark object or evaluated source."""

    kind: str
    text: str | None = None
    items: tuple["_Value", ...] = ()
    parameters: frozenset[str] = frozenset()


def _parameter(name: str) -> _Value:
    return _Value("scalar", "{" + name + "}", parameters=frozenset({name}))


def _matches_template(value: _Value, pattern: re.Pattern[str]) -> bool:
    """Literal braces cannot impersonate an actual widget-derived parameter."""
    return (
        value.kind == "scalar"
        and value.text is not None
        and pattern.fullmatch(value.text) is not None
        and frozenset(re.findall(r"\{([a-z_]+)\}", value.text)) == value.parameters
    )


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


def _reject_unsupported_apis(source: str) -> list[str]:
    if _UNRENDERED_TEMPLATE.search(source):
        raise NotebookValidationError("unsupported_api")
    tables = _validate_ast_surface(source)
    pending_sql = False
    for line in source.splitlines():
        if pending_sql and line.strip():
            if not _MAGIC_INSPECTION.fullmatch(line):
                raise NotebookValidationError("unsupported_api")
            pending_sql = False
        if _MAGIC_SQL_PREFIX.match(line):
            if _MAGIC_SQL_LANGUAGE.fullmatch(line):
                pending_sql = True
                continue
            if not _MAGIC_INSPECTION.fullmatch(line):
                raise NotebookValidationError("unsupported_api")
            continue
        if _SQL_WILDCARD_PROJECTION.search(line) or any(
            pattern.search(line) for pattern in _FORBIDDEN_PATTERNS
        ):
            raise NotebookValidationError("unsupported_api")
    if pending_sql:
        raise NotebookValidationError("unsupported_api")
    return tables


def _validate_ast_surface(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        raise NotebookValidationError("notebook_contract_invalid") from None
    try:
        policy = _NotebookPolicy()
        policy.validate(tree)
        return policy.tables
    except RecursionError:
        raise NotebookValidationError("unsupported_api") from None


class _NotebookPolicy:
    """Fail-closed, straight-line DataFrame language for this handoff artifact.

    Only imports, plain name assignments and expressions are statements. No
    user functions/classes, control flow, callable aliases, attribute mutation,
    or implicit traversal of unknown AST nodes is permitted. Every expression
    is checked, including every call argument and formatted-string component.
    This checks source, not runtime widget values or a compromised Spark host.
    """

    def __init__(self) -> None:
        self.names = {
            "spark": _Value("spark"),
            "dbutils": _Value("dbutils"),
            "display": _Value("display"),
            # The original Task 1 contract fixture intentionally leaves these
            # bindings implicit. No other unknown identifier gets this trust.
            "gold": _Value("frame"),
            "catalog": _parameter("catalog"),
            "schema": _parameter("schema"),
            "prefix": _parameter("prefix"),
        }
        self.protected = {"spark", "dbutils", "display"}
        self.contract: set[str] = set()
        self.tables: list[str] = []

    def validate(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._import(node)
            elif isinstance(node, ast.Assign):
                value = self._data(self._expression(node.value))
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        raise NotebookValidationError("unsupported_api")
                    self._bind(target.id, value)
            elif isinstance(node, ast.Expr):
                value = self._expression(node.value)
                if value.kind not in _DATA_KINDS | {"none"}:
                    raise NotebookValidationError("unsupported_api")
            else:
                raise NotebookValidationError("unsupported_api")
        if not {"widget_text", "widget_get", "parquet", "delta_write"} <= self.contract:
            raise NotebookValidationError("notebook_contract_invalid")

    def _bind(self, name: str, value: _Value, *, imported: bool = False) -> None:
        if name.startswith("_") or name in self.protected:
            raise NotebookValidationError("unsupported_api")
        if imported and name in self.names:
            raise NotebookValidationError("unsupported_api")
        self.names[name] = value
        if imported:
            self.protected.add(name)

    def _import(self, node: ast.Import | ast.ImportFrom) -> None:
        for alias in node.names:
            if isinstance(node, ast.Import):
                if alias.name != "pyspark.sql.functions":
                    raise NotebookValidationError("unsupported_api")
                name = alias.asname or "pyspark"
                value = _Value("functions" if alias.asname else "pyspark")
            else:
                if node.level:
                    raise NotebookValidationError("unsupported_api")
                name = alias.asname or alias.name
                if node.module == "pyspark.sql.functions" and alias.name in _SQL_FUNCTIONS:
                    value = _Value("function", alias.name)
                elif node.module == "pyspark.sql" and alias.name == "functions":
                    value = _Value("functions")
                elif (
                    node.module in {"pyspark.sql", "pyspark.sql.window"} and alias.name == "Window"
                ):
                    value = _Value("window_type")
                else:
                    raise NotebookValidationError("unsupported_api")
            self._bind(name, value, imported=True)

    @staticmethod
    def _data(value: _Value) -> _Value:
        if value.kind not in _DATA_KINDS:
            raise NotebookValidationError("unsupported_api")
        return value

    def _expression(self, node: ast.expr) -> _Value:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (str, int, float, bool, type(None))):
                raise NotebookValidationError("unsupported_api")
            return _Value("scalar", node.value if isinstance(node.value, str) else None)
        if isinstance(node, ast.Name):
            if node.id not in self.names:
                raise NotebookValidationError("unsupported_api")
            return self.names[node.id]
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.Attribute):
            owner = self._expression(node.value)
            attributes = {
                ("spark", "read"): "reader",
                ("dbutils", "widgets"): "widgets",
                ("pyspark", "sql"): "pyspark_sql",
                ("pyspark_sql", "functions"): "functions",
                ("window_type", "unboundedPreceding"): "scalar",
                ("window_type", "unboundedFollowing"): "scalar",
                ("window_type", "currentRow"): "scalar",
            }
            kind = attributes.get((owner.kind, node.attr))
            if kind is None:
                raise NotebookValidationError("unsupported_api")
            return _Value(kind)
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            parameters: frozenset[str] = frozenset()
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    if part.conversion != -1 or part.format_spec is not None:
                        raise NotebookValidationError("unsupported_api")
                    value = self._expression(part.value)
                elif isinstance(part, ast.Constant):
                    value = self._expression(part)
                else:
                    raise NotebookValidationError("unsupported_api")
                if value.kind != "scalar" or value.text is None:
                    raise NotebookValidationError("unsupported_api")
                parts.append(value.text)
                parameters |= value.parameters
            return _Value("scalar", "".join(parts), parameters=parameters)
        if isinstance(node, (ast.List, ast.Tuple)):
            return _Value(
                "sequence", items=tuple(self._data(self._expression(e)) for e in node.elts)
            )
        if isinstance(node, ast.Dict):
            values: list[_Value] = []
            for key, item in zip(node.keys, node.values, strict=True):
                if key is None:
                    raise NotebookValidationError("unsupported_api")
                values.extend(
                    (self._data(self._expression(key)), self._data(self._expression(item)))
                )
            return _Value("mapping", items=tuple(values))
        if isinstance(node, ast.Subscript):
            owner = self._expression(node.value)
            index = self._expression(node.slice)
            if owner.kind == "frame" and index.kind == "scalar" and index.text is not None:
                self._no_wildcards([index])
                return _Value("column")
            raise NotebookValidationError("unsupported_api")
        if isinstance(node, ast.BinOp):
            left, right = self._expression(node.left), self._expression(node.right)
            if not isinstance(
                node.op,
                (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.BitAnd, ast.BitOr),
            ):
                raise NotebookValidationError("unsupported_api")
            if (
                isinstance(node.op, ast.Add)
                and left.kind == right.kind == "scalar"
                and left.text is not None
                and right.text is not None
            ):
                return _Value(
                    "scalar", left.text + right.text, parameters=left.parameters | right.parameters
                )
            if left.text is not None or right.text is not None:
                # Do not lose string provenance through %, repetition, etc.
                raise NotebookValidationError("unsupported_api")
            return self._operator([left, right])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Invert)):
            return self._operator([self._expression(node.operand)])
        if isinstance(node, ast.Compare):
            return self._operator(
                [self._expression(node.left), *(self._expression(e) for e in node.comparators)]
            )
        raise NotebookValidationError("unsupported_api")

    @staticmethod
    def _operator(values: list[_Value]) -> _Value:
        if any(value.kind not in {"scalar", "column"} for value in values):
            raise NotebookValidationError("unsupported_api")
        return _Value("column" if any(value.kind == "column" for value in values) else "scalar")

    def _arguments(self, node: ast.Call) -> list[_Value]:
        values: list[_Value] = []
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                value = self._expression(arg.value)
                if value.kind != "sequence":
                    raise NotebookValidationError("unsupported_api")
                values.extend(value.items)
            else:
                values.append(self._data(self._expression(arg)))
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg.startswith("_"):
                raise NotebookValidationError("unsupported_api")
            values.append(self._data(self._expression(keyword.value)))
        return values

    @staticmethod
    def _no_wildcards(values: list[_Value]) -> None:
        for value in values:
            if value.text is not None and "*" in value.text:
                raise NotebookValidationError("unsupported_api")
            _NotebookPolicy._no_wildcards(list(value.items))

    @staticmethod
    def _positional(node: ast.Call, count: int) -> None:
        if (
            node.keywords
            or len(node.args) != count
            or any(isinstance(arg, ast.Starred) for arg in node.args)
        ):
            raise NotebookValidationError("unsupported_api")

    def _call(self, node: ast.Call) -> _Value:
        # Writers are validated as one complete syntactic chain. In particular
        # no writer object/method can be saved to a variable and mutated later.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "saveAsTable":
            return self._write(node)
        args = self._arguments(node)
        if isinstance(node.func, ast.Name):
            function = self._expression(node.func)
            if function.kind == "display":
                self._positional(node, 1)
                if args[0].kind != "frame":
                    raise NotebookValidationError("unsupported_api")
                return _Value("none")
            if function.kind == "function" and function.text in _SQL_FUNCTIONS:
                return self._sql_function(function.text, args)
            raise NotebookValidationError("unsupported_api")
        if not isinstance(node.func, ast.Attribute):
            raise NotebookValidationError("unsupported_api")
        owner = self._expression(node.func.value)
        method = node.func.attr
        if owner.kind == "functions" and method in _SQL_FUNCTIONS:
            return self._sql_function(method, args)
        if owner.kind == "widgets" and method in {"text", "get"}:
            return self._widget(node, method, args)
        if owner.kind == "reader" and method == "format":
            self._positional(node, 1)
            if args[0].text == "parquet":
                return _Value("parquet_reader")
        if (owner.kind, method) in {("reader", "parquet"), ("parquet_reader", "load")}:
            self._positional(node, 1)
            if not _matches_template(args[0], _INPUT_PATH):
                raise NotebookValidationError("unsupported_api")
            self.contract.add("parquet")
            return _Value("frame")
        if owner.kind == "spark" and method == "table":
            self._positional(node, 1)
            self._table(args[0])
            return _Value("frame")
        if owner.kind == "frame":
            if method in _FRAME_METHODS:
                if method in {"select", "drop"}:
                    self._no_wildcards(args)
                return _Value("frame")
            if method in {"filter", "where"}:
                self._positional(node, 1)
                if args[0].kind == "column":
                    return _Value("frame")
            if method in {"groupBy", "groupby"}:
                self._no_wildcards(args)
                return _Value("grouped")
        if (
            owner.kind in {"frame", "grouped"}
            and method == "agg"
            and args
            and all(arg.kind == "column" for arg in args)
        ):
            return _Value("frame")
        if owner.kind == "column" and method in _COLUMN_METHODS:
            return _Value("column")
        if owner.kind in {"window_type", "window"} and method in _WINDOW_METHODS:
            return _Value("window")
        if owner.kind == "scalar" and method == "rstrip":
            self._positional(node, 1)
            if args[0].text == "/" and owner.text == "{input_root}":
                return owner
        raise NotebookValidationError("unsupported_api")

    def _sql_function(self, function: str, args: list[_Value]) -> _Value:
        if function in {"col", "column"}:
            self._no_wildcards(args)
        return _Value("column")

    def _widget(self, node: ast.Call, method: str, args: list[_Value]) -> _Value:
        self._positional(node, 2 if method == "text" else 1)
        name = args[0].text
        if name not in _PARAMETERS:
            raise NotebookValidationError("unsupported_api")
        self.contract.add("widget_" + method)
        if method == "text":
            default = args[1].text
            pattern = _VOLUME_ROOT + "/?" if name == "input_root" else r"[A-Za-z_][A-Za-z0-9_]*"
            if default is None or not re.fullmatch(pattern, default):
                raise NotebookValidationError("unsupported_api")
            return _Value("none")
        return _parameter(str(name))

    @staticmethod
    def _table(value: _Value) -> str:
        if value.text is None or not _matches_template(value, _TABLE_NAME):
            raise NotebookValidationError("table_contract")
        return value.text

    def _write(self, node: ast.Call) -> _Value:
        self._positional(node, 1)
        table = self._table(self._expression(node.args[0]))
        assert isinstance(node.func, ast.Attribute)
        receiver = node.func.value
        seen: set[str] = set()
        while isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Attribute):
            method = receiver.func.attr
            if method not in {"format", "mode", "option"} or method in seen:
                raise NotebookValidationError("unsupported_api")
            seen.add(method)
            self._positional(receiver, 2 if method == "option" else 1)
            args = self._arguments(receiver)
            expected = {
                "format": ["delta"],
                "mode": ["overwrite"],
                "option": ["overwriteSchema", "true"],
            }[method]
            if [arg.text for arg in args] != expected:
                raise NotebookValidationError("unsupported_api")
            receiver = receiver.func.value
        if (
            "format" not in seen
            or not isinstance(receiver, ast.Attribute)
            or receiver.attr != "write"
            or self._expression(receiver.value).kind != "frame"
        ):
            raise NotebookValidationError("unsupported_api")
        self.contract.add("delta_write")
        self.tables.append(table)
        return _Value("none")


def _validate_table_contract(tables: list[str]) -> None:
    """Check actual AST writes, never matching names in comments or substrings."""
    if not tables or any(not _TABLE_NAME.fullmatch(table) for table in tables):
        raise NotebookValidationError("table_contract")
    if not any(table.endswith("_gold_overview_kpis") for table in tables):
        raise NotebookValidationError("table_contract")


def validate_notebook_source(source: str) -> None:
    """Validate the complete UTF-8 source text, including comments and strings."""
    if not isinstance(source, str):
        raise NotebookValidationError("notebook_contract_invalid")
    _require_contract(source)
    tables = _reject_unsupported_apis(source)
    _validate_table_contract(tables)


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
