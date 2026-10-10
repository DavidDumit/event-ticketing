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


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The real Flask app with an empty database in a temp folder (never data/app.db)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import create_app  # imported here so DATA_DIR is set before create_app() reads it

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
