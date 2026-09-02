
    
    

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


