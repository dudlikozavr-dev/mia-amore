import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Конвертируем postgresql:// → postgresql+asyncpg://
db_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

# SSL без проверки сертификата (Supabase использует self-signed CA)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    db_url,
    echo=settings.is_dev,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": ssl_ctx},
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
