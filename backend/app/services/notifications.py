"""
Уведомления через Telegram-бота.

Два сценария:
1. Уведомление Дениса о новом заказе — вызывается как background task.
   Если упало: notification_sent остаётся false → APScheduler пробует снова.
2. Уведомление покупателя о принятом/изменённом заказе.
"""
import asyncio
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

from app.config import settings

logger = logging.getLogger(__name__)


def _get_bot() -> Bot | None:
    token = settings.bot_token if not settings.is_dev else (settings.bot_token_test or settings.bot_token)
    if not token:
        return None
    if settings.telegram_proxy_url:
        return Bot(token=token, request=HTTPXRequest(proxy=settings.telegram_proxy_url))
    return Bot(token=token)


def _build_order_message(order_data: dict) -> str:
    """Формирует текст уведомления о новом заказе для Дениса."""
    items_text = "\n".join(
        f"• {item['product_name']} {item['size']}, {item['color']} ×{item['qty']}"
        for item in order_data["items"]
    )

    delivery_labels = {"cdek": "СДЭК", "post": "Почта России"}
    delivery = delivery_labels.get(order_data["delivery_method"], order_data["delivery_method"])

    return (
        f"🛍 Новый заказ {order_data['order_number']}\n"
        f"Покупатель: {order_data['buyer_name']}"
        + (f" (@{order_data['buyer_username']})" if order_data.get("buyer_username") else "")
        + f"\n\n{items_text}\n\n"
        f"Итого: {order_data['total']:,} ₽\n"
        f"Доставка: {delivery}\n"
        f"Адрес: {order_data['city']}, {order_data['address']}\n"
        f"Тел: {order_data['buyer_phone']}"
        + (f"\nКомментарий: {order_data['notes']}" if order_data.get("notes") else "")
    )


async def notify_admin_new_order(order_data: dict) -> bool:
    """
    Отправляет Денису уведомление о новом заказе.
    Возвращает True при успехе.
    Вызывается как background task из POST /api/orders.
    """
    if not settings.admin_telegram_id:
        logger.warning("ADMIN_TELEGRAM_ID не задан, уведомление пропущено")
        return False

    bot = _get_bot()
    if not bot:
        logger.warning("BOT_TOKEN не задан, уведомление пропущено")
        return False

    text = _build_order_message(order_data)

    # Кнопки управления заказом
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order_data['order_id']}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_data['order_id']}"),
        ],
        [
            InlineKeyboardButton("📦 Отправлен", callback_data=f"ship_{order_data['order_id']}"),
        ],
    ])

    try:
        await bot.send_message(
            chat_id=settings.admin_telegram_id,
            text=text,
            reply_markup=keyboard,
        )
        logger.info(f"Уведомление о заказе {order_data['order_number']} отправлено Денису")
        return True
    except TelegramError as e:
        logger.error(f"Ошибка отправки уведомления о заказе {order_data['order_number']}: {e}")
        return False


async def notify_buyer(telegram_id: int, text: str) -> bool:
    """Отправляет сообщение покупателю."""
    bot = _get_bot()
    if not bot:
        return False

    try:
        await bot.send_message(chat_id=telegram_id, text=text)
        return True
    except TelegramError as e:
        logger.error(f"Ошибка уведомления покупателя {telegram_id}: {e}")
        return False


async def notify_buyer_order_accepted(telegram_id: int, order_number: str) -> bool:
    """«Заказ #1042 принят! Скоро свяжемся с вами.»"""
    return await notify_buyer(
        telegram_id,
        f"✅ Заказ {order_number} принят!\nСкоро свяжемся с вами."
    )


async def notify_buyer_order_shipped(
    telegram_id: int, order_number: str, tracking: str = ""
) -> bool:
    """«Заказ #1042 в пути. Трек: XXXXX»"""
    text = f"🚚 Заказ {order_number} в пути."
    if tracking:
        text += f"\nТрек: {tracking}"
    return await notify_buyer(telegram_id, text)
