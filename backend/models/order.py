"""
Order Model - Section 5 Database Schema from PLAN-v2.md
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import String, DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Order(Base):
    """Order model for tracking order lifecycle."""
    
    __tablename__ = "orders"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    backtest_result_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    order_type: Mapped[str] = mapped_column(
        String(20),
        default="market",
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    pair: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    price: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    filled_quantity: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    avg_fill_price: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    commission: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    slippage_bps: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
    )
    exchange_order_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "backtest_result_id": str(self.backtest_result_id) if self.backtest_result_id else None,
            "order_type": self.order_type,
            "side": self.side,
            "pair": self.pair,
            "quantity": float(self.quantity),
            "price": float(self.price) if self.price else None,
            "filled_quantity": float(self.filled_quantity),
            "avg_fill_price": float(self.avg_fill_price),
            "commission": float(self.commission),
            "slippage_bps": float(self.slippage_bps),
            "status": self.status,
            "exchange_order_id": self.exchange_order_id,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }