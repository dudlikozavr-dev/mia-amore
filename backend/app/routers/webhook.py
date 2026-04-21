"""
POST /webhook — принимает апдейты от Telegram и передаёт в PTB Application.

Telegram шлёт сюда все сообщения и callback query.
PTB обрабатывает их через хендлеры из telegram_bot.py.
"""
import logging

from fastapi import APIRouter, HTTPException, Request, status
from telegram import Update

from app.services.telegram_bot import build_application

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])

# PTB Application — создаётся один раз при импорте
# (main.py вызывает initialize() в lifespan)
_ptb_app = None


def get_ptb_app():
    global _ptb_app
    if _ptb_app is None:
        try:
            _ptb_app = build_application()
        except RuntimeError as e:
            logger.warning(f"Бот не инициализирован: {e}")
    return _ptb_app


async def initialize_bot() -> None:
    """Инициализирует PTB и регистрирует webhook URL в Telegram."""
    from app.config import settings

    app = get_ptb_app()
    if app is None:
        return

    await app.initialize()

    # Регистрируем webhook если задан URL бэкенда
    backend_url = getattr(settings, "backend_url", "").rstrip("/")
    if backend_url:
        webhook_url = f"{backend_url}/webhook"
        try:
            import asyncio
            from telegram.error import RetryAfter
            for attempt in range(5):
                try:
                    await app.bot.set_webhook(
                        url=webhook_url,
                        allowed_updates=["message", "callback_query"],
                    )
                    logger.info(f"Webhook зарегистрирован: {webhook_url}")
                    break
                except RetryAfter as e:
                    wait = e.retry_after + 1
                    logger.warning(f"Flood control, ждём {wait}s (попытка {attempt+1}/5)")
                    await asyncio.sleep(wait)
        except Exception as e:
            logger.error(f"Не удалось зарегистрировать webhook: {e}")
    else:
        logger.warning("BACKEND_URL не задан — webhook не зарегистрирован")


async def shutdown_bot() -> None:
    """Освобождает ресурсы PTB при остановке сервера."""
    app = get_ptb_app()
    if app is not None:
        await app.shutdown()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request):
    """
    Принимает JSON-апдейт от Telegram.
    Telegram ожидает ответ 200 OK — иначе через 50 попыток прекратит слать.
    """
    app = get_ptb_app()
    if app is None:
        # Бот не настроен — возвращаем 200 чтобы Telegram не ретраил
        return {"ok": True}

    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        # Всегда 200 — иначе Telegram будет ретраить вечно

    return {"ok": True}
