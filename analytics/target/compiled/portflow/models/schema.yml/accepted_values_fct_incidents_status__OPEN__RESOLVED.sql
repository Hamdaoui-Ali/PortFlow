
    
    

with all_values as (

    select
        status as value_field,
        count(*) as n_records

    from "portflow"."main"."fct_incidents"
    group by status

)

select *
from all_values
where value_field not in (
    'OPEN','RESOLVED'
)


