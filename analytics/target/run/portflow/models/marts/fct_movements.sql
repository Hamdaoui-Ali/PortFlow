
    

    create  table
      "portflow"."main"."fct_movements__dbt_tmp"
  
    
    as (
      select *
from "portflow"."main"."stg_container_movements"
    );
    
  