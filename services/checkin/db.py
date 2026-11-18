"""Per-request database connection for the check-in service (Flask side)."""
from flask import current_app, g

import sqlserver


def get_db():
    """One SQL Server connection per request, opened on first use."""
    if "db" not in g:
        g.db = sqlserver.connect(current_app.config["DATABASE_URL"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
