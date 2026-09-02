{% set silver_root = env_var('PORTFLOW_SILVER_DIR', 'data/silver') %}

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
from read_parquet('{{ silver_root }}/container_movements/**/*.parquet', union_by_name=true)
