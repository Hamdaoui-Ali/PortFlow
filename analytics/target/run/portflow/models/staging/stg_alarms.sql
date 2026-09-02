
  
  create view "portflow"."main"."stg_alarms__dbt_tmp" as (
    

select
    cast(alarm_id as varchar) as alarm_id,
    cast(equipment_id as varchar) as equipment_id,
    cast(severity as varchar) as severity,
    cast(code as varchar) as code,
    cast(opened_at as timestamptz) as opened_at,
    cast(cleared_at as timestamptz) as cleared_at,
    cast(created_at as timestamptz) as created_at,
    cast(updated_at as timestamptz) as updated_at,
    cast(source_table as varchar) as source_table,
    cast(extraction_run_id as varchar) as extraction_run_id,
    cast(source_updated_at as timestamptz) as source_updated_at,
    cast(extracted_at as timestamptz) as extracted_at
from read_parquet('C:/Users/aliha/AppData/Local/Temp/pytest-of-aliha/pytest-99/test_dbt_builds_gold_models_an0/silver/alarms/**/*.parquet', union_by_name=true)
  );
