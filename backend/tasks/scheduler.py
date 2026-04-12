"""
APScheduler — фоновые задачи, запускаемые по расписанию.

Задача 1: retry_pending_notifications
  Каждые 5 минут ищет заказы с notification_sent = false
  и повторно пробует уведомить Дениса.
  Охватывает заказы не старше 24 часов.

Запуск: scheduler.start() в lifespan FastAPI.
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.order import Order
from app.services.notifications import notify_admin_new_order

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def retry_pending_notifications() -> None:
    """
    Ищет заказы где notification_sent = false, созданные не более 24 часов назад,
    и повторяет отправку уведомления Денису.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .where(Order.notification_sent == False)
            .where(Order.created_at > cutoff)
            .order_by(Order.created_at)
            .limit(20)  # не более 20 за раз — не блокируем бота
        )
        pending_orders = result.scalars().all()

        if not pending_orders:
            return

        logger.info(f"[scheduler] Retry уведомлений: {len(pending_orders)} заказ(ов)")

        for order in pending_orders:
            # Загружаем позиции
            from app.models.order import OrderItem
            items_result = await db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            items = items_result.scalars().all()

            # Загружаем покупателя (если есть)
            buyer_username = None
            buyer_telegram_id = None
            if order.buyer_id:
                from app.models.buyer import Buyer
                buyer_result = await db.execute(
                    select(Buyer).where(Buyer.id == order.buyer_id)
                )
                buyer = buyer_result.scalar_one_or_none()
                if buyer:
                    buyer_username = buyer.username
                    buyer_telegram_id = buyer.telegram_id

            order_data = {
                "order_id": order.id,
                "order_number": order.order_number,
                "buyer_name": order.buyer_name,
                "buyer_phone": order.buyer_phone,
                "buyer_username": buyer_username,
                "buyer_telegram_id": buyer_telegram_id,
                "city": order.city,
                "address": order.address,
                "notes": order.notes,
                "delivery_method": order.delivery_method,
                "total": order.total,
                "items": [
                    {
                        "product_name": i.product_name,
                        "size": i.size,
                        "color": i.color,
                        "qty": i.qty,
                    }
                    for i in items
                ],
            }

            success = await notify_admin_new_order(order_data)
            if success:
                order.notification_sent = True
                logger.info(f"[scheduler] Заказ {order.order_number} — уведомление доставлено")
            else:
                logger.warning(f"[scheduler] Заказ {order.order_number} — retry не удался")

        await db.commit()


def setup_scheduler() -> AsyncIOScheduler:
    """Регистрирует все задачи и возвращает готовый scheduler."""
    scheduler.add_job(
        retry_pending_notifications,
        trigger="interval",
        minutes=5,
        id="retry_notifications",
        replace_existing=True,
        max_instances=1,          # одновременно только один запуск
        misfire_grace_time=60,    # пропустить если опоздал более чем на 60 сек
    )
    return scheduler
