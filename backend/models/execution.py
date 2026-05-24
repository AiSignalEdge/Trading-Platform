"""
Execution models — Order and Position dataclasses for the trading engine.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class Position:
    id: UUID
    strategy_id: UUID
    symbol: str  # "BTCUSDT" (no slash)
    side: PositionSide
    quantity: float  # base asset amount
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    opened_at: datetime
    updated_at: datetime


@dataclass
class Order:
    id: UUID
    strategy_id: UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]  # None for market orders
    filled_quantity: float
    avg_fill_price: float
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime]