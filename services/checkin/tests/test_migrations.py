import migrate


def test_second_run_applies_nothing(conn):
    # The session fixture already applied everything once
    assert migrate.apply_migrations(conn) == []


def test_every_migration_file_is_recorded(conn):
    import os

    files = sorted(f for f in os.listdir(migrate.MIGRATIONS_DIR) if f.endswith(".sql"))
    recorded = sorted(r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall())
    assert recorded == files


def test_rows_written_without_a_gate_get_main(conn):
    # Code from before migration 002 inserted check-ins without a gate column.
    # The column's DEFAULT must keep that working and give those rows 'main',
    # which is also what 002 gives to the rows that existed when it ran.
    with conn:
        conn.execute(
            "INSERT INTO check_ins (ticket_code, event_id, checked_in_at) VALUES (?, ?, ?)",
            ("OLD1", 1, "2026-11-20T18:00:00Z"),
        )
    assert conn.execute("SELECT gate FROM check_ins WHERE ticket_code = ?", ("OLD1",)).fetchone()[0] == "main"
