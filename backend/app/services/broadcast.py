"""
broadcast.py — фоновая рассылка покупателям.

Алгоритм:
1. Получаем всех активных покупателей (is_blocked=false, telegram_id known)
2. Обновляем broadcast.status = 'sending', total_recipients = N
3. Отправляем по одному с throttle 20 сообщ/сек (лимит Telegram 30/сек, запас)
4. Обработка ошибок:
   - Forbidden (заблокировал бота) → buyer.is_blocked = true, failed_count++
   - RetryAfter → asyncio.sleep(retry_after)
   - Другие ошибки → failed_count++
5. Обновляем broadcast.status = 'sent' / 'failed'
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from telegram import Bot
from telegram.error import Forbidden, RetryAfter, TelegramError

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.broadcast import Broadcast
from app.models.buyer import Buyer
from app.services.storage import storage as storage_service

logger = logging.getLogger(__name__)

THROTTLE_DELAY = 0.05   # 20 сообщ/сек (1 / 20 = 0.05)


def _get_bot() -> Bot | None:
    token = settings.bot_token if not settings.is_dev else (settings.bot_token_test or settings.bot_token)
    return Bot(token=token) if token else None


async def run_broadcast(broadcast_id: int) -> None:
    """
    Запускается как background task из POST /admin/broadcast.
    Использует отдельную сессию БД — не привязана к HTTP-запросу.
    """
    bot = _get_bot()
    if not bot:
        logger.error(f"[broadcast {broadcast_id}] Токен бота не задан — рассылка отменена")
        await _set_status(broadcast_id, "failed")
        return

    async with AsyncSessionLocal() as db:
        # Загружаем рассылку
        result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = result.scalar_one_or_none()
        if not broadcast or broadcast.status != "draft":
            logger.warning(f"[broadcast {broadcast_id}] Не найдена или не в статусе draft")
            return

        # Получаем активных покупателей
        buyers_result = await db.execute(
            select(Buyer)
            .where(Buyer.is_blocked == False)
            .where(Buyer.telegram_id != None)
            .order_by(Buyer.id)
        )
        buyers = buyers_result.scalars().all()

        if not buyers:
            broadcast.status = "sent"
            broadcast.total_recipients = 0
            broadcast.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"[broadcast {broadcast_id}] Нет получателей")
            return

        broadcast.status = "sending"
        broadcast.total_recipients = len(buyers)
        broadcast.started_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"[broadcast {broadcast_id}] Старт: {len(buyers)} получателей")

        # Готовим фото (если есть)
        photo_url = None
        if broadcast.storage_key:
            from app.models.product import ProductImage
            # Создаём временный объект для get_url_by_key
            photo_url = storage_service.get_url_by_key(
                broadcast.storage_key, broadcast.storage_provider
            )

        sent = 0
        failed = 0

        for buyer in buyers:
            try:
                if photo_url:
                    await bot.send_photo(
                        chat_id=buyer.telegram_id,
                        photo=photo_url,
                        caption=broadcast.text,
                    )
                else:
                    await bot.send_message(
                        chat_id=buyer.telegram_id,
                        text=broadcast.text,
                    )
                sent += 1
                await asyncio.sleep(THROTTLE_DELAY)

            except Forbidden:
                # Покупатель заблокировал бота — помечаем
                buyer.is_blocked = True
                failed += 1
                logger.info(f"[broadcast {broadcast_id}] buyer {buyer.id} заблокировал бота")

            except RetryAfter as e:
                # Telegram просит подождать
                wait = e.retry_after + 1
                logger.warning(f"[broadcast {broadcast_id}] RetryAfter {wait}s")
                await asyncio.sleep(wait)
                # Повторяем этого же покупателя
                try:
                    if photo_url:
                        await bot.send_photo(chat_id=buyer.telegram_id, photo=photo_url, caption=broadcast.text)
                    else:
                        await bot.send_message(chat_id=buyer.telegram_id, text=broadcast.text)
                    sent += 1
                except TelegramError:
                    failed += 1

            except TelegramError as e:
                failed += 1
                logger.error(f"[broadcast {broadcast_id}] buyer {buyer.id}: {e}")

            # Обновляем прогресс каждые 10 отправок
            if (sent + failed) % 10 == 0:
                broadcast.sent_count = sent
                broadcast.failed_count = failed
                await db.commit()

        # Финал
        broadcast.status = "sent"
        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.finished_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info(
        f"[broadcast {broadcast_id}] Завершено: "
        f"отправлено {sent}, не дошло {failed}"
    )


async def _set_status(broadcast_id: int, status: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        b = result.scalar_one_or_none()
        if b:
            b.status = status
            await db.commit()
