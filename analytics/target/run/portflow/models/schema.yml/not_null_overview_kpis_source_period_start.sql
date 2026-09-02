
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select source_period_start
from "portflow"."main"."overview_kpis"
where source_period_start is null



  
  
      
    ) dbt_internal_test