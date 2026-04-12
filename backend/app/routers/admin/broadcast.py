from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.broadcast import Broadcast
from app.models.buyer import Buyer
from app.services.auth import require_admin
from app.services.broadcast import run_broadcast
from app.services.storage import storage

router = APIRouter(prefix="/admin/broadcast", tags=["admin"])


# ─── Схемы ───────────────────────────────────────────────────────────────────

class BroadcastIn(BaseModel):
    text: str


class BroadcastOut(BaseModel):
    id: int
    text: str
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    started_at: str | None
    finished_at: str | None
    created_at: str
    photo_url: str | None = None

    class Config:
        from_attributes = True


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[BroadcastOut])
async def list_broadcasts(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """История рассылок (последние 20)."""
    result = await db.execute(
        select(Broadcast).order_by(Broadcast.created_at.desc()).limit(20)
    )
    return [_out(b) for b in result.scalars().all()]


@router.get("/{broadcast_id}", response_model=BroadcastOut)
async def get_broadcast(
    broadcast_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Прогресс конкретной рассылки (для polling из браузера)."""
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    return _out(b)


@router.post("", response_model=BroadcastOut, status_code=status.HTTP_201_CREATED)
async def create_broadcast(
    background_tasks: BackgroundTasks,
    text: str,
    photo: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Создаёт рассылку и сразу запускает отправку в фоне.
    text — обязательный form-поле.
    photo — опциональный файл.
    """
    if not text.strip():
        raise HTTPException(status_code=422, detail="Текст рассылки не может быть пустым")

    # Считаем сколько получателей (для предварительного показа)
    count_result = await db.execute(
        select(Buyer).where(Buyer.is_blocked == False)
    )
    recipients_count = len(count_result.scalars().all())

    # Загружаем фото если есть
    storage_key = None
    storage_provider = "local"

    if photo and photo.filename:
        ALLOWED = {"image/jpeg", "image/png", "image/webp"}
        if photo.content_type not in ALLOWED:
            raise HTTPException(status_code=422, detail="Разрешены только JPEG, PNG, WebP")
        file_bytes = await photo.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Файл больше 10 МБ")
        storage_key, storage_provider = await storage.upload(
            file_bytes, photo.filename, product_id=0
        )

    broadcast = Broadcast(
        text=text.strip(),
        storage_key=storage_key,
        storage_provider=storage_provider,
        status="draft",
    )
    db.add(broadcast)
    await db.flush()
    await db.refresh(broadcast)

    # Запускаем рассылку в фоне
    background_tasks.add_task(run_broadcast, broadcast.id)

    return _out(broadcast)


@router.delete("/{broadcast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_broadcast(
    broadcast_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Удалить запись о рассылке (только draft или завершённые)."""
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    if b.status == "sending":
        raise HTTPException(status_code=409, detail="Нельзя удалить рассылку в процессе отправки")
    await db.delete(b)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _out(b: Broadcast) -> BroadcastOut:
    photo_url = None
    if b.storage_key:
        photo_url = storage.get_url_by_key(b.storage_key, b.storage_provider)
    return BroadcastOut(
        id=b.id,
        text=b.text,
        status=b.status,
        total_recipients=b.total_recipients,
        sent_count=b.sent_count,
        failed_count=b.failed_count,
        started_at=b.started_at.strftime("%d.%m.%Y %H:%M") if b.started_at else None,
        finished_at=b.finished_at.strftime("%d.%m.%Y %H:%M") if b.finished_at else None,
        created_at=b.created_at.strftime("%d.%m.%Y %H:%M"),
        photo_url=photo_url,
    )
