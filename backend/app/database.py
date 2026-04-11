from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Конвертируем postgresql:// → postgresql+asyncpg://
db_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    db_url,
    echo=settings.is_dev,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "ssl": True,
        "statement_cache_size": 0,  # обязательно для Supabase PgBouncer
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Зависимость FastAPI — открывает сессию на один запрос"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
