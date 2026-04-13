"""
Тесты для app/services/broadcast.py и GET /admin/broadcast

Проверяем:
- run_broadcast с 0 получателями → status='sent', total_recipients=0
- run_broadcast отправляет сообщения всем незаблокированным покупателям
- Forbidden → buyer.is_blocked=True, failed_count++
- RetryAfter → повторная попытка, успех засчитывается
- Токена нет → статус 'failed'
- GET /admin/broadcast требует Bearer-токен
- POST /admin/broadcast создаёт запись и возвращает id
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from telegram.error import Forbidden, RetryAfter, TelegramError

from app.database import AsyncSessionLocal
from app.models.broadcast import Broadcast
from app.models.buyer import Buyer
from app.services.broadcast import run_broadcast


# ─── Фикстуры ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def patch_session(db_engine, monkeypatch):
    """Подменяем AsyncSessionLocal на тестовый движок."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    class _CM:
        def __init__(self):
            self._session = None

        async def __aenter__(self):
            self._session = factory()
            return await self._session.__aenter__()

        async def __aexit__(self, *args):
            return await self._session.__aexit__(*args)

    import app.services.broadcast as bc_module
    monkeypatch.setattr(bc_module, "AsyncSessionLocal", _CM)


async def _add_buyer(session, telegram_id: int, is_blocked: bool = False):
    b = Buyer(telegram_id=telegram_id, first_name="Test", is_blocked=is_blocked)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def _add_broadcast(session, text: str = "Hello") -> int:
    bc = Broadcast(text=text, status="draft")
    session.add(bc)
    await session.commit()
    await session.refresh(bc)
    return bc.id


# ─── Тесты run_broadcast ─────────────────────────────────────────────────────

class TestRunBroadcast:
    @pytest.mark.asyncio
    async def test_no_token_sets_failed(self, db_session):
        bc_id = await _add_broadcast(db_session)

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=None):
            await run_broadcast(bc_id)

        from sqlalchemy import select
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.status == "failed"

    @pytest.mark.asyncio
    async def test_no_buyers_sets_sent(self, db_session):
        bc_id = await _add_broadcast(db_session)
        mock_bot = MagicMock()

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot):
            await run_broadcast(bc_id)

        from sqlalchemy import select
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.status == "sent"
        assert bc.total_recipients == 0

    @pytest.mark.asyncio
    async def test_sends_to_all_active_buyers(self, db_session):
        await _add_buyer(db_session, telegram_id=111)
        await _add_buyer(db_session, telegram_id=222)
        await _add_buyer(db_session, telegram_id=333, is_blocked=True)  # пропустить
        bc_id = await _add_broadcast(db_session)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await run_broadcast(bc_id)

        # Должны отправить только 2 (не заблокированным)
        assert mock_bot.send_message.call_count == 2

        from sqlalchemy import select
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.status == "sent"
        assert bc.total_recipients == 2
        assert bc.sent_count == 2
        assert bc.failed_count == 0

    @pytest.mark.asyncio
    async def test_forbidden_marks_buyer_blocked(self, db_session):
        buyer = await _add_buyer(db_session, telegram_id=555)
        bc_id = await _add_broadcast(db_session)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Forbidden("Bot was blocked"))

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await run_broadcast(bc_id)

        from sqlalchemy import select
        # Покупатель должен быть заблокирован
        result = await db_session.execute(select(Buyer).where(Buyer.id == buyer.id))
        updated_buyer = result.scalar_one()
        assert updated_buyer.is_blocked is True

        # Рассылка: 0 sent, 1 failed
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.failed_count == 1
        assert bc.sent_count == 0
        assert bc.status == "sent"

    @pytest.mark.asyncio
    async def test_retry_after_then_success(self, db_session):
        await _add_buyer(db_session, telegram_id=777)
        bc_id = await _add_broadcast(db_session)

        mock_bot = MagicMock()
        retry_error = RetryAfter(1)
        # Первый вызов → RetryAfter, второй (retry) → успех
        mock_bot.send_message = AsyncMock(side_effect=[retry_error, None])

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await run_broadcast(bc_id)

        from sqlalchemy import select
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.sent_count == 1
        assert bc.failed_count == 0

    @pytest.mark.asyncio
    async def test_telegram_error_increments_failed(self, db_session):
        await _add_buyer(db_session, telegram_id=888)
        bc_id = await _add_broadcast(db_session)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=TelegramError("Network error"))

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await run_broadcast(bc_id)

        from sqlalchemy import select
        result = await db_session.execute(select(Broadcast).where(Broadcast.id == bc_id))
        bc = result.scalar_one()
        assert bc.failed_count == 1
        assert bc.sent_count == 0

    @pytest.mark.asyncio
    async def test_skips_non_draft_broadcast(self, db_session):
        """Уже запущенную рассылку не трогаем."""
        bc = Broadcast(text="test", status="sending")
        db_session.add(bc)
        await db_session.commit()
        await db_session.refresh(bc)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        import app.services.broadcast as bc_module
        with patch.object(bc_module, "_get_bot", return_value=mock_bot):
            await run_broadcast(bc.id)

        assert mock_bot.send_message.call_count == 0


# ─── Тесты API /admin/broadcast ──────────────────────────────────────────────

class TestAdminBroadcastAPI:
    @pytest.mark.asyncio
    async def test_get_requires_auth(self, client):
        resp = await client.get("/admin/broadcast")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_empty_list(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "admin_api_token", "testtoken")
        resp = await client.get("/admin/broadcast", headers={"Authorization": "Bearer testtoken"})
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_post_creates_broadcast(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "admin_api_token", "testtoken")

        with patch("app.routers.admin.broadcast.run_broadcast", new_callable=AsyncMock):
            resp = await client.post(
                "/admin/broadcast",
                data={"text": "Привет покупатели!"},
                headers={"Authorization": "Bearer testtoken"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] >= 1
        assert data["text"] == "Привет покупатели!"
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_post_empty_text_returns_422(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "admin_api_token", "testtoken")

        resp = await client.post(
            "/admin/broadcast",
            data={"text": "   "},
            headers={"Authorization": "Bearer testtoken"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "admin_api_token", "testtoken")

        resp = await client.get(
            "/admin/broadcast/999",
            headers={"Authorization": "Bearer testtoken"},
        )
        assert resp.status_code == 404
