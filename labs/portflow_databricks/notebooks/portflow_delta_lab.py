# ruff: noqa: E402, F821
# mypy: ignore-errors
# Databricks notebook source
# COMMAND ----------
dbutils.widgets.text("input_root", "/Volumes/demo/default/portflow")
dbutils.widgets.text("catalog", "demo")
dbutils.widgets.text("schema", "default")
dbutils.widgets.text("table_prefix", "pf107")

input_root = dbutils.widgets.get("input_root")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
table_prefix = dbutils.widgets.get("table_prefix")

# COMMAND ----------
bronze_telemetry_events = spark.read.parquet(f"{input_root}/telemetry_events")
bronze_container_movements = spark.read.parquet(f"{input_root}/container_movements")
bronze_incidents = spark.read.parquet(f"{input_root}/incidents")
bronze_alarms = spark.read.parquet(f"{input_root}/alarms")

bronze_telemetry_events.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_bronze_telemetry_events"
)
bronze_container_movements.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_bronze_container_movements"
)
bronze_incidents.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_bronze_incidents"
)
bronze_alarms.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_bronze_alarms"
)

# COMMAND ----------
from pyspark.sql import functions as F

silver_telemetry_events = bronze_telemetry_events.select(
    "event_id",
    "schema_version",
    "equipment_id",
    "terminal_id",
    "event_timestamp",
    "ingestion_timestamp",
    "state",
    "available",
    "load_percent",
    "temperature_c",
)
silver_container_movements = bronze_container_movements.select(
    "movement_id",
    "terminal_id",
    "equipment_id",
    "movement_type",
    "container_ref",
    "event_timestamp",
)
silver_incidents = bronze_incidents.select(
    "incident_id",
    "equipment_id",
    "severity",
    "status",
    "opened_at",
    "resolved_at",
    "root_cause",
)
silver_alarms = bronze_alarms.select(
    "alarm_id",
    "equipment_id",
    "severity",
    "code",
    "opened_at",
    "cleared_at",
)

silver_telemetry_events.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_silver_telemetry_events"
)
silver_container_movements.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_silver_container_movements"
)
silver_incidents.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_silver_incidents"
)
silver_alarms.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_silver_alarms"
)

# COMMAND ----------
equipment_terminal = silver_telemetry_events.select("equipment_id", "terminal_id").distinct()

telemetry_period = silver_telemetry_events.groupBy("terminal_id").agg(
    F.min("event_timestamp").alias("source_period_start"),
    F.max("event_timestamp").alias("source_period_end"),
    F.count("event_id").alias("scheduled_intervals"),
    F.sum(F.when(F.col("available"), F.lit(1)).otherwise(F.lit(0))).alias("available_intervals"),
    F.sum(F.when(F.col("state") == "ACTIVE", F.lit(1)).otherwise(F.lit(0))).alias(
        "active_intervals"
    ),
)
telemetry_period = telemetry_period.withColumn(
    "available_time_minutes", F.col("available_intervals") * F.lit(5)
)

movement_pairs = silver_container_movements.groupBy("terminal_id", "container_ref").agg(
    F.min(
        F.when(
            F.col("movement_type").isin("GATE_IN", "LOAD"),
            F.col("event_timestamp"),
        )
    ).alias("entry_timestamp"),
    F.max(
        F.when(
            F.col("movement_type").isin("GATE_OUT", "DISCHARGE"),
            F.col("event_timestamp"),
        )
    ).alias("exit_timestamp"),
)
movement_metrics = movement_pairs.groupBy("terminal_id").agg(
    F.sum(
        F.when(
            F.col("entry_timestamp").isNotNull() & F.col("exit_timestamp").isNotNull(),
            F.lit(1),
        ).otherwise(F.lit(0))
    ).alias("throughput"),
    F.avg(
        F.when(
            F.col("entry_timestamp").isNotNull() & F.col("exit_timestamp").isNotNull(),
            (F.unix_timestamp("exit_timestamp") - F.unix_timestamp("entry_timestamp"))
            / F.lit(60.0),
        )
    ).alias("average_dwell_minutes"),
)

