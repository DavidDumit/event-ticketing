import migrate


def test_second_run_applies_nothing(conn):
    # The session fixture already applied everything once
    assert migrate.apply_migrations(conn) == []


def test_every_migration_file_is_recorded(conn):
    import os

    files = sorted(f for f in os.listdir(migrate.MIGRATIONS_DIR) if f.endswith(".sql"))
    recorded = sorted(r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall())
    assert recorded == files
