"""SQLite helpers. The schema itself lives in schema.sql."""
import os
import sqlite3

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite has FKs off by default
    return conn


def init_db(db_path):
    """Create the folder and tables if missing. Safe to run on every start."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    with open(SCHEMA_FILE) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
