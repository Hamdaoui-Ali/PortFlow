
    
    

select
    terminal_id as unique_field,
    count(*) as n_records

from "portflow"."main"."overview_kpis"
where terminal_id is not null
group by terminal_id
having count(*) > 1


