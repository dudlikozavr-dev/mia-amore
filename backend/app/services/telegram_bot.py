"""
Telegram Bot — хендлеры для Дениса (администратора).

Команды:
  /start        — главное меню
  /orders       — список новых заказов
  /order 1042   — детали заказа

Inline callbacks (кнопки из уведомления о новом заказе):
  confirm_<order_id>  — перевести в «confirmed»
  cancel_<order_id>   — перевести в «cancelled»
  ship_<order_id>     — перевести в «shipped»
"""
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

from app.config import settings

logger = logging.getLogger(__name__)

# Статусы и их метки
STATUS_LABELS = {
    "new":       "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "shipped":   "📦 Отправлен",
    "delivered": "🏠 Доставлен",
    "cancelled": "❌ Отменён",
}

DELIVERY_LABELS = {"cdek": "СДЭК", "post": "Почта России"}
PAYMENT_LABELS = {"cod": "При получении", "online": "Онлайн"}


def _is_admin(user_id: int) -> bool:
    return settings.admin_telegram_id != 0 and user_id == settings.admin_telegram_id


# ─── Команды ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Новые заказы", callback_data="list_new")],
        [InlineKeyboardButton("📦 Все заказы", callback_data="list_all")],
    ])
    await update.message.reply_text(
        "Mia-Amore Admin\n\nВыбери действие:",
        reply_markup=keyboard,
    )


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список заказов со статусом 'new'"""
    if not _is_admin(update.effective_user.id):
        return
    await _send_orders_list(update, context, status_filter="new")


async def cmd_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/order 1042 — детали заказа по номеру"""
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Укажи номер: /order 1042")
        return

    raw = context.args[0].lstrip("#")
    from app.database import AsyncSessionLocal
    from app.models.order import Order, OrderItem
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order).where(Order.order_number == f"#{raw}")
        )
        order = result.scalar_one_or_none()

        if not order:
            await update.message.reply_text(f"Заказ #{raw} не найден")
            return

        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()

    await update.message.reply_text(
        _format_order_detail(order, items),
        reply_markup=_order_keyboard(order.id, order.status),
    )


# ─── Inline callbacks ─────────────────────────────────────────────────────────

