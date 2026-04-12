"""
Тесты для GET /api/products и GET /api/products/{id}

Используем SQLite в памяти.

Проверяем:
- Пустой каталог → []
- Один товар → список из 1 элемента
- is_active=False → не попадает в список
- Фильтр по категории
- GET /api/products/{id} → 200 с полными данными
- GET /api/products/999 → 404
- GET /api/categories → список категорий
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.config import settings
from app.models.category import Category
from app.models.product import Product


# ─── Фикстуры ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine, monkeypatch):
    from main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(settings, "environment", "development")

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Вспомогательные функции ─────────────────────────────────────────────────

async def _add_category(session, name="Халаты", slug="robe"):
    cat = Category(name=name, slug=slug, sort_order=0, is_active=True)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


async def _add_product(session, category_id=None, is_active=True, price=1500):
    p = Product(
        name="Шёлковый халат",
        category_id=category_id,
        price=price,
        stock=10,
        is_active=is_active,
        sizes=["S", "M", "L"],
        disabled_sizes=[],
        colors=[{"name": "Бежевый", "hex": "#D4B896"}],
        sort_order=0,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


# ─── Тесты каталога ──────────────────────────────────────────────────────────

class TestGetProducts:
    @pytest.mark.asyncio
    async def test_empty_catalog(self, client):
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_active_product_appears(self, client, db_session):
        await _add_product(db_session)
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Шёлковый халат"

    @pytest.mark.asyncio
    async def test_inactive_product_hidden(self, client, db_session):
        await _add_product(db_session, is_active=False)
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client, db_session):
        cat = await _add_category(db_session, slug="robe")
        await _add_product(db_session, category_id=cat.id)
        await _add_product(db_session, category_id=None)  # без категории

        resp = await client.get("/api/products?category=robe")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_filter_all_returns_all(self, client, db_session):
        cat = await _add_category(db_session)
        await _add_product(db_session, category_id=cat.id)
        await _add_product(db_session)

        resp = await client.get("/api/products?category=all")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetProductDetail:
    @pytest.mark.asyncio
    async def test_existing_product(self, client, db_session):
        product = await _add_product(db_session)
        resp = await client.get(f"/api/products/{product.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == product.id
        assert data["name"] == "Шёлковый халат"
        assert data["sizes"] == ["S", "M", "L"]
        assert data["images"] == []

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        resp = await client.get("/api/products/999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_inactive_product_not_found(self, client, db_session):
        product = await _add_product(db_session, is_active=False)
        resp = await client.get(f"/api/products/{product.id}")
        assert resp.status_code == 404


class TestGetCategories:
    @pytest.mark.asyncio
    async def test_empty(self, client):
        resp = await client.get("/api/categories")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_active_category_appears(self, client, db_session):
        await _add_category(db_session, name="Халаты", slug="robe")
        resp = await client.get("/api/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert len(cats) == 1
        assert cats[0]["slug"] == "robe"

    @pytest.mark.asyncio
    async def test_inactive_category_hidden(self, client, db_session):
        cat = Category(name="Скрытая", slug="hidden", is_active=False, sort_order=0)
        db_session.add(cat)
        await db_session.commit()
        resp = await client.get("/api/categories")
        assert resp.json() == []
