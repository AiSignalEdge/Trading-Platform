"""
Position Domain Model - Section 4 from PLAN-v2.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Position domain model."""
    id: UUID = field(default_factory=uuid4)
    order_id: Optional[UUID] = None
    strategy_id: UUID = field(default_factory=uuid4)
    pair: str = ""
    side: PositionSide = PositionSide.LONG
    quantity: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id) if self.order_id else None,
            "strategy_id": str(self.strategy_id),
            "pair": self.pair,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "updated_at": self.updated_at.isoformat(),
        }

    def update_price(self, current_price: float) -> None:
        """Recalculate unrealized PnL based on current price."""
        self.current_price = current_price
        price_change = (current_price - self.entry_price) / self.entry_price
        
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
            self.unrealized_pnl_pct = price_change * 100
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
            self.unrealized_pnl_pct = -price_change * 100
        
        self.updated_at = datetime.utcnow()

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def notional_value(self) -> float:
        return self.quantity * self.current_price