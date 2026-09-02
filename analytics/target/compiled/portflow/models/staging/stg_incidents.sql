

select
    cast(incident_id as varchar) as incident_id,
    cast(equipment_id as varchar) as equipment_id,
    cast(severity as varchar) as severity,
    cast(status as varchar) as status,
    cast(opened_at as timestamptz) as opened_at,
    cast(resolved_at as timestamptz) as resolved_at,
    cast(root_cause as varchar) as root_cause,
    cast(created_at as timestamptz) as created_at,
    cast(updated_at as timestamptz) as updated_at,
    cast(source_table as varchar) as source_table,
    cast(extraction_run_id as varchar) as extraction_run_id,
    cast(source_updated_at as timestamptz) as source_updated_at,
    cast(extracted_at as timestamptz) as extracted_at
from read_parquet('C:/Users/aliha/AppData/Local/Temp/pytest-of-aliha/pytest-99/test_dbt_builds_gold_models_an0/silver/incidents/**/*.parquet', union_by_name=true)