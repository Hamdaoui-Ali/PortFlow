
    

    create  table
      "portflow"."main"."fct_incidents__dbt_tmp"
  
    
    as (
      select *
from "portflow"."main"."stg_incidents"
    );
    
  