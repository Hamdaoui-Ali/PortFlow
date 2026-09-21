import hashlib
from pathlib import Path

import pytest
from labs.portflow_databricks.notebook import (
    NotebookValidationError,
    notebook_sha256,
    validate_notebook_file,
    validate_notebook_source,
)

SAFE_NOTEBOOK = """# Databricks notebook source
# COMMAND ----------
dbutils.widgets.text("input_root", "/Volumes/demo/default/portflow")
input_root = dbutils.widgets.get("input_root")
bronze = spark.read.parquet(f"{input_root}/telemetry_events")
bronze.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_bronze_telemetry_events")
# COMMAND ----------
silver = bronze.select("event_id", "terminal_id", "event_timestamp")
silver.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_silver_telemetry_events")
# COMMAND ----------
gold.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_gold_overview_kpis")
# COMMAND ----------
gold.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_gold_overview_kpis")
# COMMAND ----------
gold.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{prefix}_gold_overview_kpis")
# COMMAND ----------
"""


def test_notebook_contract_accepts_serverless_shape() -> None:
    validate_notebook_source(SAFE_NOTEBOOK)


@pytest.mark.parametrize(
    "forbidden",
    [
        "spark.sparkContext",
        "frame.rdd",
        "dbutils.fs",
        "udf(",
        "dbfs:/",
        "maven",
        "https://example.invalid",
        "SELECT * FROM unsafe_table",
        "{{catalog}}",
    ],
)
def test_notebook_rejects_forbidden_tokens_in_comments(forbidden: str) -> None:
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n# {forbidden}\n")


def test_notebook_requires_qualified_delta_table_writes() -> None:
    with pytest.raises(NotebookValidationError, match="table_contract"):
        validate_notebook_source(
            SAFE_NOTEBOOK.replace('f"{catalog}.{schema}.{prefix}_', '"unqualified_')
        )


def test_notebook_allows_read_only_magic_inspection_query() -> None:
    validate_notebook_source(
        SAFE_NOTEBOOK + "\n# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis\n"
    )


@pytest.mark.parametrize(
    "unsafe_magic_sql",
    [
        "# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis; "
        "DROP TABLE catalog.schema.important",
        "# MAGIC DROP TABLE catalog.schema.prefix_gold_overview_kpis",
    ],
)
def test_notebook_rejects_mutating_or_multi_statement_magic_sql(unsafe_magic_sql: str) -> None:
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n{unsafe_magic_sql}\n")


def test_notebook_rejects_standard_jdbc_datasource_form() -> None:
    jdbc_read = 'spark.read.format("jdbc").option("url", "remote").load()'
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n# {jdbc_read}\n")


def test_notebook_rejects_standard_library_ftp_client() -> None:
    ftp_client = 'from ftplib import FTP\nFTP("example.invalid")'
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n{ftp_client}\n")


def test_notebook_rejects_urllib3_pool_manager_network_client() -> None:
    urllib3_client = """import urllib3
client = urllib3.PoolManager()
client.request("GET", "https" + "://" + "example.invalid")
"""
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n{urllib3_client}\n")


def test_notebook_rejects_non_pyspark_imports() -> None:
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + "\nimport os\n")


def test_notebook_rejects_builtin_open_file_write() -> None:
    file_write = """with open("/tmp/pf107-escape", "w", encoding="utf-8") as handle:
    handle.write("payload")
"""
    with pytest.raises(NotebookValidationError, match="unsupported_api"):
        validate_notebook_source(SAFE_NOTEBOOK + f"\n{file_write}")


def test_notebook_allows_required_pyspark_import_surface() -> None:
    pyspark_imports = """from pyspark.sql import functions as F
from pyspark.sql.functions import col, when
from pyspark.sql.window import Window
"""
    validate_notebook_source(SAFE_NOTEBOOK + f"\n{pyspark_imports}\n")


def test_notebook_sha256_hashes_utf8_source() -> None:
    expected = hashlib.sha256(SAFE_NOTEBOOK.encode("utf-8")).hexdigest()
    assert notebook_sha256(SAFE_NOTEBOOK) == expected


def test_notebook_file_validation_reads_utf8_source(tmp_path: Path) -> None:
    path = tmp_path / "notebook.py"
    path.write_text(SAFE_NOTEBOOK, encoding="utf-8")
    validate_notebook_file(path)


