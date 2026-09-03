create table if not exists schema_migrations (
    filename text primary key,
    checksum_sha256 char(64) not null,
    applied_at timestamptz not null
);

create table if not exists terminals (
    terminal_id text primary key check (terminal_id ~ '^TM-[0-9]{3}$'),
    name text not null check (length(trim(name)) > 0),
    timezone_name text not null default 'UTC',
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create table if not exists equipment (
    equipment_id text primary key check (equipment_id ~ '^[A-Z]{2,4}-[0-9]{3}$'),
    terminal_id text not null references terminals(terminal_id),
    equipment_type text not null check (equipment_type in ('QUAY_CRANE', 'RTG', 'REACH_STACKER')),
    commissioning_date date not null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create table if not exists telemetry_events (
    event_id text primary key check (event_id ~ '^evt-[0-9]{6}-[0-9]{6}$'),
    schema_version smallint not null default 1 check (schema_version = 1),
    equipment_id text not null references equipment(equipment_id),
    terminal_id text not null references terminals(terminal_id),
    event_timestamp timestamptz not null,
    ingestion_timestamp timestamptz not null,
    state text not null check (state in ('IDLE', 'ACTIVE', 'WARNING', 'UNAVAILABLE', 'MAINTENANCE')),
    available boolean not null,
    load_percent numeric(5,2) not null check (load_percent between 0 and 100),
    temperature_c numeric(6,2) not null check (temperature_c between -20 and 150),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (ingestion_timestamp >= event_timestamp),
    check (updated_at >= created_at),
    check ((state in ('UNAVAILABLE', 'MAINTENANCE')) = (not available))
);

create table if not exists alarms (
    alarm_id text primary key check (alarm_id ~ '^alm-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    severity text not null check (severity in ('INFO', 'WARNING', 'CRITICAL')),
    code text not null check (length(trim(code)) > 0),
    opened_at timestamptz not null,
    cleared_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (cleared_at is null or cleared_at >= opened_at),
    check (updated_at >= created_at)
);

create table if not exists incidents (
    incident_id text primary key check (incident_id ~ '^inc-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    severity text not null check (severity in ('MINOR', 'MAJOR', 'CRITICAL')),
    status text not null check (status in ('OPEN', 'RESOLVED')),
    opened_at timestamptz not null,
    resolved_at timestamptz,
    root_cause text not null check (length(trim(root_cause)) > 0),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (resolved_at is null or resolved_at >= opened_at),
    check ((status = 'RESOLVED') = (resolved_at is not null)),
    check (updated_at >= created_at)
);

create table if not exists maintenance_orders (
    maintenance_order_id text primary key check (maintenance_order_id ~ '^mnt-[0-9]{6}$'),
    equipment_id text not null references equipment(equipment_id),
    status text not null check (status in ('PLANNED', 'IN_PROGRESS', 'COMPLETED')),
    started_at timestamptz not null,
    completed_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (completed_at is null or completed_at >= started_at),
    check ((status = 'COMPLETED') = (completed_at is not null)),
    check (updated_at >= created_at)
);

create table if not exists container_movements (
    movement_id text primary key check (movement_id ~ '^mov-[0-9]{6}$'),
    terminal_id text not null references terminals(terminal_id),
    equipment_id text not null references equipment(equipment_id),
    movement_type text not null check (movement_type in ('GATE_IN', 'GATE_OUT', 'LOAD', 'DISCHARGE')),
    container_ref text not null check (length(trim(container_ref)) > 0),
    event_timestamp timestamptz not null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (updated_at >= created_at)
);

create index if not exists idx_equipment_updated_cursor
    on equipment (updated_at, equipment_id);
create index if not exists idx_telemetry_updated_cursor
    on telemetry_events (updated_at, event_id);
create index if not exists idx_alarms_updated_cursor
    on alarms (updated_at, alarm_id);
create index if not exists idx_incidents_updated_cursor
    on incidents (updated_at, incident_id);
create index if not exists idx_maintenance_updated_cursor
    on maintenance_orders (updated_at, maintenance_order_id);
create index if not exists idx_movements_updated_cursor
    on container_movements (updated_at, movement_id);
