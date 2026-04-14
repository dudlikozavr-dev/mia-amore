from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.product import Product, ProductImage
from app.services.auth import require_admin
from app.services.storage import storage

router = APIRouter(prefix="/admin/products", tags=["admin"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ─── Схемы ───────────────────────────────────────────────────────────────────

class ProductIn(BaseModel):
    category_id: int | None = None
    name: str
    material: str | None = None
    material_label: str | None = None
    price: int
    old_price: int | None = None
    badge: str | None = None
    stock: int = 0
    sizes: list[str] = []
    disabled_sizes: list[str] = []
    colors: list[dict] = []
    description: str | None = None
    care: str | None = None
    is_active: bool = True
    sort_order: int = 0


class ImageOut(BaseModel):
    id: int
    url: str
    sort_order: int
    storage_key: str


class ProductOut(BaseModel):
    id: int
    category_id: int | None
    name: str
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
    is_active: bool
    sort_order: int
    images: list[ImageOut] = []

    class Config:
        from_attributes = True


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProductOut])
async def list_products(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Все товары (включая скрытые is_active=false)."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .order_by(Product.sort_order, Product.id)
    )
    products = result.scalars().all()
    return [_product_out(p) for p in products]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return _product_out(product)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    product = Product(**body.model_dump())
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return _product_out(product)


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    body: ProductIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    for field, value in body.model_dump().items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)
    return _product_out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Мягкое удаление: is_active = false."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    product.is_active = False
    await db.flush()


# ─── Фото ────────────────────────────────────────────────────────────────────

@router.post("/{product_id}/images", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Загружает фото и привязывает к товару."""
    # Проверяем что товар существует
    result = await db.execute(select(Product).where(Product.id == product_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Товар не найден")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="Разрешены только JPEG, PNG, WebP")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ")

    # Определяем sort_order (после последнего существующего фото)
    count_result = await db.execute(
        select(ProductImage).where(ProductImage.product_id == product_id)
    )
    existing = count_result.scalars().all()
    next_order = max((img.sort_order for img in existing), default=-1) + 1

    # Загружаем в хранилище
    key, provider = await storage.upload(file_bytes, file.filename or "image.jpg", product_id)

    image = ProductImage(
        product_id=product_id,
        storage_key=key,
        storage_provider=provider,
        sort_order=next_order,
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    return ImageOut(id=image.id, url=storage.get_url(image), sort_order=image.sort_order, storage_key=key)


@router.put("/{product_id}/images/reorder")
async def reorder_images(
    product_id: int,
    image_ids: list[int],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Переставить порядок фото. image_ids — новый порядок (список id)."""
    for order, image_id in enumerate(image_ids):
        result = await db.execute(
            select(ProductImage).where(
                ProductImage.id == image_id,
                ProductImage.product_id == product_id,
            )
        )
        img = result.scalar_one_or_none()
        if img:
            img.sort_order = order

    return {"ok": True}


@router.patch("/images/{image_id}/type")
async def set_image_type(
    image_id: int,
    image_type: str,   # gallery | size_chart
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Пометить фото как таблицу размеров или обычное фото галереи."""
    if image_type not in ("gallery", "size_chart"):
        raise HTTPException(status_code=400, detail="image_type: gallery или size_chart")

    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    # Если ставим size_chart — сбрасываем у других фото этого товара
    if image_type == "size_chart":
        await db.execute(
            select(ProductImage).where(
                ProductImage.product_id == image.product_id,
                ProductImage.image_type == "size_chart",
            )
        )
        siblings_result = await db.execute(
            select(ProductImage).where(
                ProductImage.product_id == image.product_id,
                ProductImage.image_type == "size_chart",
            )
        )
        for sibling in siblings_result.scalars().all():
            sibling.image_type = "gallery"

    image.image_type = image_type
    return {"id": image_id, "image_type": image_type}


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    await storage.delete(image)
    await db.delete(image)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        category_id=p.category_id,
        name=p.name,
        material=p.material,
        material_label=p.material_label,
        price=p.price,
        old_price=p.old_price,
        badge=p.badge,
        stock=p.stock,
        sizes=p.sizes or [],
        disabled_sizes=p.disabled_sizes or [],
        colors=p.colors or [],
        description=p.description,
        care=p.care,
        is_active=p.is_active,
        sort_order=p.sort_order,
        images=[
            ImageOut(id=img.id, url=storage.get_url(img), sort_order=img.sort_order, storage_key=img.storage_key)
            for img in sorted(p.images, key=lambda x: x.sort_order)
        ] if p.images else [],
    )
