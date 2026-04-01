"""
Pytest fixtures for Meruem backend tests.

Uses an in-memory SQLite database so tests run without a live Postgres instance.
pgvector-specific types are mocked out at the DB level via a simple BLOB column.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "sqlite:///./pytest-smoke.db"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


try:
    from pgvector.sqlalchemy import Vector

    @compiles(Vector, "sqlite")
    def compile_vector_sqlite(_type, _compiler, **_kwargs):
        return "BLOB"
except Exception:
    Vector = None


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    # SQLite doesn't have pgvector — patch Vector columns to TEXT
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    # Create all tables (Vector columns map to BLOB in SQLite)
    with eng.begin() as conn:
        Base.metadata.create_all(bind=eng)

    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def db(engine):
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
