import migrate


def test_second_run_applies_nothing(conn):
    # The session fixture already applied everything once
    assert migrate.apply_migrations(conn) == []


def test_every_migration_file_is_recorded(conn):
    import os

    files = sorted(f for f in os.listdir(migrate.MIGRATIONS_DIR) if f.endswith(".sql"))
    recorded = sorted(r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall())
    assert recorded == files


def test_events_written_without_a_limit_get_two(conn):
    # Code from before migration 003 inserted events without max_tickets_per_email.
    # The DEFAULT keeps that working and gives them 2, which is also what 003 gave
    # the events that already existed when it ran.
    with conn:
        conn.execute(
            "INSERT INTO events (name, venue, starts_at, capacity, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Old event", "Hall", "2026-12-01T20:00:00Z", 10, "2026-11-20T18:00:00Z"),
        )
    row = conn.execute("SELECT max_tickets_per_email FROM events WHERE name = ?", ("Old event",)).fetchone()
    assert row[0] == 2
