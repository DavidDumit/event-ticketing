"""Tests run against a real SQL Server test database (never Azure SQL).

Set TEST_DATABASE_URL, e.g. locally with compose running:
  TEST_DATABASE_URL=mssql+pymssql://sa:<MSSQL_SA_PASSWORD>@localhost:1433/tickets_test
In CI it points at a throwaway SQL Server container.
"""
import os

import pytest

import migrate
import sqlserver

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
TABLES = ["tickets", "events"]  # children first, because tickets references events


@pytest.fixture(scope="session")
def database():
    """Apply the real migrations to the test database once per test run."""
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL is not set (see README: Tests)")
    conn = sqlserver.connect(TEST_URL)
    migrate.apply_migrations(conn)
    conn.close()
    return TEST_URL


@pytest.fixture
def conn(database):
    """A connection to an emptied test database, one per test."""
    conn = sqlserver.connect(database)
    for table in TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()
