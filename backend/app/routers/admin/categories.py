from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.services.auth import require_admin

router = APIRouter(prefix="/admin/categories", tags=["admin"])


class CategoryIn(BaseModel):
    name: str
    slug: str
    sort_order: int = 0
    is_active: bool = True


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    sort_order: int
    is_active: bool
    product_count: int = 0

    class Config:
        from_attributes = True


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(
        select(Category).order_by(Category.sort_order)
    )
    categories = result.scalars().all()

    # Считаем кол-во товаров в каждой категории
    counts_result = await db.execute(
        select(Product.category_id, func.count(Product.id))
        .where(Product.is_active == True)
        .group_by(Product.category_id)
    )
    counts = dict(counts_result.all())

    out = []
    for c in categories:
        out.append(CategoryOut(
            id=c.id,
            name=c.name,
            slug=c.slug,
            sort_order=c.sort_order,
            is_active=c.is_active,
            product_count=counts.get(c.id, 0),
        ))
    return out


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    # Проверяем уникальность slug
    existing = await db.execute(select(Category).where(Category.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug «{body.slug}» уже занят")

    category = Category(**body.model_dump())
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return CategoryOut(
        id=category.id, name=category.name, slug=category.slug,
        sort_order=category.sort_order, is_active=category.is_active,
        product_count=0,
    )


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    body: CategoryIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Проверяем slug (только если изменился)
    if body.slug != category.slug:
        existing = await db.execute(select(Category).where(Category.slug == body.slug))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Slug «{body.slug}» уже занят")

    for field, value in body.model_dump().items():
        setattr(category, field, value)

    await db.flush()
    await db.refresh(category)
    return CategoryOut(
        id=category.id, name=category.name, slug=category.slug,
        sort_order=category.sort_order, is_active=category.is_active,
        product_count=0,
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Удалять нельзя если есть товары
    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    if count_result.scalar() > 0:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить категорию с товарами — сначала перенеси или удали товары",
        )

    await db.delete(category)
