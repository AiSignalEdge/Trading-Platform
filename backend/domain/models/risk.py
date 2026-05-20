"""
Risk Domain Model - Section 9 and Section 22 from PLAN-v2.md

Includes risk limits, circuit breakers, and risk check results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RegimeType(Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"


@dataclass
class RiskLimits:
    """Risk limits configuration - Section 22."""
    # Portfolio-level
    max_portfolio_drawdown_pct: float = 20.0
    daily_loss_limit_pct: float = 5.0
    max_leverage: float = 3.0

    # Position-level
    max_position_size_pct: float = 20.0
    max_open_positions: int = 10
    max_pairs_per_strategy: int = 5

    # Risk per trade
    max_risk_per_trade_pct: float = 2.0

    # Correlation
    max_strategy_correlation: float = 0.7

    # Circuit breaker
    circuit_breaker_consecutive_losses: int = 5

    # Stop loss defaults
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 6.0

    def to_dict(self) -> dict:
        return {
            "max_portfolio_drawdown_pct": self.max_portfolio_drawdown_pct,
            "daily_loss_limit_pct": self.daily_loss_limit_pct,
            "max_leverage": self.max_leverage,
            "max_position_size_pct": self.max_position_size_pct,
            "max_open_positions": self.max_open_positions,
            "max_pairs_per_strategy": self.max_pairs_per_strategy,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            "max_strategy_correlation": self.max_strategy_correlation,
            "circuit_breaker_consecutive_losses": self.circuit_breaker_consecutive_losses,
            "default_stop_loss_pct": self.default_stop_loss_pct,
            "default_take_profit_pct": self.default_take_profit_pct,
        }


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    approved: bool = True
    risk_level: RiskLevel = RiskLevel.LOW
    reason: Optional[str] = None
    adjustment_applied: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "adjustment_applied": self.adjustment_applied,
        }


@dataclass
class RiskExposure:
    """Current risk exposure across portfolio."""
    total_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    net_exposure: float = 0.0
    correlation_score: float = 0.0
    volatility_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_exposure": self.total_exposure,
            "long_exposure": self.long_exposure,
            "short_exposure": self.short_exposure,
            "net_exposure": self.net_exposure,
            "correlation_score": self.correlation_score,
            "volatility_score": self.volatility_score,
        }


@dataclass
class CircuitBreakerStatus:
    """Circuit breaker state."""
    consecutive_losses: int = 0
    is_triggered: bool = False
    triggered_at: Optional[datetime] = None
    pause_until: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "consecutive_losses": self.consecutive_losses,
            "is_triggered": self.is_triggered,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
        }

    def record_loss(self) -> None:
        self.consecutive_losses += 1
        if self.consecutive_losses >= 5:  # Default threshold
            self.is_triggered = True
            self.triggered_at = datetime.utcnow()

    def record_win(self) -> None:
        self.consecutive_losses = 0
        self.is_triggered = False

    def reset(self) -> None:
        self.consecutive_losses = 0
        self.is_triggered = False
        self.triggered_at = None
        self.pause_until = None


@dataclass
class MarketRegime:
    """Market regime state."""
    pair: str = ""
    timeframe: str = ""
    regime: RegimeType = RegimeType.RANGING
    trend_strength: float = 0.0
    volatility_rank: float = 0.0
    analyzed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "timeframe": self.timeframe,
            "regime": self.regime.value,
            "trend_strength": self.trend_strength,
            "volatility_rank": self.volatility_rank,
            "analyzed_at": self.analyzed_at.isoformat(),
        }