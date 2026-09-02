with telemetry_period as (
    select
        terminal_id,
        min(event_timestamp) as source_period_start,
        max(event_timestamp) as source_period_end,
        count(*) as scheduled_intervals,
        count(*) filter (where available) as available_intervals,
        count(*) filter (where state = 'ACTIVE') as active_intervals,
        count(*) filter (where available) * 5 as available_time_minutes
    from "portflow"."main"."fct_equipment_telemetry"
    group by terminal_id
),
movement_pairs as (
    select
        terminal_id,
        container_ref,
        min(event_timestamp) filter (where movement_type in ('GATE_IN', 'LOAD')) as entry_timestamp,
        max(event_timestamp) filter (where movement_type in ('GATE_OUT', 'DISCHARGE')) as exit_timestamp
    from "portflow"."main"."fct_movements"
    group by terminal_id, container_ref
),
movement_metrics as (
    select
        terminal_id,
        count(*) filter (where entry_timestamp is not null and exit_timestamp is not null) as throughput,
        avg(
            date_diff('second', entry_timestamp, exit_timestamp) / 60.0
        ) filter (where entry_timestamp is not null and exit_timestamp is not null) as average_dwell_minutes
    from movement_pairs
    group by terminal_id
),
incident_metrics as (
    select
        p.terminal_id,
        count(*) filter (where i.status = 'RESOLVED') as resolved_incident_count,
        coalesce(
            sum(date_diff('second', i.opened_at, i.resolved_at) / 60.0)
                filter (where i.status = 'RESOLVED'),
            0
        ) as repair_minutes,
        count(*) filter (where i.severity = 'CRITICAL') as qualifying_failure_count,
        count(*) filter (
            where i.status = 'OPEN'
              and i.opened_at <= p.source_period_end
              and (i.resolved_at is null or i.resolved_at > p.source_period_end)
        ) as active_incidents
    from "portflow"."main"."fct_incidents" i
    join telemetry_period p on p.terminal_id = 'TM-001'
    group by p.terminal_id
),
alarm_metrics as (
    select
        p.terminal_id,
        count(*) filter (
            where a.severity = 'CRITICAL'
              and a.opened_at between p.source_period_start and p.source_period_end
        ) as critical_alarms
    from "portflow"."main"."stg_alarms" a
    cross join telemetry_period p
    group by p.terminal_id
)
select
    p.terminal_id,
    p.source_period_start,
    p.source_period_end,
    p.available_intervals,
    p.scheduled_intervals,
    p.active_intervals,
    p.available_time_minutes,
    coalesce(i.resolved_incident_count, 0) as resolved_incident_count,
    coalesce(i.repair_minutes, 0) as repair_minutes,
    coalesce(i.qualifying_failure_count, 0) as qualifying_failure_count,
    p.scheduled_intervals * 5.0 / 60.0 as operating_hours,
    coalesce(m.throughput, 0) as throughput,
    m.average_dwell_minutes,
    case
        when p.scheduled_intervals = 0 then null
        else p.available_intervals * 1.0 / p.scheduled_intervals
    end as availability,
    case
        when p.available_intervals = 0 then null
        else p.active_intervals * 1.0 / p.available_intervals
    end as utilization,
    case
        when coalesce(i.resolved_incident_count, 0) = 0 then null
        else i.repair_minutes / i.resolved_incident_count
    end as mttr_minutes,
    case
        when coalesce(i.qualifying_failure_count, 0) = 0 then null
        else (p.scheduled_intervals * 5.0 / 60.0) / i.qualifying_failure_count
    end as mtbf_hours,
    coalesce(i.active_incidents, 0) as active_incidents,
    coalesce(a.critical_alarms, 0) as critical_alarms
from telemetry_period p
left join movement_metrics m on m.terminal_id = p.terminal_id
left join incident_metrics i on i.terminal_id = p.terminal_id
left join alarm_metrics a on a.terminal_id = p.terminal_id