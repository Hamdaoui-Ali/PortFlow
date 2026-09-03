select *
from {{ ref('stg_telemetry_events') }}
