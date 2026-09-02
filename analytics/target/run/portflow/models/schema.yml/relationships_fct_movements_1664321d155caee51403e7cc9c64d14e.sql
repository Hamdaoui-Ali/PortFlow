
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with child as (
    select terminal_id as from_field
    from "portflow"."main"."fct_movements"
    where terminal_id is not null
),

parent as (
    select terminal_id as to_field
    from "portflow"."main"."fct_equipment_telemetry"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null



  
  
      
    ) dbt_internal_test