"""
Portfolio Domain Model - Section 4 from PLAN-v2.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from .position import Position, PositionSide
from .order import OrderSide


@dataclass
class Portfolio:
    """Portfolio domain model for multi-strategy tracking."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    strategies: list[UUID] = field(default_factory=list)
    initial_capital: float = 10000.0
    current_equity: float = 10000.0
    cash: float = 10000.0
    positions: list[Position] = field(default_factory=list)
    total_unrealized_pnl: float = 0.0
    leverage: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "strategies": [str(s) for s in self.strategies],
            "initial_capital": self.initial_capital,
            "current_equity": self.current_equity,
            "cash": self.cash,
            "positions": [p.to_dict() for p in self.positions],
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "leverage": self.leverage,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def update_equity(self) -> None:
        """Recalculate total equity from cash + positions."""
        position_value = sum(p.quantity * p.current_price for p in self.positions)
        self.total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions)
        self.current_equity = self.cash + position_value + self.total_unrealized_pnl
        self.updated_at = datetime.utcnow()

    def add_position(self, position: Position) -> None:
        """Add a new position to portfolio."""
        self.positions.append(position)
        self.update_equity()

    def close_position(self, position_id: UUID) -> Optional[Position]:
        """Close and remove a position."""
        for i, pos in enumerate(self.positions):
            if pos.id == position_id:
                pos.closed_at = datetime.utcnow()
                closed = self.positions.pop(i)
                self.update_equity()
                return closed
        return None

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.is_open]

    @property
    def total_position_value(self) -> float:
        return sum(p.quantity * p.current_price for p in self.positions)

    @property
    def margin_used(self) -> float:
        return self.total_position_value / self.leverage

    @property
    def return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return ((self.current_equity - self.initial_capital) / self.initial_capital) * 100