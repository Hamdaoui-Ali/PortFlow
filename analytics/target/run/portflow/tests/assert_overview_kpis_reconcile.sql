
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select *
from "portflow"."main"."overview_kpis"
where availability < 0
   or availability > 1
   or utilization < 0
   or utilization > 1
  
  
      
    ) dbt_internal_test