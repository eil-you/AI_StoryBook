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
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-not-production")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")
os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # always use test DB

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.models.base import Base

# ---------------------------------------------------------------------------
# Async engine for runtime DB operations (mirrors the real app setup)
# ---------------------------------------------------------------------------
_TEST_ASYNC_URL = "sqlite+aiosqlite:///./test.db"
_TEST_SYNC_URL = "sqlite:///./test.db"

_async_engine = create_async_engine(_TEST_ASYNC_URL)
_AsyncTestingSession = async_sessionmaker(_async_engine, expire_on_commit=False)

# Sync engine is only used for table creation/deletion (session-scoped fixtures
# cannot easily be async, so we use the sync API for setup/teardown only).
_sync_engine = create_engine(_TEST_SYNC_URL, connect_args={"check_same_thread": False})


async def _override_get_db():
    async with _AsyncTestingSession() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# Session-scoped fixture: create all tables once, drop them when the suite ends
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    Base.metadata.create_all(bind=_sync_engine)
    yield
    Base.metadata.drop_all(bind=_sync_engine)


# ---------------------------------------------------------------------------
# Function-scoped fixture: truncate every table after each test for isolation.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
async def _truncate_tables(_create_test_tables):
    yield
    async with _AsyncTestingSession() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


# ---------------------------------------------------------------------------
# Reusable TestClient fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers shared across test modules
# ---------------------------------------------------------------------------
_TEST_EMAIL = "test@example.com"
_TEST_PASSWORD = "testpassword123"


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    """회원가입된 유저 정보를 반환합니다."""
    resp = client.post("/auth/register", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict) -> dict:
    """로그인 후 Authorization 헤더를 반환합니다."""
    resp = client.post("/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
