"""
Тесты для POST /api/orders

Используем SQLite в памяти (aiosqlite) — не нужен реальный Postgres.
initData проверка отключена через мок settings.is_dev = True.

Проверяем:
- Успешный заказ → 201 + корректный order_number
- Пустая корзина → 422
- Неверный delivery_method → 422
- Расчёт стоимости: subtotal >= 3000 → доставка 0
- Расчёт стоимости: subtotal < 3000 → доставка 300/250
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.config import settings


# ─── Фикстуры ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # SQLite не поддерживает ARRAY/JSONB — пропускаем postgres-специфичные типы
        # через create_all с checkfirst
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine, monkeypatch):
    """
    TestClient с подменённой зависимостью get_db + is_dev=True (пропуск initData).
    """
    from main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    # Отключаем проверку initData
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "bot_token", "")

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Данные ───────────────────────────────────────────────────────────────────

VALID_ORDER = {
    "buyer_name": "Анна Иванова",
    "buyer_phone": "+79001234567",
    "city": "Москва",
    "address": "ул. Ленина, 1",
    "delivery_method": "cdek",
    "payment_method": "cod",
    "items": [
        {
            "product_name": "Шёлковый халат",
            "size": "M",
            "color": "Бежевый",
            "qty": 1,
            "unit_price": 2500,
        }
    ],
}


# ─── Тесты ────────────────────────────────────────────────────────────────────

class TestCreateOrder:
    @pytest.mark.asyncio
    async def test_success_returns_201(self, client):
        resp = await client.post("/api/orders", json=VALID_ORDER)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "new"
        assert data["order_number"].startswith("#")

    @pytest.mark.asyncio
    async def test_order_number_format(self, client):
        resp = await client.post("/api/orders", json=VALID_ORDER)
        assert resp.status_code == 201
        # order_number = #(1000 + id), id >= 1, значит >= #1001
        number = int(resp.json()["order_number"].lstrip("#"))
        assert number >= 1001

    @pytest.mark.asyncio
    async def test_empty_items_returns_422(self, client):
        order = {**VALID_ORDER, "items": []}
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_delivery_method_returns_422(self, client):
        order = {**VALID_ORDER, "delivery_method": "dhl"}
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_payment_method_returns_422(self, client):
        order = {**VALID_ORDER, "payment_method": "crypto"}
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_qty_zero_returns_422(self, client):
        order = {**VALID_ORDER, "items": [{**VALID_ORDER["items"][0], "qty": 0}]}
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_free_delivery_above_threshold(self, client):
        """subtotal >= 3000 → delivery_cost = 0"""
        order = {
            **VALID_ORDER,
            "items": [
                {
                    "product_name": "Дорогой халат",
                    "size": "L",
                    "color": "Белый",
                    "qty": 1,
                    "unit_price": 3500,
                }
            ],
        }
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 201
        assert resp.json()["total"] == 3500  # delivery = 0

    @pytest.mark.asyncio
    async def test_cdek_delivery_cost(self, client):
        """subtotal < 3000, cdek → delivery = 300"""
        resp = await client.post("/api/orders", json=VALID_ORDER)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 2500 + 300  # subtotal + cdek

    @pytest.mark.asyncio
    async def test_post_delivery_cost(self, client):
        """subtotal < 3000, post → delivery = 250"""
        order = {**VALID_ORDER, "delivery_method": "post"}
        resp = await client.post("/api/orders", json=order)
        assert resp.status_code == 201
        assert resp.json()["total"] == 2500 + 250
