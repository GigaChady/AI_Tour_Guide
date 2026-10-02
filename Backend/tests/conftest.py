import os


import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.models.models import Base
from app.main import app
from app.core.database import get_db

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/test_db"
IS_E2E = os.getenv("E2E_TESTS") == "1"

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Drop and recreate all tables once per test session."""
    if IS_E2E:
        yield
        return

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def patch_startup():
    if IS_E2E:
        yield
        return

    with (
        patch("app.main.init_db", new=AsyncMock()),
        patch("app.main.init_redis", new=AsyncMock()),
        patch("app.main.close_redis", new=AsyncMock()),
        patch("app.main.AsyncSessionLocal", TestSessionLocal),
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
async def override_get_db(setup_database):
    if IS_E2E:
        yield
        return

    async def _get_test_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
