"""
Strategy Domain Model - Section 4 from PLAN-v2.md
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class StrategyType(Enum):
    """Strategy classification types."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    GRID = "grid"
    ARBITRAGE = "arbitrage"
    MOON_PHASE = "moon_phase"
    BREAKOUT = "breakout"
    CUSTOM = "custom"


class AssetClass(Enum):
    """Asset class for strategy."""
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCKS = "stocks"
    COMMODITIES = "commodities"


@dataclass
class StrategyConfig:
    """Strategy configuration with parameters."""
    fast_period: int = 10
    slow_period: int = 20
    ma_type: str = "sma"
    direction: str = "both"
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_entry: int = 30
    rsi_exit: int = 70
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_threshold: float = 1.5
    grid_spacing_pct: float = 1.0
    num_levels: int = 10
    auto_rebalance: bool = True
    base_quantity: float = 0.0
    breakout_period: int = 20
    confirmation_bars: int = 2
    stop_pct: float = 2.0
    supertrend_period: int = 10
    supertrend_multiplier: float = 3.0
    vwap_period: int = 14
    deviation_threshold: float = 0.02
    session_start: str = "09:30"
    phase_sensitivity: float = 1.0
    entry_offset: float = 0.001
    exit_after_n: int = 5
    kelly_fraction: float = 0.5
    max_position_pct: float = 20.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    position_size_pct: float = 10.0


@dataclass
class Strategy:
    """Trading strategy domain model."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    author: str = ""
    version: int = 1
    strategy_type: StrategyType = StrategyType.MOMENTUM
    asset_class: AssetClass = AssetClass.CRYPTO
    pairs: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    parameters: dict = field(default_factory=dict)
    pine_script: str = ""
    tags: list[str] = field(default_factory=list)
    is_public: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    current_version_id: UUID = field(default_factory=uuid4)
    rating: float = 0.0
    backtest_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "strategy_type": self.strategy_type.value,
            "asset_class": self.asset_class.value,
            "pairs": self.pairs,
            "timeframes": self.timeframes,
            "parameters": self.parameters,
            "pine_script": self.pine_script,
            "tags": self.tags,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_version_id": str(self.current_version_id),
            "rating": self.rating,
            "backtest_count": self.backtest_count,
        }


@dataclass
class StrategyVersion:
    """Versioned snapshot of strategy parameters and code."""
    id: UUID = field(default_factory=uuid4)
    strategy_id: UUID = field(default_factory=uuid4)
    version: int = 1
    parameters: dict = field(default_factory=dict)
    pine_script: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    changelog: str = ""

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "strategy_id": str(self.strategy_id),
            "version": self.version,
            "parameters": self.parameters,
            "pine_script": self.pine_script,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "changelog": self.changelog,
        }