from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.buyer import Buyer
from app.models.order import Order
from app.services.auth import require_admin

router = APIRouter(prefix="/admin/buyers", tags=["admin"])


# ─── Схемы ───────────────────────────────────────────────────────────────────

class BuyerListItem(BaseModel):
    id: int
    telegram_id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    is_blocked: bool
    order_count: int
    total_spent: int
    created_at: str


class BuyerDetail(BuyerListItem):
    phone: str | None
    last_active_at: str
    orders: list[dict] = []


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[BuyerListItem])
async def list_buyers(
    search: str | None = Query(None),  # по имени или username
    blocked: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Список покупателей с количеством заказов и суммой покупок."""
    q = select(Buyer).order_by(Buyer.created_at.desc()).limit(200)

    if blocked is not None:
        q = q.where(Buyer.is_blocked == blocked)

    if search:
        pattern = f"%{search}%"
        from sqlalchemy import or_
        q = q.where(or_(
            Buyer.first_name.ilike(pattern),
            Buyer.username.ilike(pattern),
        ))

    result = await db.execute(q)
    buyers = result.scalars().all()

    # Подгружаем статистику по каждому покупателю
    items = []
    for b in buyers:
        stats = await db.execute(
            select(
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.total), 0).label("total"),
            ).where(Order.buyer_id == b.id)
        )
        row = stats.one()
        items.append(BuyerListItem(
            id=b.id,
            telegram_id=b.telegram_id,
            first_name=b.first_name,
            last_name=b.last_name,
            username=b.username,
            is_blocked=b.is_blocked,
            order_count=row.cnt,
            total_spent=row.total,
            created_at=b.created_at.strftime("%d.%m.%Y %H:%M"),
        ))
    return items


@router.get("/{buyer_id}", response_model=BuyerDetail)
async def get_buyer(
    buyer_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Профиль покупателя + история заказов."""
    result = await db.execute(select(Buyer).where(Buyer.id == buyer_id))
    buyer = result.scalar_one_or_none()
    if not buyer:
        raise HTTPException(status_code=404, detail="Покупатель не найден")

    # Статистика
    stats = await db.execute(
        select(
            func.count(Order.id).label("cnt"),
            func.coalesce(func.sum(Order.total), 0).label("total"),
        ).where(Order.buyer_id == buyer_id)
    )
    row = stats.one()

    # Последние 20 заказов
    orders_result = await db.execute(
        select(Order)
        .where(Order.buyer_id == buyer_id)
        .order_by(Order.created_at.desc())
        .limit(20)
    )
    orders = orders_result.scalars().all()

    return BuyerDetail(
        id=buyer.id,
        telegram_id=buyer.telegram_id,
        first_name=buyer.first_name,
        last_name=buyer.last_name,
        username=buyer.username,
        phone=buyer.phone,
        is_blocked=buyer.is_blocked,
        order_count=row.cnt,
        total_spent=row.total,
        created_at=buyer.created_at.strftime("%d.%m.%Y %H:%M"),
        last_active_at=buyer.last_active_at.strftime("%d.%m.%Y %H:%M"),
        orders=[
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "total": o.total,
                "created_at": o.created_at.strftime("%d.%m.%Y %H:%M"),
            }
            for o in orders
        ],
    )


@router.patch("/{buyer_id}/block")
async def toggle_block(
    buyer_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Заблокировать / разблокировать покупателя (переключение)."""
    result = await db.execute(select(Buyer).where(Buyer.id == buyer_id))
    buyer = result.scalar_one_or_none()
    if not buyer:
        raise HTTPException(status_code=404, detail="Покупатель не найден")

    buyer.is_blocked = not buyer.is_blocked
    await db.commit()
    return {"id": buyer.id, "is_blocked": buyer.is_blocked}
