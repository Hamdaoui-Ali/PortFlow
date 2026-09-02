
    
    

with all_values as (

    select
        state as value_field,
        count(*) as n_records

    from "portflow"."main"."fct_equipment_telemetry"
    group by state

)

select *
from all_values
where value_field not in (
    'IDLE','ACTIVE','WARNING','UNAVAILABLE','MAINTENANCE'
)


