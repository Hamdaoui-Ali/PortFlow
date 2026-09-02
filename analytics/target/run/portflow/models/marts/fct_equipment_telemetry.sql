
    

    create  table
      "portflow"."main"."fct_equipment_telemetry__dbt_tmp"
  
    
    as (
      select *
from "portflow"."main"."stg_telemetry_events"
    );
    
  