select *
from "portflow"."main"."overview_kpis"
where availability < 0
   or availability > 1
   or utilization < 0
   or utilization > 1