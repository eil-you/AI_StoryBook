from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base


def _make_engine():
    settings = get_settings()
    # sqlite:///./storybook.db  →  sqlite+aiosqlite:///./storybook.db
    url = settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return create_async_engine(url, echo=False)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """앱 시작 시 테이블을 생성하고 누락된 컬럼을 추가합니다."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 기존 DB에 cover_published 컬럼이 없으면 추가 (SQLite ALTER TABLE)
        result = await conn.execute(text("PRAGMA table_info(books)"))
        columns = {row[1] for row in result.fetchall()}
        if "cover_published" not in columns:
            await conn.execute(
                text("ALTER TABLE books ADD COLUMN cover_published BOOLEAN NOT NULL DEFAULT 0")
            )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
