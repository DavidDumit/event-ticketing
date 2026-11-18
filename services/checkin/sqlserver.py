"""Thin SQL Server layer: connect with retries, and a small sqlite3-like wrapper.

The service code keeps writing conn.execute("... WHERE id = ?", (x,)) and
`with conn:` blocks; this wrapper turns ? into pymssql's %s and commits or
rolls back at the end of a `with` block.
"""
import logging
import os
import time
import urllib.parse

import pymssql

log = logging.getLogger(__name__)

IntegrityError = pymssql.IntegrityError  # UNIQUE / CHECK / FOREIGN KEY violations


def parse_url(url):
    """mssql+pymssql://user:password@host:1433/database -> pymssql.connect() arguments."""
    u = urllib.parse.urlsplit(url)
    if not u.scheme.startswith("mssql"):
        raise ValueError("DATABASE_URL must look like mssql+pymssql://user:password@host:1433/db")
    return {
        "server": u.hostname,
        "port": u.port or 1433,
        "user": urllib.parse.unquote(u.username or ""),
        "password": urllib.parse.unquote(u.password or ""),
        "database": u.path.lstrip("/"),
    }


class Connection:
    """A pymssql connection with a sqlite3-style execute() and `with` support."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        cur = self.raw.cursor()
        if params:
            cur.execute(sql.replace("?", "%s"), tuple(params))
        else:
            cur.execute(sql)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False  # never swallow the exception


def connect(url, attempts=None):
    """Connect, retrying with backoff while the database is starting or resuming.

    On Azure a serverless database that was paused takes up to about a minute to
    resume, and connections fail meanwhile (error 40613), so we wait and retry
    (1, 2, 4, 8, 15, 15... seconds) instead of crashing.
    """
    attempts = attempts or int(os.environ.get("DB_CONNECT_ATTEMPTS", "8"))
    params = parse_url(url)
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            raw = pymssql.connect(**params, login_timeout=15, timeout=30, autocommit=False)
            return Connection(raw)
        except pymssql.OperationalError as e:
            if attempt == attempts:
                raise
            log.warning("database not ready (attempt %d/%d): %s; retrying in %ss",
                        attempt, attempts, str(e).splitlines()[0], delay)
            time.sleep(delay)
            delay = min(delay * 2, 15)