incident_metrics = (
    silver_incidents.join(equipment_terminal, "equipment_id", "left")
    .groupBy("terminal_id")
    .agg(
        F.sum(F.when(F.col("status") == "RESOLVED", F.lit(1)).otherwise(F.lit(0))).alias(
            "resolved_incident_count"
        ),
        F.sum(
            F.when(
                F.col("status") == "RESOLVED",
                (F.unix_timestamp("resolved_at") - F.unix_timestamp("opened_at")) / F.lit(60.0),
            ).otherwise(F.lit(0.0))
        ).alias("repair_minutes"),
        F.sum(F.when(F.col("severity") == "CRITICAL", F.lit(1)).otherwise(F.lit(0))).alias(
            "qualifying_failure_count"
        ),
        F.sum(F.when(F.col("status") == "OPEN", F.lit(1)).otherwise(F.lit(0))).alias(
            "active_incidents"
        ),
    )
)

alarm_metrics = (
    silver_alarms.join(equipment_terminal, "equipment_id", "left")
    .join(telemetry_period, "terminal_id", "left")
    .groupBy("terminal_id")
    .agg(
        F.sum(
            F.when(
                (F.col("severity") == "CRITICAL")
                & F.col("opened_at").between(
                    F.col("source_period_start"), F.col("source_period_end")
                ),
                F.lit(1),
            ).otherwise(F.lit(0))
        ).alias("critical_alarms")
    )
)

# COMMAND ----------
gold = (
    telemetry_period.join(movement_metrics, "terminal_id", "left")
    .join(incident_metrics, "terminal_id", "left")
    .join(alarm_metrics, "terminal_id", "left")
    .withColumn("resolved_incident_count", F.coalesce(F.col("resolved_incident_count"), F.lit(0)))
    .withColumn("repair_minutes", F.coalesce(F.col("repair_minutes"), F.lit(0.0)))
    .withColumn(
        "qualifying_failure_count",
        F.coalesce(F.col("qualifying_failure_count"), F.lit(0)),
    )
    .withColumn("throughput", F.coalesce(F.col("throughput"), F.lit(0)))
    .withColumn("active_incidents", F.coalesce(F.col("active_incidents"), F.lit(0)))
    .withColumn("critical_alarms", F.coalesce(F.col("critical_alarms"), F.lit(0)))
    .withColumn(
        "operating_hours",
        F.col("scheduled_intervals") * F.lit(5.0) / F.lit(60.0),
    )
    .withColumn(
        "availability",
        F.when(
            F.col("scheduled_intervals") > F.lit(0),
            F.col("available_intervals") / F.col("scheduled_intervals"),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "utilization",
        F.when(
            F.col("available_intervals") > F.lit(0),
            F.col("active_intervals") / F.col("available_intervals"),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "mttr_minutes",
        F.when(
            F.col("resolved_incident_count") > F.lit(0),
            F.col("repair_minutes") / F.col("resolved_incident_count"),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "mtbf_hours",
        F.when(
            F.col("qualifying_failure_count") > F.lit(0),
            F.col("operating_hours") / F.col("qualifying_failure_count"),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "average_dwell_minutes",
        F.coalesce(F.col("average_dwell_minutes"), F.lit(0.0)),
    )
    .select(
        "terminal_id",
        "source_period_start",
        "source_period_end",
        "available_intervals",
        "scheduled_intervals",
        "active_intervals",
        "available_time_minutes",
        "resolved_incident_count",
        "repair_minutes",
        "qualifying_failure_count",
        "operating_hours",
        "throughput",
        "average_dwell_minutes",
        "availability",
        "utilization",
        "mttr_minutes",
        "mtbf_hours",
        "active_incidents",
        "critical_alarms",
    )
)
gold.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.{table_prefix}_gold_overview_kpis"
)

# COMMAND ----------
display(gold)

# COMMAND ----------
# MAGIC %sql
# MAGIC SELECT * FROM catalog.schema.prefix_gold_overview_kpis
