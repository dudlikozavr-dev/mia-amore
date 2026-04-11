from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.database import get_db
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.services.storage import storage

router = APIRouter(prefix="/api", tags=["public"])


# ─── Схемы ответа ────────────────────────────────────────────

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    sort_order: int

    class Config:
        from_attributes = True


class ImageOut(BaseModel):
    id: int
    url: str
    sort_order: int


class ProductListItem(BaseModel):
    id: int
    name: str
    category_slug: str | None
    material_label: str | None
    price: int
    old_price: int | None
    badge: str | None
    stock: int
    cover: str | None    # первое фото


class ProductDetail(BaseModel):
    id: int
    name: str
    category_id: int | None
    category_slug: str | None
    material: str | None
    material_label: str | None
    price: int
    old_price: int | None
    badge: str | None
    stock: int
    sizes: list[str]
    disabled_sizes: list[str]
    colors: list[dict]
    description: str | None
    care: str | None
    images: list[ImageOut]


# ─── Эндпоинты ───────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Список активных категорий для фильтров в каталоге"""
    result = await db.execute(
        select(Category)
        .where(Category.is_active == True)
        .order_by(Category.sort_order)
    )
    return result.scalars().all()


@router.get("/products", response_model=list[ProductListItem])
async def get_products(
    category: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Список товаров для каталога.
    ?category=robe — фильтр по slug категории
    """
    query = (
        select(Product)
        .where(Product.is_active == True)
        .order_by(Product.sort_order)
        .options(selectinload(Product.images), selectinload(Product.category))
    )

    if category and category != "all":
        query = query.join(Category).where(Category.slug == category)

    result = await db.execute(query)
    products = result.scalars().all()

    items = []
    for p in products:
        cover = storage.get_url(p.images[0]) if p.images else None
        cat_slug = p.category.slug if p.category else None

        items.append(ProductListItem(
            id=p.id,
            name=p.name,
            category_slug=cat_slug,
            material_label=p.material_label,
            price=p.price,
            old_price=p.old_price,
            badge=p.badge,
            stock=p.stock,
            cover=cover,
        ))

    return items


@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Карточка товара — полные данные"""
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.is_active == True)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Загружаем фото
    img_result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
    )
    images = img_result.scalars().all()

    cat_slug = None
    if product.category_id:
        cat_result = await db.execute(
            select(Category).where(Category.id == product.category_id)
        )
        cat = cat_result.scalar_one_or_none()
        if cat:
            cat_slug = cat.slug

    return ProductDetail(
        id=product.id,
        name=product.name,
        category_id=product.category_id,
        category_slug=cat_slug,
        material=product.material,
        material_label=product.material_label,
        price=product.price,
        old_price=product.old_price,
        badge=product.badge,
        stock=product.stock,
        sizes=product.sizes or [],
        disabled_sizes=product.disabled_sizes or [],
        colors=product.colors or [],
        description=product.description,
        care=product.care,
        images=[
            ImageOut(id=img.id, url=storage.get_url(img), sort_order=img.sort_order)
            for img in images
        ],
    )
