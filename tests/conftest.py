import os
import sqlite3

import pytest

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "schema.sql")


@pytest.fixture
def conn():
    """A fresh in-memory database with the real schema, one per test."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_FILE) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()
