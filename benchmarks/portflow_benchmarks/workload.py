"""Engine-neutral benchmark workload definitions."""


TELEMETRY_SUMMARY_WORKLOAD = """
SELECT
  terminal_id,
  state,
  COUNT(*) AS event_count,
  SUM(CASE WHEN available THEN 1 ELSE 0 END) AS available_event_count,
  ROUND(AVG(load_percent), 6) AS average_load_percent,
  ROUND(AVG(temperature_c), 6) AS average_temperature_c
FROM telemetry_fixture
WHERE event_timestamp >= ?
  AND event_timestamp < ?
GROUP BY terminal_id, state
ORDER BY terminal_id, state
"""
