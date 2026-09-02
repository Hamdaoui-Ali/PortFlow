
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        movement_type as value_field,
        count(*) as n_records

    from "portflow"."main"."fct_movements"
    group by movement_type

)

select *
from all_values
where value_field not in (
    'GATE_IN','GATE_OUT','LOAD','DISCHARGE'
)



  
  
      
    ) dbt_internal_test