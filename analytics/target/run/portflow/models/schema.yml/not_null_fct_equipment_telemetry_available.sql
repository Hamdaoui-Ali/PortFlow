
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select available
from "portflow"."main"."fct_equipment_telemetry"
where available is null



  
  
      
    ) dbt_internal_test