
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select movement_id
from "portflow"."main"."fct_movements"
where movement_id is null



  
  
      
    ) dbt_internal_test