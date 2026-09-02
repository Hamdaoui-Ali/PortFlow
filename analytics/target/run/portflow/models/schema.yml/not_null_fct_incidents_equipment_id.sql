
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select equipment_id
from "portflow"."main"."fct_incidents"
where equipment_id is null



  
  
      
    ) dbt_internal_test