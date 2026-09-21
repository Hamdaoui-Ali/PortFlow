WITH telemetry_period AS (
  SELECT
    terminal_id,
    MIN(event_timestamp) AS source_period_start,
    MAX(event_timestamp) AS source_period_end,
    COUNT(*) AS scheduled_intervals,
    COUNTIF(available) AS available_intervals,
    COUNTIF(state = 'ACTIVE') AS active_intervals,
    COUNTIF(available) * 5 AS available_time_minutes
  FROM `{{ project_id }}.{{ dataset }}.fct_equipment_telemetry`
  GROUP BY terminal_id
),
movement_pairs AS (
  SELECT
    terminal_id,
    container_ref,
    MIN(IF(movement_type IN ('GATE_IN', 'LOAD'), event_timestamp, NULL)) AS entry_timestamp,
    MAX(IF(movement_type IN ('GATE_OUT', 'DISCHARGE'), event_timestamp, NULL)) AS exit_timestamp
  FROM `{{ project_id }}.{{ dataset }}.fct_movements`
  GROUP BY terminal_id, container_ref
),
movement_metrics AS (
  SELECT
    terminal_id,
    COUNTIF(entry_timestamp IS NOT NULL AND exit_timestamp IS NOT NULL) AS throughput,
    AVG(
      IF(
        entry_timestamp IS NOT NULL AND exit_timestamp IS NOT NULL,
        TIMESTAMP_DIFF(exit_timestamp, entry_timestamp, SECOND) / 60.0,
        NULL
      )
    ) AS average_dwell_minutes
  FROM movement_pairs
  GROUP BY terminal_id
),
incident_metrics AS (
  SELECT
    p.terminal_id,
    COUNTIF(i.status = 'RESOLVED') AS resolved_incident_count,
    COALESCE(
      SUM(
        IF(
          i.status = 'RESOLVED',
          TIMESTAMP_DIFF(i.resolved_at, i.opened_at, SECOND) / 60.0,
          NULL
        )
      ),
      0
    ) AS repair_minutes,
    COUNTIF(i.severity = 'CRITICAL') AS qualifying_failure_count,
    COUNTIF(
      i.status = 'OPEN'
      AND i.opened_at <= p.source_period_end
      AND (i.resolved_at IS NULL OR i.resolved_at > p.source_period_end)
    ) AS active_incidents
  FROM `{{ project_id }}.{{ dataset }}.fct_incidents` AS i
  JOIN telemetry_period AS p ON p.terminal_id = 'TM-001'
  GROUP BY p.terminal_id
),
alarm_metrics AS (
  SELECT
    p.terminal_id,
    COUNTIF(
      a.severity = 'CRITICAL'
      AND a.opened_at BETWEEN p.source_period_start AND p.source_period_end
    ) AS critical_alarms
  FROM `{{ project_id }}.{{ dataset }}.stg_alarms` AS a
  CROSS JOIN telemetry_period AS p
  GROUP BY p.terminal_id
)
SELECT
  p.terminal_id,
  p.source_period_start,
  p.source_period_end,
  p.available_intervals,
  p.scheduled_intervals,
  p.active_intervals,
  p.available_time_minutes,
  COALESCE(i.resolved_incident_count, 0) AS resolved_incident_count,
  COALESCE(i.repair_minutes, 0) AS repair_minutes,
  COALESCE(i.qualifying_failure_count, 0) AS qualifying_failure_count,
  p.scheduled_intervals * 5.0 / 60.0 AS operating_hours,
  COALESCE(m.throughput, 0) AS throughput,
  m.average_dwell_minutes,
  SAFE_DIVIDE(p.available_intervals, p.scheduled_intervals) AS availability,
  SAFE_DIVIDE(p.active_intervals, p.available_intervals) AS utilization,
  SAFE_DIVIDE(i.repair_minutes, i.resolved_incident_count) AS mttr_minutes,
  SAFE_DIVIDE(
    p.scheduled_intervals * 5.0 / 60.0,
    i.qualifying_failure_count
  ) AS mtbf_hours,
  COALESCE(i.active_incidents, 0) AS active_incidents,
  COALESCE(a.critical_alarms, 0) AS critical_alarms
FROM telemetry_period AS p
LEFT JOIN movement_metrics AS m ON m.terminal_id = p.terminal_id
LEFT JOIN incident_metrics AS i ON i.terminal_id = p.terminal_id
LEFT JOIN alarm_metrics AS a ON a.terminal_id = p.terminal_id
ORDER BY p.terminal_id;
