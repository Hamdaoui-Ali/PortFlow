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


def test_notebook_sha256_hashes_utf8_source() -> None:
    expected = hashlib.sha256(SAFE_NOTEBOOK.encode("utf-8")).hexdigest()
    assert notebook_sha256(SAFE_NOTEBOOK) == expected


def test_notebook_file_validation_reads_utf8_source(tmp_path: Path) -> None:
    path = tmp_path / "notebook.py"
    path.write_text(SAFE_NOTEBOOK, encoding="utf-8")
    validate_notebook_file(path)
