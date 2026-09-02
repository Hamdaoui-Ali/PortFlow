
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select terminal_id
from "portflow"."main"."fct_equipment_telemetry"
where terminal_id is null



  
  
      
    ) dbt_internal_test