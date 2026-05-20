"""
Event Pipeline - All system events are immutable dataclasses.

Section 3: Event Pipeline from PLAN-v2.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from uuid import UUID, uuid4


class EventType(Enum):
    """All event types in the system."""
    TICK = "tick"
    CANDLE = "candle"
    SIGNAL = "signal"
    ORDER_REQUEST = "order_request"
    ORDER_REJECTED = "order_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_UPDATE = "portfolio_update"
    REGIME_CHANGE = "regime_change"


@dataclass
class BaseEvent:
    """Base class for all events."""
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: EventType = EventType.CANDLE
    source: str = ""  # strategy_id, exchange, etc.

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "source": self.source,
        }


@dataclass
class CandleEvent(BaseEvent):
    """Raw OHLCV candle event."""
    pair: str = ""
    timeframe: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "pair": self.pair,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        })
        return base


@dataclass
class SignalEvent(BaseEvent):
    """Strategy signal generated."""
    pair: str = ""
    direction: Literal["long", "short", "close"] = "long"
    strength: float = 0.0  # 0.0–1.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_id: UUID = field(default_factory=uuid4)
    signal_id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "pair": self.pair,
            "direction": self.direction,
            "strength": self.strength,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy_id": str(self.strategy_id),
            "signal_id": str(self.signal_id),
        })
        return base


@dataclass
class OrderEvent(BaseEvent):
    """Order lifecycle event."""
    order_id: UUID = field(default_factory=uuid4)
    signal_id: Optional[UUID] = None
    pair: str = ""
    side: Literal["buy", "sell"] = "buy"
    order_type: Literal["market", "limit", "stop", "take_profit"] = "market"
    quantity: float = 0.0
    price: Optional[float] = None
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    commission: float = 0.0
    slippage_bps: float = 0.0

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "order_id": str(self.order_id),
            "signal_id": str(self.signal_id) if self.signal_id else None,
            "pair": self.pair,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "filled_price": self.filled_price,
            "filled_quantity": self.filled_quantity,
            "commission": self.commission,
            "slippage_bps": self.slippage_bps,
        })
        return base


@dataclass
class PositionEvent(BaseEvent):
    """Position update event."""
    position_id: UUID = field(default_factory=uuid4)
    pair: str = ""
    side: Literal["long", "short"] = "long"
    quantity: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "position_id": str(self.position_id),
            "pair": self.pair,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
        })
        return base