import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database import get_db
from app.models.buyer import Buyer
from app.models.order import Order, OrderItem
from app.services.auth import require_init_data

router = APIRouter(prefix="/api", tags=["public"])


class BuyerIn(BaseModel):
    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class BuyerOut(BaseModel):
    id: int
    telegram_id: int
    first_name: str | None
    username: str | None

    class Config:
        from_attributes = True


@router.post("/buyers/identify", response_model=BuyerOut)
async def identify_buyer(
    body: BuyerIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_init_data),
):
    """
    Регистрирует покупателя при первом открытии Mini App
    или обновляет last_active_at при повторном.
    Upsert по telegram_id.
    """
    result = await db.execute(
        select(Buyer).where(Buyer.telegram_id == body.telegram_id)
    )
    buyer = result.scalar_one_or_none()

    if buyer:
        # Обновляем данные и время активности
        buyer.first_name = body.first_name
        buyer.last_name = body.last_name
        buyer.username = body.username
        buyer.last_active_at = func.now()
    else:
        buyer = Buyer(
            telegram_id=body.telegram_id,
            first_name=body.first_name,
            last_name=body.last_name,
            username=body.username,
        )
        db.add(buyer)

    await db.flush()
    await db.refresh(buyer)
    return buyer


# ─── История заказов покупателя ───────────────────────────────────────────────

class OrderItemOut(BaseModel):
    product_name: str
    size: str
    color: str
    qty: int
    unit_price: int

    class Config:
        from_attributes = True


class MyOrderOut(BaseModel):
    order_number: str
    status: str
    total: int
    created_at: datetime
    items: list[OrderItemOut]

    class Config:
        from_attributes = True


@router.get("/buyers/{telegram_id}/orders", response_model=list[MyOrderOut])
async def get_my_orders(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
    init_data: dict = Depends(require_init_data),
):
    """История заказов покупателя по telegram_id.

    Запрашивать можно только свои заказы: telegram_id в URL должен
    совпадать с id из проверенной initData. В dev-режиме initData
    может быть пустым — тогда проверка пропускается.
    """
    user_json = init_data.get("user") if init_data else None
    if user_json:
        try:
            user_id = json.loads(user_json).get("id")
        except (ValueError, TypeError):
            user_id = None
        if user_id != telegram_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно запрашивать только свои заказы",
            )

    result = await db.execute(
        select(Buyer).where(Buyer.telegram_id == telegram_id)
    )
    buyer = result.scalar_one_or_none()
    if not buyer:
        return []

    result = await db.execute(
        select(Order)
        .where(Order.buyer_id == buyer.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(20)
    )
    orders = result.scalars().all()
    return orders
