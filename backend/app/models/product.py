from datetime import datetime
from sqlalchemy import Integer, Text, Boolean, ARRAY, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[str | None] = mapped_column(Text)
    material_label: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    badge: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sizes: Mapped[list] = mapped_column(ARRAY(Text), default=[])
    disabled_sizes: Mapped[list] = mapped_column(ARRAY(Text), default=[])
    colors: Mapped[list] = mapped_column(JSONB, default=[])
    description: Mapped[str | None] = mapped_column(Text)
    care: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    category: Mapped["Category"] = relationship(
        "Category", back_populates="products"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        order_by="ProductImage.sort_order",
        cascade="all, delete-orphan",
    )


class ProductImage(Base):
    __tablename__ = "product_image"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_provider: Mapped[str] = mapped_column(Text, default="cloudinary")
    telegram_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_type: Mapped[str] = mapped_column(Text, default="gallery")
    # gallery | size_chart
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    product: Mapped["Product"] = relationship("Product", back_populates="images")
