import os
import sqlite3

import pytest

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "schema.sql")


@pytest.fixture
def conn():
    """A fresh in-memory database with this service's schema, one per test."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_FILE) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real Flask app with an empty database in a temp folder."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()