async def callback_order_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопки confirm_N, cancel_N, ship_N, list_new, list_all"""
    query = update.callback_query
    await query.answer()

    if not _is_admin(query.from_user.id):
        return

    data = query.data

    if data in ("list_new", "list_all"):
        status = "new" if data == "list_new" else None
        await _send_orders_list_via_callback(query, status)
        return

    # Кнопки действий с заказом: confirm_42, cancel_42, ship_42
    action_map = {
        "confirm": "confirmed",
        "cancel":  "cancelled",
        "ship":    "shipped",
    }

    for prefix, new_status in action_map.items():
        if data.startswith(f"{prefix}_"):
            order_id = int(data.split("_", 1)[1])
            await _change_order_status(query, order_id, new_status)
            return


# ─── Вспомогательные функции ─────────────────────────────────────────────────

async def _send_orders_list(update, context, status_filter: str | None = "new") -> None:
    from app.database import AsyncSessionLocal
    from app.models.order import Order
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        q = select(Order).order_by(Order.created_at.desc()).limit(10)
        if status_filter:
            q = q.where(Order.status == status_filter)
        result = await db.execute(q)
        orders = result.scalars().all()

    if not orders:
        label = f"со статусом «{status_filter}»" if status_filter else ""
        await update.message.reply_text(f"Заказов {label} нет.")
        return

    lines = [f"Заказы ({STATUS_LABELS.get(status_filter, 'все')}):"]
    for o in orders:
        lines.append(f"  {o.order_number} — {o.buyer_name} — {o.total:,} ₽ — /order {o.order_number.lstrip('#')}")
    await update.message.reply_text("\n".join(lines))


async def _send_orders_list_via_callback(query, status_filter: str | None) -> None:
    from app.database import AsyncSessionLocal
    from app.models.order import Order
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        q = select(Order).order_by(Order.created_at.desc()).limit(10)
        if status_filter:
            q = q.where(Order.status == status_filter)
        result = await db.execute(q)
        orders = result.scalars().all()

    if not orders:
        label = f"со статусом «{status_filter}»" if status_filter else ""
        await query.edit_message_text(f"Заказов {label} нет.")
        return

    lines = [f"Заказы ({STATUS_LABELS.get(status_filter, 'все')}):"]
    for o in orders:
        lines.append(f"  {o.order_number} — {o.buyer_name} — {o.total:,} ₽")
    await query.edit_message_text("\n".join(lines))


async def _change_order_status(query, order_id: int, new_status: str) -> None:
    from app.database import AsyncSessionLocal
    from app.models.order import Order
    from app.models.buyer import Buyer
    from app.services.notifications import notify_buyer
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            await query.edit_message_text(f"Заказ #{order_id} не найден")
            return

        old_status = order.status
        order.status = new_status
        await db.commit()
        await db.refresh(order)

        # Уведомление покупателю
        if order.buyer_id:
            buyer_result = await db.execute(
                select(Buyer).where(Buyer.id == order.buyer_id)
            )
            buyer = buyer_result.scalar_one_or_none()
            if buyer:
                msg = _buyer_status_message(order.order_number, new_status)
                if msg:
                    await notify_buyer(buyer.telegram_id, msg)

    label = STATUS_LABELS.get(new_status, new_status)
    await query.edit_message_text(
        f"Заказ {order.order_number}: статус изменён → {label}\n"
        f"Покупатель уведомлён.",
    )


def _buyer_status_message(order_number: str, status: str) -> str | None:
    messages = {
        "confirmed": f"📦 Заказ {order_number} подтверждён и готовится к отправке.",
        "shipped":   f"🚚 Заказ {order_number} отправлен. Ожидайте!",
        "delivered": f"✅ Заказ {order_number} доставлен. Спасибо за покупку!",
        "cancelled": f"❌ Заказ {order_number} отменён. Свяжитесь с нами, если есть вопросы.",
    }
    return messages.get(status)


def _format_order_detail(order, items: list) -> str:
    items_text = "\n".join(
        f"  • {i.product_name} {i.size}, {i.color} ×{i.qty} — {i.unit_price * i.qty:,} ₽"
        for i in items
    )
    delivery = DELIVERY_LABELS.get(order.delivery_method, order.delivery_method)
    payment = PAYMENT_LABELS.get(order.payment_method, order.payment_method)
    status = STATUS_LABELS.get(order.status, order.status)

    return (
        f"Заказ {order.order_number} | {status}\n"
        f"Покупатель: {order.buyer_name}\n"
        f"Телефон: {order.buyer_phone}\n\n"
        f"{items_text}\n\n"
        f"Подитог: {order.subtotal:,} ₽\n"
        f"Доставка: {order.delivery_cost:,} ₽ ({delivery})\n"
        f"Итого: {order.total:,} ₽\n"
        f"Оплата: {payment}\n\n"
        f"Адрес: {order.city}, {order.address}"
        + (f"\nКомментарий: {order.notes}" if order.notes else "")
        + f"\n\nСоздан: {order.created_at.strftime('%d.%m.%Y %H:%M')}"
    )


def _order_keyboard(order_id: int, current_status: str) -> InlineKeyboardMarkup:
    """Кнопки действий для конкретного заказа."""
    buttons = []
    if current_status == "new":
        buttons.append([
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}"),
        ])
        buttons.append([
            InlineKeyboardButton("📦 Отправлен", callback_data=f"ship_{order_id}"),
        ])
    elif current_status == "confirmed":
        buttons.append([
            InlineKeyboardButton("📦 Отправлен", callback_data=f"ship_{order_id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}"),
        ])
    return InlineKeyboardMarkup(buttons) if buttons else None


# ─── Рассылка через бота ─────────────────────────────────────────────────────

# Словарь: admin_telegram_id → текст который набирает для рассылки
_broadcast_drafts: dict[int, str] = {}


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/broadcast — начать создание рассылки."""
    if not _is_admin(update.effective_user.id):
        return
    _broadcast_drafts[update.effective_user.id] = ""
    await update.message.reply_text(
        "📢 Введи текст рассылки.\n"
        "Можно прикрепить фото к следующему сообщению.\n\n"
        "Для отмены: /cancel"
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    _broadcast_drafts.pop(update.effective_user.id, None)
    await update.message.reply_text("Отменено.")


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перехватывает текст/фото пока активен режим рассылки."""
    user_id = update.effective_user.id
    if not _is_admin(user_id) or user_id not in _broadcast_drafts:
        return

    msg = update.message
    text = _broadcast_drafts.get(user_id, "")

    # Если ещё не ввели текст — сохраняем
    if not text:
        text = msg.text or msg.caption or ""
        if not text:
            await msg.reply_text("Введи текст рассылки (или текст + фото).")
            return
        _broadcast_drafts[user_id] = text

        # Показываем превью и просим подтвердить
        from app.database import AsyncSessionLocal
        from app.models.buyer import Buyer
        from sqlalchemy import select, func as sqlfunc
        async with AsyncSessionLocal() as db:
            count_res = await db.execute(
                select(sqlfunc.count(Buyer.id)).where(Buyer.is_blocked == False)
            )
            count = count_res.scalar()

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Отправить {count} покупателям", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"),
        ]])
        await msg.reply_text(
            f"📢 Превью рассылки:\n\n{text}\n\n"
            f"Получателей: {count}",
            reply_markup=keyboard,
        )
        return

    # Иначе — сообщение не относится к рассылке
    _broadcast_drafts.pop(user_id, None)


async def callback_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """callback_data: broadcast_confirm / broadcast_cancel."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not _is_admin(user_id):
        return

    if query.data == "broadcast_cancel":
        _broadcast_drafts.pop(user_id, None)
        await query.edit_message_text("Рассылка отменена.")
        return

    if query.data == "broadcast_confirm":
        text = _broadcast_drafts.pop(user_id, None)
        if not text:
            await query.edit_message_text("Текст рассылки потерян. Начни заново: /broadcast")
            return

        # Создаём рассылку через сервис
        from app.database import AsyncSessionLocal
        from app.models.broadcast import Broadcast
        from app.services.broadcast import run_broadcast
        import asyncio

        async with AsyncSessionLocal() as db:
            broadcast = Broadcast(text=text, status="draft")
            db.add(broadcast)
            await db.flush()
            await db.refresh(broadcast)
            broadcast_id = broadcast.id
            await db.commit()

        asyncio.create_task(run_broadcast(broadcast_id))

        await query.edit_message_text(
            f"🚀 Рассылка #{broadcast_id} запущена!\n"
            f"Прогресс можно отследить в /admin панели."
        )


# ─── Оплата ──────────────────────────────────────────────────────────────────

async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram требует подтвердить заказ в течение 10 секунд."""
    await update.pre_checkout_query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    try:
        order_id = int(payment.invoice_payload)
    except ValueError:
        logger.error("successful_payment: некорректный payload %s", payment.invoice_payload)
        return

    from app.database import AsyncSessionLocal
    from app.models.order import Order, OrderItem
    from app.models.buyer import Buyer
    from app.services.notifications import notify_admin_new_order, notify_buyer
    from sqlalchemy import select
    import asyncio

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            logger.error("successful_payment: заказ #%s не найден", order_id)
            return

        order.status = "paid"
        order.notification_sent = True
        await db.commit()

        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()

        buyer_telegram_id: int | None = None
        if order.buyer_id:
            buyer_result = await db.execute(
                select(Buyer).where(Buyer.id == order.buyer_id)
            )
            buyer = buyer_result.scalar_one_or_none()
            if buyer:
                buyer_telegram_id = buyer.telegram_id

    order_data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "buyer_name": order.buyer_name,
        "buyer_phone": order.buyer_phone,
        "buyer_username": None,
        "buyer_telegram_id": buyer_telegram_id,
        "city": order.city,
        "address": order.address,
        "notes": order.notes,
        "delivery_method": order.delivery_method,
        "total": order.total,
        "items": [
            {"product_name": i.product_name, "size": i.size, "color": i.color, "qty": i.qty}
            for i in items
        ],
    }

    tasks = [notify_admin_new_order(order_data)]
    if buyer_telegram_id:
        tasks.append(notify_buyer(
            buyer_telegram_id,
            f"✅ Оплата прошла успешно!\nЗаказ {order.order_number} принят и готовится к отправке.",
        ))
    await asyncio.gather(*tasks)


# ─── Инициализация приложения бота ───────────────────────────────────────────

def build_application() -> Application:
    """Создаёт и настраивает PTB Application для webhook-режима."""
    token = settings.bot_token if not settings.is_dev else (settings.bot_token_test or settings.bot_token)
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    builder = Application.builder().token(token)
    if settings.telegram_proxy_url:
        builder = builder.proxy(settings.telegram_proxy_url)
    app = builder.build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("orders",    cmd_orders))
    app.add_handler(CommandHandler("order",     cmd_order))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))

    # Оплата
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    # Callback handlers — порядок важен: broadcast раньше order-actions
    app.add_handler(CallbackQueryHandler(callback_broadcast,    pattern=r"^broadcast_"))
    app.add_handler(CallbackQueryHandler(callback_order_action))

    # Текстовые сообщения — для ввода текста рассылки
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_broadcast_message,
    ))

    return app