REVIEWER_ESCAPES = [
    'with __builtins__.open("/tmp/pf107-escape", "w", encoding="utf-8") as handle: '
    'handle.write("payload")',
    'gold.write.format("delta").mode("overwrite").save("/tmp/pf107-escape")',
    'spark.sql("DROP TABLE catalog.schema.prefix_gold_overview_kpis")',
    'spark._jvm.java.net.URL("https" + "://example.invalid").openConnection()',
    'getattr(getattr(__builtins__, "__im" + "port__")("o" + "s"), "sy" + "stem")("echo pf107")',
]


@pytest.mark.parametrize("payload", REVIEWER_ESCAPES)
def test_notebook_rejects_reviewer_escape_payloads(payload: str) -> None:
    with pytest.raises(NotebookValidationError) as error:
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + payload)
    assert error.value.reason_code == "unsupported_api"
    assert str(error.value) == "unsupported_api"


@pytest.mark.parametrize(
    "payload",
    [
        'getattr(gold, "write")',
        'vars()["danger"]("payload")',
        'globals()["danger"]("payload")',
        "type(gold)",
        'print("payload", file=gold)',
        "display(__builtins__)",
        'danger("payload")',
        "gold.unknown_api()",
        "gold._jdf",
        "gold.__class__",
        'spark.conf.set("key", "value")',
        'spark.catalog.dropTempView("x")',
        'dbutils.notebook.run("other", 0)',
        "dbutils.widgets.removeAll()",
        'gold.toPandas().to_csv("/tmp/pf107-escape")',
        "gold.foreach(print)",
        'gold.mapInPandas(lambda rows: rows, "x string")',
        'gold.selectExpr("java_method(1)")',
        'gold.filter("reflect(1)")',
        'gold.where("reflect(1)")',
        'from pyspark.sql.functions import java_method\njava_method("x", "y")',
        "from pyspark.sql.functions import builtin",
        "from pyspark.sql.functions import *",
        'from pyspark.sql import functions as F\nF.expr("reflect(1)")',
        'from pyspark.sql import functions as F\nF.call_function("reflect", "x")',
        'from pyspark.sql import functions as F\nF.__getattr__("x")',
        "from pyspark.sql import functions as F\nF.lit(spark)",
        "from pyspark.sql import functions as F\nF.col = display",
        'read = spark.read.parquet\nread("/tmp/pf107-escape")',
        'write = gold.write\nwrite.save("/tmp/pf107-escape")',
        "f = display\nf(gold)",
        "spark = gold",
        'gold = "other"\ngold.select("x")',
        'gold["x"] = 1',
        "del gold",
        "def danger():\n    pass",
        "@display\nclass Danger:\n    pass",
        "(lambda: gold)()",
        "[display(gold) for item in [1]]",
        "if False:\n    danger()",
        "try:\n    danger()\nexcept:\n    pass",
        'gold.write.format("parquet").mode("overwrite").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'gold.write.format("delta").option("path", "/tmp/escape").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'gold.write.format("delta").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis", path="/tmp/escape")',
        'gold.write.format("delta").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis", format="parquet")',
        'gold.write.mode("overwrite").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'gold.write.format("delta").format("parquet").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'spark.read.format("text").load("/tmp/escape")',
        'spark.read.parquet("/tmp/pf107-escape")',
        'spark.read.parquet("https" + "://example.invalid")',
        'spark.read.parquet(f"{input_root}/../escape")',
        'spark.read.parquet("{input_root}/telemetry_events")',
        'root = "{" + "input_root}"\nspark.read.parquet(f"{root}/telemetry_events")',
        'input_root = "{input_root}"\nspark.read.parquet(f"{input_root}/telemetry_events")',
        'spark.read.parquet(f"{input_root}/telemetry_events", pathGlobFilter="*")',
        'spark.read.option("x", "y").parquet(f"{input_root}/telemetry_events")',
        'gold.select("terminal_id", "*")',
        'gold.select(["terminal_id", "gold.*"])',
        'star = "*"\ngold.select(star * 1)',
        'star = "%s" % "*"\ngold.select(star)',
        'from pyspark.sql import functions as F\ngold.select(F.col("*"))',
    ],
)
def test_notebook_rejects_unapproved_surface(payload: str) -> None:
    with pytest.raises(NotebookValidationError) as error:
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + payload)
    assert error.value.reason_code == "unsupported_api"
    assert str(error.value) == "unsupported_api"


