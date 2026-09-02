
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select availability
from "portflow"."main"."overview_kpis"
where availability is null



  
  
      
    ) dbt_internal_test