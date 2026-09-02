
    
    

select
    event_id as unique_field,
    count(*) as n_records

from "portflow"."main"."fct_equipment_telemetry"
where event_id is not null
group by event_id
having count(*) > 1