@pytest.mark.parametrize("method", ["save", "text", "csv", "json", "parquet", "insertInto"])
def test_notebook_rejects_every_unapproved_writer_terminal(method: str) -> None:
    payload = f'gold.write.format("delta").mode("overwrite").{method}("/tmp/escape")'
    with pytest.raises(NotebookValidationError, match="^unsupported_api$"):
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + payload)


@pytest.mark.parametrize(
    "table",
    [
        '"unqualified_gold_overview_kpis"',
        '"other.catalog.schema.prefix_gold_overview_kpis"',
        'f"other.{catalog}.{schema}.{prefix}_gold_overview_kpis"',
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis.extra"',
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis/escape"',
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis;DROP"',
        '"{catalog}.{schema}.{prefix}_gold_overview_kpis"',
        '"{" + "catalog}.{schema}.{prefix}_gold_overview_kpis"',
    ],
)
def test_notebook_rejects_table_substring_spoofing(table: str) -> None:
    payload = f'gold.write.format("delta").mode("overwrite").saveAsTable({table})'
    with pytest.raises(NotebookValidationError, match="^table_contract$"):
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + payload)


def test_notebook_allows_combined_required_transformation_surface() -> None:
    source = """from pyspark.sql import functions as F, Window
from pyspark.sql.functions import col, when, sum as spark_sum
from pyspark.sql.window import Window as W
dbutils.widgets.text("catalog", "demo")
dbutils.widgets.text("schema", "default")
dbutils.widgets.text("table_prefix", "pf107")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
table_prefix = dbutils.widgets.get("table_prefix")
prefix = table_prefix
movements = spark.read.format("parquet").load(f"{input_root}/container_movements")
incidents = spark.read.parquet(f"{input_root}/incidents")
alarms = spark.read.parquet(f"{input_root}/alarms")
typed = bronze.select(
    col("terminal_id").cast("string").alias("terminal_id"),
    F.col("event_timestamp").cast("timestamp").alias("event_timestamp"),
    F.col("active").cast("boolean").alias("active"),
    F.col("duration").cast("double").alias("duration"),
)
window = Window.partitionBy("terminal_id").orderBy("event_timestamp")
bounded = W.partitionBy("terminal_id").orderBy("event_timestamp").rowsBetween(
    Window.unboundedPreceding, Window.currentRow
)
typed = typed.withColumn("previous", F.lag("event_timestamp").over(window))
typed = typed.withColumn("rank", F.row_number().over(bounded))
typed = typed.withColumn("seconds", F.unix_timestamp("event_timestamp") -
    F.unix_timestamp("previous"))
typed = typed.filter(F.col("seconds").isNotNull() & (F.col("seconds") >= 0))
metrics = typed.groupBy("terminal_id").agg(
    F.count(when(F.col("active") == True, 1)).alias("active_intervals"),
    F.count("*").alias("scheduled_intervals"),
    spark_sum("duration").alias("available_time_minutes"),
    F.min("event_timestamp").alias("source_period_start"),
    F.max("event_timestamp").alias("source_period_end"),
    F.avg("seconds").alias("average_dwell_minutes"),
)
other = movements.groupBy("terminal_id").agg(F.count("*").alias("throughput"))
gold = metrics.join(other, ["terminal_id"], "left").fillna({"throughput": 0})
gold = gold.withColumn("availability", F.when(F.col("scheduled_intervals") > 0,
    F.col("active_intervals") / F.col("scheduled_intervals")).otherwise(F.lit(None)))
gold = gold.withColumn("throughput", F.coalesce(F.col("throughput"), F.lit(0)))
columns = ["terminal_id", "availability", "throughput"]
gold = gold.select(*columns).orderBy("terminal_id")
gold.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_gold_overview_kpis")
display(gold.orderBy("terminal_id"))
# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis
"""
    validate_notebook_source(SAFE_NOTEBOOK + "\n" + source)


@pytest.mark.parametrize(
    "imports, expression",
    [
        ("import pyspark.sql.functions as sf", 'sf.col("terminal_id")'),
        ("import pyspark.sql.functions", 'pyspark.sql.functions.col("terminal_id")'),
        ("from pyspark.sql import functions", 'functions.col("terminal_id")'),
        ("from pyspark.sql.functions import col as c", 'c("terminal_id")'),
    ],
)
def test_notebook_allows_approved_import_aliases(imports: str, expression: str) -> None:
    validate_notebook_source(SAFE_NOTEBOOK + f"\n{imports}\ngold.select({expression})")


