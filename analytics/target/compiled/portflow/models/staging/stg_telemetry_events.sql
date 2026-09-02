

select
    cast(event_id as varchar) as event_id,
    cast(schema_version as smallint) as schema_version,
    cast(equipment_id as varchar) as equipment_id,
    cast(terminal_id as varchar) as terminal_id,
    cast(event_timestamp as timestamptz) as event_timestamp,
    cast(ingestion_timestamp as timestamptz) as ingestion_timestamp,
    cast(state as varchar) as state,
    cast(available as boolean) as available,
    cast(load_percent as double) as load_percent,
    cast(temperature_c as double) as temperature_c,
    cast(created_at as timestamptz) as created_at,
    cast(updated_at as timestamptz) as updated_at,
    cast(source_table as varchar) as source_table,
    cast(extraction_run_id as varchar) as extraction_run_id,
    cast(source_updated_at as timestamptz) as source_updated_at,
    cast(extracted_at as timestamptz) as extracted_at
from read_parquet('C:/Users/aliha/AppData/Local/Temp/pytest-of-aliha/pytest-99/test_dbt_builds_gold_models_an0/silver/telemetry_events/**/*.parquet', union_by_name=true)