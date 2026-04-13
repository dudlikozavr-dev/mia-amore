"""
GET /admin/stats — базовая аналитика магазина.

Возвращает:
- Выручка за сегодня / неделю / месяц / всё время
- Количество заказов по статусам
- Топ-5 товаров по количеству продаж
- Количество покупателей
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.buyer import Buyer
from app.models.order import Order, OrderItem
from app.services.auth import require_admin

router = APIRouter(prefix="/admin/stats", tags=["admin"])


@router.get("")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # ── Выручка за периоды ───────────────────────────────────────────────────
    async def revenue(since: datetime) -> int:
        result = await db.execute(
            select(func.coalesce(func.sum(Order.total), 0))
            .where(Order.created_at >= since)
            .where(Order.status.notin_(["cancelled"]))
        )
        return result.scalar()

    revenue_today = await revenue(today_start)
    revenue_week = await revenue(week_start)
    revenue_month = await revenue(month_start)

    total_revenue = await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.status.notin_(["cancelled"]))
    )
    revenue_all = total_revenue.scalar()

    # ── Заказы по статусам ───────────────────────────────────────────────────
    statuses_result = await db.execute(
        select(Order.status, func.count(Order.id).label("cnt"))
        .group_by(Order.status)
    )
    orders_by_status = {row.status: row.cnt for row in statuses_result}

    total_orders = sum(orders_by_status.values())

    # ── Топ-5 товаров ────────────────────────────────────────────────────────
    top_result = await db.execute(
        select(
            OrderItem.product_name,
            func.sum(OrderItem.qty).label("total_qty"),
            func.sum(OrderItem.qty * OrderItem.unit_price).label("total_revenue"),
        )
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.qty).desc())
        .limit(5)
    )
    top_products = [
        {
            "product_name": row.product_name,
            "total_qty": row.total_qty,
            "total_revenue": row.total_revenue,
        }
        for row in top_result
    ]

    # ── Покупатели ───────────────────────────────────────────────────────────
    buyers_count = await db.execute(select(func.count(Buyer.id)))
    total_buyers = buyers_count.scalar()

    new_buyers_today = await db.execute(
        select(func.count(Buyer.id)).where(Buyer.created_at >= today_start)
    )
    buyers_today = new_buyers_today.scalar()

    return {
        "revenue": {
            "today": revenue_today,
            "week": revenue_week,
            "month": revenue_month,
            "all_time": revenue_all,
        },
        "orders": {
            "total": total_orders,
            "by_status": orders_by_status,
        },
        "top_products": top_products,
        "buyers": {
            "total": total_buyers,
            "new_today": buyers_today,
        },
    }
