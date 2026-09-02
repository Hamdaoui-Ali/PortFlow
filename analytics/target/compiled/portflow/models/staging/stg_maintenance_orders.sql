

select
    cast(maintenance_order_id as varchar) as maintenance_order_id,
    cast(equipment_id as varchar) as equipment_id,
    cast(status as varchar) as status,
    cast(started_at as timestamptz) as started_at,
    cast(completed_at as timestamptz) as completed_at,
    cast(created_at as timestamptz) as created_at,
    cast(updated_at as timestamptz) as updated_at,
    cast(source_table as varchar) as source_table,
    cast(extraction_run_id as varchar) as extraction_run_id,
    cast(source_updated_at as timestamptz) as source_updated_at,
    cast(extracted_at as timestamptz) as extracted_at
from read_parquet('C:/Users/aliha/AppData/Local/Temp/pytest-of-aliha/pytest-99/test_dbt_builds_gold_models_an0/silver/maintenance_orders/**/*.parquet', union_by_name=true)