def test_notebook_allows_names_with_proven_qualified_table_values() -> None:
    validate_notebook_source(
        SAFE_NOTEBOOK + '\ntarget = f"{catalog}.{schema}.{prefix}_gold_overview_kpis"\n'
        'gold.write.format("delta").mode("overwrite").saveAsTable(target)'
    )


def test_notebook_allows_exact_magic_sql_cell() -> None:
    validate_notebook_source(
        SAFE_NOTEBOOK + "# MAGIC %sql\n"
        "# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis\n"
    )


@pytest.mark.parametrize(
    "payload",
    [
        "# MAGIC %sql",
        "# MAGIC %sql\n# COMMAND ----------\n"
        "# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis",
        "# MAGIC %python\n# MAGIC display(gold)",
        "# MAGIC %sh echo pf107",
        "# MAGIC %sql\n# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis;",
        "# MAGIC %sql\n# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis\n"
        "# MAGIC DROP TABLE catalog.schema.prefix_gold_overview_kpis",
    ],
)
def test_notebook_rejects_unapproved_magic_cells(payload: str) -> None:
    with pytest.raises(NotebookValidationError, match="^unsupported_api$"):
        validate_notebook_source(SAFE_NOTEBOOK + payload)


@pytest.mark.parametrize(
    "original, replacement",
    [
        ('dbutils.widgets.text("input_root", "/Volumes/demo/default/portflow")', ""),
        (
            'input_root = dbutils.widgets.get("input_root")',
            'input_root = "/Volumes/demo/default/portflow"',
        ),
    ],
)
def test_notebook_contract_cannot_be_satisfied_by_comments(original: str, replacement: str) -> None:
    with pytest.raises(NotebookValidationError, match="^notebook_contract_invalid$"):
        validate_notebook_source(SAFE_NOTEBOOK.replace(original, f"# {original}\n{replacement}"))


@pytest.mark.parametrize("payload", ["broken(", "\x00"])
def test_notebook_parse_failures_are_bounded(payload: str) -> None:
    with pytest.raises(NotebookValidationError, match="^notebook_contract_invalid$"):
        validate_notebook_source(SAFE_NOTEBOOK + payload)


@pytest.mark.parametrize(
    "assignment",
    [
        'catalog = "{catalog}"',
        'schema = "{schema}"',
        'prefix = "{prefix}"',
        'catalog = "other"',
        'schema = "default.other"',
        'prefix = "../escape"',
    ],
)
def test_notebook_rejects_replaced_table_parameter_provenance(assignment: str) -> None:
    with pytest.raises(NotebookValidationError, match="^table_contract$"):
        validate_notebook_source(
            SAFE_NOTEBOOK + f"\n{assignment}\n"
            'gold.write.format("delta").mode("overwrite").saveAsTable('
            'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")'
        )


def test_notebook_allows_volume_paths_and_column_expressions() -> None:
    validate_notebook_source(
        SAFE_NOTEBOOK
        + """
from pyspark.sql import functions as F
input_root = input_root.rstrip("/")
copy = spark.read.parquet(input_root + "/telemetry_events")
copy = copy.select(copy["terminal_id"], F.col("active").alias("active"))
copy = copy.where(~F.col("active").isNull()).dropDuplicates(["terminal_id"])
copy = copy.withColumn("active", F.when(F.col("active") == "yes", 1).otherwise(0))
loaded = spark.table(f"{catalog}.{schema}.{prefix}_bronze_telemetry_events")
copy.write.mode("overwrite").format("delta").saveAsTable(
    f"{catalog}.{schema}.{prefix}_silver_telemetry_events")
display(loaded)
"""
    )


@pytest.mark.parametrize(
    "payload",
    [
        'gold.write.format("delta").mode("overwrite").saveAsTable("catalog.schema.prefix_gold_overview_kpis")',
        (
            'literal = "catalog.schema.prefix_gold_overview_kpis"\n'
            'gold.write.format("delta").mode("overwrite").saveAsTable(literal)'
        ),
        (
            'literal = "catalog.schema." + "prefix_gold_overview_kpis"\n'
            'gold.write.format("delta").mode("overwrite").saveAsTable(literal)'
        ),
        (
            'catalog = "catalog"\nschema = "schema"\nprefix = "prefix"\n'
            'gold.write.format("delta").mode("overwrite").saveAsTable('
            'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")'
        ),
    ],
)
def test_notebook_rejects_executable_literal_table_provenance(payload: str) -> None:
    source = SAFE_NOTEBOOK + "\n" + payload + "\n"
    with pytest.raises(NotebookValidationError, match="^table_contract$"):
        validate_notebook_source(source)


