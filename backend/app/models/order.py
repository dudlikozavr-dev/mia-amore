from datetime import datetime
from sqlalchemy import Integer, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class Order(Base):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    buyer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("buyer.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(Text, default="new")
    # new | confirmed | shipped | delivered | cancelled

    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    delivery_cost: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)

    delivery_method: Mapped[str] = mapped_column(Text, nullable=False)
    # cdek | post
    payment_method: Mapped[str] = mapped_column(Text, nullable=False)
    # cod | online
    payment_status: Mapped[str] = mapped_column(Text, default="pending")
    # pending | paid | refunded

    # Snapshot данных доставки на момент заказа
    buyer_name: Mapped[str] = mapped_column(Text, nullable=False)
    buyer_phone: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    # Надёжность: False = уведомление ещё не дошло до Дениса → retry
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    buyer: Mapped["Buyer"] = relationship("Buyer", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("product.id", ondelete="SET NULL"), nullable=True
    )

    # Snapshot на момент заказа — не меняется никогда
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
