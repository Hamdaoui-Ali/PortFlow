

select
    cast(movement_id as varchar) as movement_id,
    cast(terminal_id as varchar) as terminal_id,
    cast(equipment_id as varchar) as equipment_id,
    cast(movement_type as varchar) as movement_type,
    cast(container_ref as varchar) as container_ref,
    cast(event_timestamp as timestamptz) as event_timestamp,
    cast(created_at as timestamptz) as created_at,
    cast(updated_at as timestamptz) as updated_at,
    cast(source_table as varchar) as source_table,
    cast(extraction_run_id as varchar) as extraction_run_id,
    cast(source_updated_at as timestamptz) as source_updated_at,
    cast(extracted_at as timestamptz) as extracted_at
from read_parquet('C:/Users/aliha/AppData/Local/Temp/pytest-of-aliha/pytest-99/test_dbt_builds_gold_models_an0/silver/container_movements/**/*.parquet', union_by_name=true)