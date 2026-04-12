from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.buyer import Buyer
from app.services.auth import require_admin
from app.services.telegram_bot import _change_order_status as bot_change_status

router = APIRouter(prefix="/admin/orders", tags=["admin"])

VALID_STATUSES = {"new", "confirmed", "shipped", "delivered", "cancelled"}

STATUS_LABELS = {
    "new": "Новый", "confirmed": "Подтверждён",
    "shipped": "Отправлен", "delivered": "Доставлен", "cancelled": "Отменён",
}


# ─── Схемы ───────────────────────────────────────────────────────────────────

class OrderItemOut(BaseModel):
    id: int
    product_name: str
    size: str
    color: str
    qty: int
    unit_price: int

    class Config:
        from_attributes = True


class OrderListItem(BaseModel):
    id: int
    order_number: str
    status: str
    buyer_name: str
    buyer_phone: str
    total: int
    delivery_method: str
    payment_method: str
    notification_sent: bool
    created_at: str

    class Config:
        from_attributes = True


class OrderDetail(OrderListItem):
    subtotal: int
    discount_amount: int
    delivery_cost: int
    payment_status: str
    city: str
    address: str
    notes: str | None
    buyer_username: str | None = None
    items: list[OrderItemOut] = []


class StatusUpdate(BaseModel):
    status: str


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[OrderListItem])
async def list_orders(
    status: str | None = Query(None),
    search: str | None = Query(None),   # по имени/телефону/номеру
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Список заказов. Фильтры: ?status=new, ?search=Анна"""
    q = select(Order).order_by(Order.created_at.desc()).limit(100)

    if status and status in VALID_STATUSES:
        q = q.where(Order.status == status)

    if search:
        pattern = f"%{search}%"
        q = q.where(or_(
            Order.buyer_name.ilike(pattern),
            Order.buyer_phone.ilike(pattern),
            Order.order_number.ilike(pattern),
        ))

    result = await db.execute(q)
    orders = result.scalars().all()
    return [_order_list_item(o) for o in orders]


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # username покупателя
    buyer_username = None
    if order.buyer_id:
        buyer_result = await db.execute(select(Buyer).where(Buyer.id == order.buyer_id))
        buyer = buyer_result.scalar_one_or_none()
        if buyer:
            buyer_username = buyer.username

    return OrderDetail(
        **_order_list_item(order).model_dump(),
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        delivery_cost=order.delivery_cost,
        payment_status=order.payment_status,
        city=order.city,
        address=order.address,
        notes=order.notes,
        buyer_username=buyer_username,
        items=[
            OrderItemOut(
                id=i.id, product_name=i.product_name,
                size=i.size, color=i.color,
                qty=i.qty, unit_price=i.unit_price,
            )
            for i in order.items
        ],
    )


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Сменить статус → уведомить покупателя через бота."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Неверный статус. Допустимые: {', '.join(VALID_STATUSES)}",
        )

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    old_status = order.status
    order.status = body.status
    await db.commit()

    # Уведомляем покупателя (через логику из telegram_bot.py)
    if order.buyer_id:
        from app.models.buyer import Buyer
        from app.services.notifications import notify_buyer
        from app.services.telegram_bot import _buyer_status_message
        buyer_result = await db.execute(select(Buyer).where(Buyer.id == order.buyer_id))
        buyer = buyer_result.scalar_one_or_none()
        if buyer:
            msg = _buyer_status_message(order.order_number, body.status)
            if msg:
                await notify_buyer(buyer.telegram_id, msg)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "old_status": old_status,
        "new_status": body.status,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _order_list_item(o: Order) -> OrderListItem:
    return OrderListItem(
        id=o.id,
        order_number=o.order_number,
        status=o.status,
        buyer_name=o.buyer_name,
        buyer_phone=o.buyer_phone,
        total=o.total,
        delivery_method=o.delivery_method,
        payment_method=o.payment_method,
        notification_sent=o.notification_sent,
        created_at=o.created_at.strftime("%d.%m.%Y %H:%M"),
    )
