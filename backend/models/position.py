"""
Position Model - Section 5 Database Schema from PLAN-v2.md
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import String, DateTime, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Position(Base):
    """Position model for tracking open positions."""
    
    __tablename__ = "positions"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    order_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    strategy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    pair: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    entry_price: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    current_price: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    unrealized_pnl: Mapped[float] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00000000"),
    )
    stop_loss: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    take_profit: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    closed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id) if self.order_id else None,
            "strategy_id": str(self.strategy_id),
            "pair": self.pair,
            "side": self.side,
            "quantity": float(self.quantity),
            "entry_price": float(self.entry_price),
            "current_price": float(self.current_price),
            "unrealized_pnl": float(self.unrealized_pnl),
            "stop_loss": float(self.stop_loss) if self.stop_loss else None,
            "take_profit": float(self.take_profit) if self.take_profit else None,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }