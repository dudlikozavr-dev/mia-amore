"""
POST /api/orders — оформление заказа из Mini App (требует Telegram initData).
POST /api/orders/web — оформление заказа с внешнего сайта (требует API ключ).

Алгоритм:
1. Валидация (initData или API ключ)
2. Upsert покупателя (если telegram_id передан, только для Mini App)
3. Создать Order + OrderItem[]  (notification_sent = false)
4. Ответить 201 немедленно
5. Background task: уведомить Дениса → при успехе notification_sent = true
6. Background task: уведомить покупателя (если telegram_id известен)
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.models.buyer import Buyer
from app.models.order import Order, OrderItem
from app.services.auth import require_init_data
from app.services.notifications import (
    notify_admin_new_order,
    notify_buyer_order_accepted,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["public"])

DELIVERY_COST = {"cdek": 300, "post": 250}
FREE_DELIVERY_THRESHOLD = 3000


# ─── Зависимость для проверки API ключа ────────────────────────────────────────

async def require_api_key(request: Request) -> str:
    """Проверяет API ключ в заголовке X-Api-Key."""
    api_key = request.headers.get("X-Api-Key", "")
    if not api_key or api_key != settings.admin_api_token:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ─── Схемы входящего запроса ──────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int | None = None
    product_name: str
    size: str
    color: str
    qty: int
    unit_price: int

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("qty должно быть >= 1")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("unit_price должно быть >= 1")
        return v


class OrderIn(BaseModel):
    # Покупатель
    buyer_telegram_id: int | None = None
    buyer_username: str | None = None

    # Форма доставки
    buyer_name: str
    buyer_phone: str
    city: str
    address: str
    notes: str | None = None

    # Способы
    delivery_method: str   # cdek | post
    payment_method: str    # cod | online

    # Позиции
    items: list[OrderItemIn]

    @field_validator("delivery_method")
    @classmethod
    def valid_delivery(cls, v: str) -> str:
        if v not in ("cdek", "post"):
            raise ValueError("delivery_method: cdek или post")
        return v

    @field_validator("payment_method")
    @classmethod
    def valid_payment(cls, v: str) -> str:
        if v not in ("cod", "online"):
            raise ValueError("payment_method: cod или online")
        return v

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("Корзина пуста")
        return v


# ─── Схема ответа ─────────────────────────────────────────────────────────────

class OrderOut(BaseModel):
    id: int
    order_number: str
    total: int
    status: str


# ─── Фоновые задачи ───────────────────────────────────────────────────────────

async def _send_notifications(order_id: int, order_data: dict) -> None:
    """
    Запускается после ответа 201.
    Уведомляет Дениса и покупателя.
    При успехе обновляет notification_sent = true.
    """
    success = await notify_admin_new_order(order_data)

    if success:
        # Открываем отдельную сессию — оригинальная уже закрыта
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order:
                order.notification_sent = True
                await db.commit()

    # Уведомляем покупателя (если знаем telegram_id)
    buyer_telegram_id = order_data.get("buyer_telegram_id")
    if buyer_telegram_id:
        await notify_buyer_order_accepted(
            buyer_telegram_id, order_data["order_number"]
        )


# ─── Эндпоинт ─────────────────────────────────────────────────────────────────

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_init_data),
):
    # 1. Upsert покупателя
    buyer_id: int | None = None
    if body.buyer_telegram_id:
        result = await db.execute(
            select(Buyer).where(Buyer.telegram_id == body.buyer_telegram_id)
        )
        buyer = result.scalar_one_or_none()

        if buyer:
            buyer.last_active_at = func.now()
        else:
            buyer = Buyer(
                telegram_id=body.buyer_telegram_id,
                username=body.buyer_username,
                first_name=body.buyer_name,
            )
            db.add(buyer)
            await db.flush()

        buyer_id = buyer.id

    # 2. Считаем суммы
    subtotal = sum(item.unit_price * item.qty for item in body.items)
    delivery_cost = 0 if subtotal >= FREE_DELIVERY_THRESHOLD else DELIVERY_COST.get(body.delivery_method, 300)
    total = subtotal + delivery_cost

    # 3. Создаём Order (notification_sent = false по умолчанию)
    order = Order(
        order_number="",          # заполним после flush
        buyer_id=buyer_id,
        status="new",
        subtotal=subtotal,
        delivery_cost=delivery_cost,
        total=total,
        delivery_method=body.delivery_method,
        payment_method=body.payment_method,
        buyer_name=body.buyer_name,
        buyer_phone=body.buyer_phone,
        city=body.city,
        address=body.address,
        notes=body.notes,
    )
    db.add(order)
    await db.flush()  # получаем order.id

    order.order_number = f"#{1000 + order.id}"

    # 4. Добавляем позиции
    for item in body.items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product_name,
            size=item.size,
            color=item.color,
            qty=item.qty,
            unit_price=item.unit_price,
        ))

    await db.flush()

    # 5. Данные для уведомлений (собираем до закрытия сессии)
    order_data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "buyer_name": body.buyer_name,
        "buyer_phone": body.buyer_phone,
        "buyer_username": body.buyer_username,
        "buyer_telegram_id": body.buyer_telegram_id,
        "city": body.city,
        "address": body.address,
        "notes": body.notes,
        "delivery_method": body.delivery_method,
        "total": total,
        "items": [
            {
                "product_name": i.product_name,
                "size": i.size,
                "color": i.color,
                "qty": i.qty,
            }
            for i in body.items
        ],
    }

    result = OrderOut(
        id=order.id,
        order_number=order.order_number,
        total=total,
        status="new",
    )

    # 6. Фоновая задача — запускается после ответа 201
    background_tasks.add_task(_send_notifications, order.id, order_data)

    return result


# ─── Эндпоинт для веб-сайтов (без Telegram auth) ────────────────────────────────

@router.post("/orders/web", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_web_order(
    body: OrderIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Создание заказа с внешнего сайта (например, sikretsweet.ru).
    Требует API ключ в заголовке X-Api-Key.

    Не требует Telegram initData, но может содержать buyer_telegram_id = null.
    """
    # 1. Upsert покупателя (только если передан telegram_id — маловероятно для веб)
    buyer_id: int | None = None
    if body.buyer_telegram_id:
        result = await db.execute(
            select(Buyer).where(Buyer.telegram_id == body.buyer_telegram_id)
        )
        buyer = result.scalar_one_or_none()

        if buyer:
            buyer.last_active_at = func.now()
        else:
            buyer = Buyer(
                telegram_id=body.buyer_telegram_id,
                username=body.buyer_username,
                first_name=body.buyer_name,
            )
            db.add(buyer)
            await db.flush()

        buyer_id = buyer.id

    # 2. Считаем суммы
    subtotal = sum(item.unit_price * item.qty for item in body.items)
    delivery_cost = 0 if subtotal >= FREE_DELIVERY_THRESHOLD else DELIVERY_COST.get(body.delivery_method, 300)
    total = subtotal + delivery_cost

    # 3. Создаём Order
    order = Order(
        order_number="",
        buyer_id=buyer_id,
        status="new",
        subtotal=subtotal,
        delivery_cost=delivery_cost,
        total=total,
        delivery_method=body.delivery_method,
        payment_method=body.payment_method,
        buyer_name=body.buyer_name,
        buyer_phone=body.buyer_phone,
        city=body.city,
        address=body.address,
        notes=body.notes,
    )
    db.add(order)
    await db.flush()

    order.order_number = f"#{1000 + order.id}"

    # 4. Добавляем позиции
    for item in body.items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product_name,
            size=item.size,
            color=item.color,
            qty=item.qty,
            unit_price=item.unit_price,
        ))

    await db.flush()

    # 5. Данные для уведомлений
    order_data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "buyer_name": body.buyer_name,
        "buyer_phone": body.buyer_phone,
        "buyer_username": body.buyer_username,
        "buyer_telegram_id": body.buyer_telegram_id,
        "city": body.city,
        "address": body.address,
        "notes": body.notes,
        "delivery_method": body.delivery_method,
        "total": total,
        "items": [
            {
                "product_name": i.product_name,
                "size": i.size,
                "color": i.color,
                "qty": i.qty,
            }
            for i in body.items
        ],
    }

    result = OrderOut(
        id=order.id,
        order_number=order.order_number,
        total=total,
        status="new",
    )

    # 6. Фоновая задача — уведомить админа
    background_tasks.add_task(_send_notifications, order.id, order_data)

    return result
