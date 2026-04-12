"""Pytest configuration and shared fixtures.

Environment variables MUST be set before any app module is imported so that
pydantic-settings picks them up at Settings() instantiation time.
"""

import os

# ---------------------------------------------------------------------------
# Override settings BEFORE importing anything from the app package.
# os.environ takes precedence over .env file values in pydantic-settings.
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("SWEETBOOK_API_KEY", "test-sweetbook-key")
os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # always use test DB

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models.base import Base

# ---------------------------------------------------------------------------
# Test database engine — points to test.db, separate from storybook.db
# ---------------------------------------------------------------------------
_TEST_DATABASE_URL = "sqlite:///./test.db"

_engine = create_engine(
    _TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    """Dependency override that yields a session backed by the test database."""
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# Session-scoped fixture: create all tables once, drop them when the suite ends
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


# ---------------------------------------------------------------------------
# Function-scoped fixture: truncate every table after each test for isolation.
# The route commits its own transaction, so rollback-based isolation won't
# work here — explicit DELETE is the reliable approach with SQLite.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _truncate_tables(_create_test_tables):
    yield
    with _TestingSessionLocal() as session:
        # Reverse topological order respects FK dependencies.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


# ---------------------------------------------------------------------------
# Reusable TestClient fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
