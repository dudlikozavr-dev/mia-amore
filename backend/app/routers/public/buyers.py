from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.buyer import Buyer
from app.services.auth import require_init_data

router = APIRouter(prefix="/api", tags=["public"])


class BuyerIn(BaseModel):
    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class BuyerOut(BaseModel):
    id: int
    telegram_id: int
    first_name: str | None
    username: str | None

    class Config:
        from_attributes = True


@router.post("/buyers/identify", response_model=BuyerOut)
async def identify_buyer(
    body: BuyerIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_init_data),
):
    """
    Регистрирует покупателя при первом открытии Mini App
    или обновляет last_active_at при повторном.
    Upsert по telegram_id.
    """
    result = await db.execute(
        select(Buyer).where(Buyer.telegram_id == body.telegram_id)
    )
    buyer = result.scalar_one_or_none()

    if buyer:
        # Обновляем данные и время активности
        buyer.first_name = body.first_name
        buyer.last_name = body.last_name
        buyer.username = body.username
        buyer.last_active_at = func.now()
    else:
        buyer = Buyer(
            telegram_id=body.telegram_id,
            first_name=body.first_name,
            last_name=body.last_name,
            username=body.username,
        )
        db.add(buyer)

    await db.flush()
    await db.refresh(buyer)
    return buyer
