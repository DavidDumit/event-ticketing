"""Versioned migrations: apply migrations/NNN_name.sql once each, in order, on startup.

Applied versions are recorded in schema_migrations, so a second start applies
nothing. Each migration runs in its own transaction: if it fails, it is rolled
back and the service does not start. Applied files are never edited; a change
goes in a new, higher-numbered file.
"""
import logging
import os
import re

log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)  # batch separator, like sqlcmd


def apply_migrations(conn, directory=MIGRATIONS_DIR):
    """Apply every migration not yet recorded. Returns the names applied this time."""
    conn.execute(
        "IF OBJECT_ID('schema_migrations') IS NULL "
        "CREATE TABLE schema_migrations ("
        " version NVARCHAR(255) NOT NULL PRIMARY KEY,"
        " applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME())"
    )
    conn.commit()

    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    pending = sorted(f for f in os.listdir(directory) if f.endswith(".sql") and f not in applied)

    for name in pending:
        with open(os.path.join(directory, name)) as f:
            sql = f.read()
        try:
            for batch in _GO.split(sql):
                if batch.strip():
                    conn.execute(batch)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (name,))
            conn.commit()
        except Exception:
            conn.rollback()
            log.error("migration %s failed and was rolled back", name)
            raise
        log.info("applied migration %s", name)

    if not pending:
        log.info("migrations up to date (%d already applied)", len(applied))
    return pending
