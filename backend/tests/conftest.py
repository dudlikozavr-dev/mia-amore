"""
Общие фикстуры для тестов.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.config import settings


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """SQLite in-memory engine — отдельный для каждого теста."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Асинхронная сессия для прямых операций с БД в тестах."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine, monkeypatch):
    """
    HTTP-клиент с переопределёнными зависимостями:
    - get_db → SQLite in-memory
    - settings.environment = 'development' (пропуск initData)
    """
    from httpx import AsyncClient, ASGITransport
    from main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "bot_token", "")

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
