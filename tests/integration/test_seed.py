import psycopg

from portflow.seed import SeedReport, seed_operational


def run_seed(database_url: str, *, seed: int) -> SeedReport:
    with psycopg.connect(database_url) as connection:
        return seed_operational(connection, seed=seed)


def test_seed_is_idempotent(database_url: str) -> None:
    first = run_seed(database_url, seed=42)
    second = run_seed(database_url, seed=42)

    assert first.row_counts == second.row_counts
    assert first.digest_sha256 == second.digest_sha256
    assert first.row_counts == {
        "terminals": 1,
        "equipment": 1,
        "telemetry_events": 288,
        "alarms": 3,
        "incidents": 2,
        "maintenance_orders": 2,
        "container_movements": 8,
    }


def test_seed_creates_connected_references(database_url: str) -> None:
    run_seed(database_url, seed=42)
    with psycopg.connect(database_url) as connection:
        orphan_count = connection.execute(
            """
            select count(*)
            from telemetry_events t
            left join equipment e on e.equipment_id = t.equipment_id
            left join terminals m on m.terminal_id = t.terminal_id
            where e.equipment_id is null or m.terminal_id is null
            """
        ).fetchone()[0]
    assert orphan_count == 0
