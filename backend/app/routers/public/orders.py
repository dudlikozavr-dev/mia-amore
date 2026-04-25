"""
POST /api/orders        — оформление заказа из Mini App (требует Telegram initData).
POST /api/orders/invoice — создать заказ + вернуть ссылку на Telegram Invoice (ЮКасса).
POST /api/orders/web    — оформление заказа с внешнего сайта (требует API ключ).

/api/orders / /api/orders/web:
  1. Валидация  2. Upsert покупателя  3. Сохранить Order + OrderItem[]
  4. Ответить 201  5. Background task: уведомить Дениса + покупателя

/api/orders/invoice:
  1. Валидация  2. Upsert покупателя  3. Flush Order (получаем ID)
  4. createInvoiceLink (ЮКасса) — если упало, get_db делает rollback, заказ не создаётся
  5. Commit  6. Ответить 201 с invoice_link
  После оплаты Telegram шлёт successful_payment в webhook → статус меняется на paid.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import LabeledPrice
from telegram.error import TelegramError

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.models.buyer import Buyer
from app.models.order import Order, OrderItem
from app.services.auth import require_init_data
from app.services.notifications import (
    _get_bot,
    notify_admin_new_order,
    notify_buyer_order_accepted,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["public"])

DELIVERY_COST = {"cdek": 300, "post": 250}
FREE_DELIVERY_THRESHOLD = 3000
DELIVERY_LABELS = {"cdek": "СДЭК", "post": "Почта России"}


# ─── Схемы входящего запроса ──────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int | None = None
    product_name: str
    size: str | None = None
    color: str | None = None
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
    buyer_telegram_id: int | None = None
    buyer_username: str | None = None

    buyer_name: str
    buyer_phone: str
    city: str
    address: str
    notes: str | None = None

    delivery_method: str   # cdek | post
    payment_method: str    # cod | online

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


# ─── Схемы ответа ─────────────────────────────────────────────────────────────

class OrderOut(BaseModel):
    id: int
    order_number: str
    total: int
    status: str


class InvoiceOut(BaseModel):
    id: int
    order_number: str
    total: int
    invoice_link: str


# ─── Зависимость для проверки API ключа ───────────────────────────────────────

async def require_api_key(request: Request) -> str:
    api_key = request.headers.get("X-Api-Key", "")
    if not api_key or api_key != settings.admin_api_token:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _upsert_buyer(
    db: AsyncSession,
    telegram_id: int | None,
    username: str | None,
    name: str,
) -> int | None:
    if not telegram_id:
        return None
    result = await db.execute(select(Buyer).where(Buyer.telegram_id == telegram_id))
    buyer = result.scalar_one_or_none()
    if buyer:
        buyer.last_active_at = func.now()
    else:
        buyer = Buyer(telegram_id=telegram_id, username=username, first_name=name)
        db.add(buyer)
        await db.flush()
    return buyer.id


def _calculate_totals(items: list[OrderItemIn], delivery_method: str) -> tuple[int, int, int]:
    subtotal = sum(i.unit_price * i.qty for i in items)
    delivery_cost = 0 if subtotal >= FREE_DELIVERY_THRESHOLD else DELIVERY_COST.get(delivery_method, 300)
    return subtotal, delivery_cost, subtotal + delivery_cost


async def _persist_order(
    db: AsyncSession,
    body: OrderIn,
    buyer_id: int | None,
    subtotal: int,
    delivery_cost: int,
    total: int,
    *,
    status: str = "new",
) -> Order:
    order = Order(
        order_number="",
        buyer_id=buyer_id,
        status=status,
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
    return order


def _build_order_data(order: Order, body: OrderIn) -> dict:
    return {
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
        "total": order.total,
        "items": [
            {"product_name": i.product_name, "size": i.size, "color": i.color, "qty": i.qty}
            for i in body.items
        ],
    }


# ─── Фоновые задачи ───────────────────────────────────────────────────────────

async def _send_notifications(order_id: int, order_data: dict) -> None:
    success = await notify_admin_new_order(order_data)

    if success:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order:
                order.notification_sent = True
                await db.commit()

    buyer_telegram_id = order_data.get("buyer_telegram_id")
    if buyer_telegram_id:
        await notify_buyer_order_accepted(buyer_telegram_id, order_data["order_number"])


# ─── Эндпоинт: оформление заказа из Mini App ─────────────────────────────────

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_init_data),
):
    buyer_id = await _upsert_buyer(db, body.buyer_telegram_id, body.buyer_username, body.buyer_name)
    subtotal, delivery_cost, total = _calculate_totals(body.items, body.delivery_method)
    order = await _persist_order(db, body, buyer_id, subtotal, delivery_cost, total)
    order_data = _build_order_data(order, body)
    background_tasks.add_task(_send_notifications, order.id, order_data)
    return OrderOut(id=order.id, order_number=order.order_number, total=total, status="new")


# ─── Эндпоинт: создать заказ + Telegram Invoice (ЮКасса) ─────────────────────

@router.post("/orders/invoice", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_order_invoice(
    body: OrderIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_init_data),
):
    if not settings.payment_provider_token:
        raise HTTPException(status_code=503, detail="Оплата временно недоступна")

    buyer_id = await _upsert_buyer(db, body.buyer_telegram_id, body.buyer_username, body.buyer_name)
    subtotal, delivery_cost, total = _calculate_totals(body.items, body.delivery_method)

    # Flush order first to get the ID needed for the invoice payload.
    # get_db rolls back automatically if create_invoice_link raises below.
    order = await _persist_order(
        db, body, buyer_id, subtotal, delivery_cost, total, status="pending_payment"
    )

    prices = [LabeledPrice("Товары", subtotal * 100)]
    if delivery_cost > 0:
        prices.append(LabeledPrice(f"Доставка ({DELIVERY_LABELS.get(body.delivery_method, '')})", delivery_cost * 100))

    items_desc = ", ".join(f"{i.product_name} ×{i.qty}" for i in body.items)[:255]

    bot = _get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Бот не настроен")

    try:
        invoice_link = await bot.create_invoice_link(
            title="Mia-Amore",
            description=items_desc,
            payload=str(order.id),
            provider_token=settings.payment_provider_token,
            currency="RUB",
            prices=prices,
        )
    except TelegramError as e:
        logger.error(f"create_invoice_link error: {e}")
        raise HTTPException(status_code=502, detail=f"Telegram: {e}")

    # get_db commits on successful return
    return InvoiceOut(id=order.id, order_number=order.order_number, total=total, invoice_link=invoice_link)


# ─── Эндпоинт для веб-сайтов (без Telegram auth) ─────────────────────────────

@router.post("/orders/web", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_web_order(
    body: OrderIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    buyer_id = await _upsert_buyer(db, body.buyer_telegram_id, body.buyer_username, body.buyer_name)
    subtotal, delivery_cost, total = _calculate_totals(body.items, body.delivery_method)
    order = await _persist_order(db, body, buyer_id, subtotal, delivery_cost, total)
    order_data = _build_order_data(order, body)
    background_tasks.add_task(_send_notifications, order.id, order_data)
    return OrderOut(id=order.id, order_number=order.order_number, total=total, status="new")
