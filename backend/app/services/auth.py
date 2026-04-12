"""
Валидация Telegram initData (HMAC-SHA256).
Стандарт: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Алгоритм:
1. Из строки initData убрать параметр hash=
2. Отсортировать оставшиеся параметры по алфавиту, склеить "\n"
3. Ключ = HMAC-SHA256("WebAppData", bot_token)
4. Подпись = HMAC-SHA256(data_check_string, ключ)
5. Сравнить подпись с hash из initData
6. Проверить auth_date: не старше 24 часов
"""
import hashlib
import hmac
import time
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException, status

from app.config import settings


class InitDataError(Exception):
    """Невалидная или устаревшая подпись initData"""


def _verify_init_data(init_data_raw: str, bot_token: str) -> dict:
    """
    Проверяет подпись и возвращает распарсенные поля initData.
    Бросает InitDataError если что-то не так.
    """
    params = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    received_hash = params.pop("hash", None)

    if not received_hash:
        raise InitDataError("Поле hash отсутствует")

    # data_check_string: параметры отсортированы и склеены \n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # Ключ = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()

    # Подпись = HMAC-SHA256(data_check_string, secret_key)
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("Подпись не совпадает")

    # Проверка свежести: auth_date не старше 24 часов
    auth_date = params.get("auth_date")
    if not auth_date:
        raise InitDataError("Поле auth_date отсутствует")

    age = time.time() - int(auth_date)
    if age > 86400:  # 24 часа
        raise InitDataError(f"initData устарела: {int(age)} сек")

    return params


def verify_init_data(init_data_raw: str) -> dict:
    """
    Проверяет initData с prod-токеном.
    В режиме development принимает пустой initData (для тестов из браузера).
    """
    if settings.is_dev and not init_data_raw:
        return {}

    token = settings.bot_token or settings.bot_token_test
    if not token:
        if settings.is_dev:
            return {}
        raise InitDataError("Токен бота не настроен")

    return _verify_init_data(init_data_raw, token)


# ─── FastAPI dependency ───────────────────────────────────────────────────────

def require_init_data(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> dict:
    """
    Зависимость для защищённых публичных эндпоинтов.
    Использование: data = Depends(require_init_data)
    """
    try:
        return verify_init_data(x_telegram_init_data)
    except InitDataError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


# ─── Admin Bearer-токен ───────────────────────────────────────────────────────

def require_admin(
    authorization: str = Header(default="", alias="Authorization"),
) -> None:
    """
    Зависимость для /admin/* эндпоинтов.
    Ожидает заголовок: Authorization: Bearer <token>
    """
    if not settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Админский токен не настроен",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа",
        )