@pytest.mark.parametrize(
    "read_expression",
    [
        'spark.read.parquet("/Volumes/other/default/private/telemetry_events")',
        (
            'literal = "/Volumes/other/default/private/telemetry_events"\n'
            'spark.read.parquet(literal)'
        ),
        (
            'input_root = "/Volumes/other/default/private"\n'
            'spark.read.parquet(f"{input_root}/telemetry_events")'
        ),
    ],
)
def test_notebook_rejects_executable_literal_input_provenance(read_expression: str) -> None:
    with pytest.raises(NotebookValidationError, match="^unsupported_api$"):
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + read_expression)


@pytest.mark.parametrize(
    "fragment",
    [
        "# Databricks notebook source",
        "# COMMAND ----------",
        'dbutils.widgets.text("input_root", "/Volumes/demo/default/portflow")',
        'input_root = dbutils.widgets.get("input_root")',
        'bronze = spark.read.parquet(f"{input_root}/telemetry_events")',
        '.format("delta")',
        ".saveAsTable",
    ],
)
def test_notebook_preserves_required_structure_checks(fragment: str) -> None:
    with pytest.raises(NotebookValidationError, match="^notebook_contract_invalid$"):
        validate_notebook_source(SAFE_NOTEBOOK.replace(fragment, ""))


def test_notebook_gold_contract_cannot_be_satisfied_by_comment() -> None:
    source = SAFE_NOTEBOOK.replace("_gold_overview_kpis", "_silver_alarms")
    with pytest.raises(NotebookValidationError, match="^table_contract$"):
        validate_notebook_source(source + "\n# gold_overview_kpis")


def test_notebook_cannot_satisfy_read_and_write_contracts_with_comments() -> None:
    source = "\n".join("# " + line for line in SAFE_NOTEBOOK.splitlines())
    with pytest.raises(NotebookValidationError, match="^notebook_contract_invalid$"):
        validate_notebook_source(source)


@pytest.mark.parametrize(
    "payload",
    [
        "display(gold.select(danger()))",
        'gold.select(f"{danger()}")',
        "gold.select([danger()])",
        'gold.fillna({"terminal_id": danger()})',
        "gold.select(*[danger()])",
        'gold.orderBy("terminal_id", ascending=danger())',
        'gold.orderBy("terminal_id", **{"ascending": True})',
        'gold.write.format("delta").saveAsTable(danger())',
        "from .pyspark.sql import functions as F",
        "import pyspark.sql.functions as spark",
        "from pyspark.sql import functions as F\nF = gold",
        "from pyspark.sql import functions as F\nfunctions = F",
        'from pyspark.sql import functions as F\nF.col("x").__class__',
        'from pyspark.sql import functions as F\nF.col("x").unknown_api()',
        "from pyspark.sql import Window\nWindow.unknown_api()",
        'gold.write.format("delta").option("overwriteSchema", "true").option('
        '"path", "/tmp/escape").saveAsTable(f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'gold.write.format("delta").mode("append").saveAsTable('
        'f"{catalog}.{schema}.{prefix}_gold_overview_kpis")',
        'spark.read.format("parquet").load(f"{input_root}/telemetry_events", format="text")',
        'dbutils.widgets.text("input_root", "/tmp/escape")',
        'dbutils.widgets.text("catalog", "other.schema")',
        'dbutils.widgets.get("unapproved")',
    ],
)
def test_notebook_policy_checks_nested_expressions_and_argument_boundaries(payload: str) -> None:
    with pytest.raises(NotebookValidationError, match="^unsupported_api$"):
        validate_notebook_source(SAFE_NOTEBOOK + "\n" + payload)


@pytest.mark.parametrize("bad_file", [b"\xff", None])
def test_notebook_file_failures_are_bounded(tmp_path: Path, bad_file: bytes | None) -> None:
    path = tmp_path / "notebook.py"
    if bad_file is not None:
        path.write_bytes(bad_file)
    with pytest.raises(NotebookValidationError, match="^notebook_contract_invalid$"):
        validate_notebook_file(path)
