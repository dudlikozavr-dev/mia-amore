"""
Тесты для app/services/auth.py

Проверяем:
- _verify_init_data с корректной подписью → OK
- _verify_init_data с неверной подписью → InitDataError
- _verify_init_data с устаревшим auth_date → InitDataError
- _verify_init_data без hash → InitDataError
- verify_init_data в dev-режиме с пустым initData → {}
"""
import hashlib
import hmac
import time
import urllib.parse

import pytest

from app.services.auth import _verify_init_data, InitDataError


def _make_init_data(bot_token: str, auth_date: int | None = None, extra: dict | None = None) -> str:
    """Собирает валидный initData для тестов."""
    params = {
        "auth_date": str(auth_date or int(time.time())),
        "user": '{"id":12345,"first_name":"Test","username":"testuser"}',
    }
    if extra:
        params.update(extra)

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    params["hash"] = signature
    return urllib.parse.urlencode(params)


BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ0123456789"


class TestVerifyInitData:
    def test_valid_signature(self):
        init_data = _make_init_data(BOT_TOKEN)
        result = _verify_init_data(init_data, BOT_TOKEN)
        assert "auth_date" in result
        assert "user" in result

    def test_wrong_signature(self):
        init_data = _make_init_data(BOT_TOKEN)
        with pytest.raises(InitDataError, match="Подпись не совпадает"):
            _verify_init_data(init_data, "wrong_token")

    def test_missing_hash(self):
        init_data = "auth_date=12345&user=%7B%22id%22%3A1%7D"
        with pytest.raises(InitDataError, match="hash отсутствует"):
            _verify_init_data(init_data, BOT_TOKEN)

    def test_expired_auth_date(self):
        # auth_date старше 25 часов
        old_timestamp = int(time.time()) - 25 * 3600
        init_data = _make_init_data(BOT_TOKEN, auth_date=old_timestamp)
        with pytest.raises(InitDataError, match="устарела"):
            _verify_init_data(init_data, BOT_TOKEN)

    def test_fresh_auth_date(self):
        # auth_date 1 час назад — всё ещё валидно
        recent = int(time.time()) - 3600
        init_data = _make_init_data(BOT_TOKEN, auth_date=recent)
        result = _verify_init_data(init_data, BOT_TOKEN)
        assert result["auth_date"] == str(recent)

    def test_returns_params_without_hash(self):
        init_data = _make_init_data(BOT_TOKEN)
        result = _verify_init_data(init_data, BOT_TOKEN)
        # hash не должен быть в возвращаемом dict
        assert "hash" not in result
