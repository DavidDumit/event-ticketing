"""SQLite helpers for the check-in service. The schema lives in schema.sql."""
import os
import sqlite3

from flask import current_app, g

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    """Create the folder and tables if missing. Safe to run on every start."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    with open(SCHEMA_FILE) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def get_db():
    """One connection per request, opened on first use."""
    if "db" not in g:
        g.db = get_connection(current_app.config["DB_PATH"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
