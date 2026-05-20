"""
Signal Framework — Event-driven signal model with indicator registry.
Signals are generated from indicators, then consumed by the OMS or backtester.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import talib

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """A trading signal with metadata."""

    timestamp: datetime
    symbol: str
    direction: str          # 'long', 'short', 'neutral'
    strength: float         # 0–1 confidence score
    price: float           # price at signal time
    indicators: dict        # snapshot of indicator values that generated it
    strategy: str
    metadata: dict = field(default_factory=dict)

    def is_active(self, max_age_seconds: int = 3600) -> bool:
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age < max_age_seconds

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.signal_strength,
            "price": self.price,
            "indicators": self.indicators,
            "strategy": self.strategy,
            "metadata": self.metadata,
        }


@dataclass
class IndicatorConfig:
    name: str
    params: dict = field(default_factory=dict)
    timeframe: str = "1h"


class BaseStrategy(ABC):
    """Abstract base for any strategy that generates signals."""

    name: str = "BaseStrategy"

    def __init__(self, config: dict):
        self.config = config
        self.indicators: dict = {}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute indicators on OHLCV DataFrame. Return df with new columns."""
        ...

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """Generate signals from indicator DataFrame."""
        ...

    def warmup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run indicators to prime values (handle NaN at start)."""
        return self.compute(df)


class MACrossStrategy(BaseStrategy):
    """Moving Average Crossover."""

    name = "ma_cross"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"].values
        fast = int(self.config.get("fast_period", 10))
        slow = int(self.config.get("slow_period", 30))
        df["ma_fast"] = talib.SMA(close, fast)
        df["ma_slow"] = talib.SMA(close, slow)
        df["ma_signal"] = np.where(df["ma_fast"] > df["ma_slow"], 1, -1)
        return df

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i in range(1, len(df)):
            prev_signal = df["ma_signal"].iloc[i - 1]
            curr_signal = df["ma_signal"].iloc[i]

            if curr_signal == 1 and prev_signal == -1:
                direction = "long"
                strength = 0.7
            elif curr_signal == -1 and prev_signal == 1:
                direction = "short"
                strength = 0.7
            else:
                direction = "neutral"
                strength = 0.0

            if direction != "neutral":
                signals.append(Signal(
                    timestamp=df.index[i].to_pydatetime() if hasattr(df.index[i], 'to_pydatetime') else datetime.now(timezone.utc),
                    symbol=df["symbol"].iloc[i] if "symbol" in df.columns else self.config.get("symbol", "UNKNOWN"),
                    direction=direction,
                    strength=strength,
                    price=df["close"].iloc[i],
                    indicators={
                        "ma_fast": df["ma_fast"].iloc[i],
                        "ma_slow": df["ma_slow"].iloc[i],
                        "spread": float(df["ma_fast"].iloc[i] - df["ma_slow"].iloc[i]),
                    },
                    strategy=self.name,
                ))
        return signals


class RSIStrategy(BaseStrategy):
    """RSI mean-reversion strategy."""

    name = "rsi"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"].values
        period = int(self.config.get("period", 14))
        df["rsi"] = talib.RSI(close, period)
        return df

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        oversold = float(self.config.get("oversold", 30))
        overbought = float(self.config.get("overbought", 70))

        for i in range(1, len(df)):
            rsi_val = df["rsi"].iloc[i]
            prev_rsi = df["rsi"].iloc[i - 1]

            if prev_rsi < oversold and rsi_val >= oversold:
                direction = "long"
                strength = min(1.0, (rsi_val - oversold) / 30)
            elif prev_rsi > overbought and rsi_val <= overbought:
                direction = "short"
                strength = min(1.0, (overbought - rsi_val) / 30)
            else:
                continue

            signals.append(Signal(
                timestamp=df.index[i].to_pydatetime() if hasattr(df.index[i], 'to_pydatetime') else datetime.now(timezone.utc),
                symbol=df["symbol"].iloc[i] if "symbol" in df.columns else self.config.get("symbol", "UNKNOWN"),
                direction=direction,
                strength=strength,
                price=df["close"].iloc[i],
                indicators={"rsi": rsi_val},
                strategy=self.name,
            ))
        return signals


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands breakout strategy."""

    name = "bollinger"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"].values
        period = int(self.config.get("period", 20))
        nb_dev = float(self.config.get("nb_dev", 2.0))
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(
            close, period, nbdevup=nb_dev, nbdevdn=nb_dev
        )
        df["bb_width"] = df["bb_upper"] - df["bb_lower"]
        return df

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["bb_upper"].iloc[i]:
                signals.append(Signal(
                    timestamp=df.index[i].to_pydatetime() if hasattr(df.index[i], 'to_pydatetime') else datetime.now(timezone.utc),
                    symbol=df["symbol"].iloc[i] if "symbol" in df.columns else self.config.get("symbol", "UNKNOWN"),
                    direction="long",
                    strength=0.8,
                    price=df["close"].iloc[i],
                    indicators={
                        "bb_upper": df["bb_upper"].iloc[i],
                        "bb_lower": df["bb_lower"].iloc[i],
                        "bb_width": df["bb_width"].iloc[i],
                    },
                    strategy=self.name,
                ))
            elif df["close"].iloc[i] < df["bb_lower"].iloc[i]:
                signals.append(Signal(
                    timestamp=df.index[i].to_pydatetime() if hasattr(df.index[i], 'to_pydatetime') else datetime.now(timezone.utc),
                    symbol=df["symbol"].iloc[i] if "symbol" in df.columns else self.config.get("symbol", "UNKNOWN"),
                    direction="short",
                    strength=0.8,
                    price=df["close"].iloc[i],
                    indicators={
                        "bb_upper": df["bb_upper"].iloc[i],
                        "bb_lower": df["bb_lower"].iloc[i],
                        "bb_width": df["bb_width"].iloc[i],
                    },
                    strategy=self.name,
                ))
        return signals


class MACDStrategy(BaseStrategy):
    """MACD momentum strategy."""

    name = "macd"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"].values
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(close)
        return df

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i in range(1, len(df)):
            curr_hist = df["macd_hist"].iloc[i]
            prev_hist = df["macd_hist"].iloc[i - 1]

            if prev_hist < 0 and curr_hist >= 0:
                direction, strength = "long", 0.75
            elif prev_hist > 0 and curr_hist <= 0:
                direction, strength = "short", 0.75
            else:
                continue

            signals.append(Signal(
                timestamp=df.index[i].to_pydatetime() if hasattr(df.index[i], 'to_pydatetime') else datetime.now(timezone.utc),
                symbol=df["symbol"].iloc[i] if "symbol" in df.columns else self.config.get("symbol", "UNKNOWN"),
                direction=direction,
                strength=strength,
                price=df["close"].iloc[i],
                indicators={
                    "macd": df["macd"].iloc[i],
                    "macd_signal": df["macd_signal"].iloc[i],
                    "macd_hist": curr_hist,
                },
                strategy=self.name,
            ))
        return signals


# ─── Indicator Registry ─────────────────────────────────────────────────────

_registry: dict[str, type[BaseStrategy]] = {}


def register_strategy(cls: type[BaseStrategy]):
    _registry[cls.name] = cls
    return cls


def get_strategy(name: str) -> type[BaseStrategy]:
    if name in _registry:
        return _registry[name]
    raise ValueError(f"Unknown strategy: {name}. Available: {list(_registry.keys())}")


# Register built-ins
for _cls in [MACrossStrategy, RSIStrategy, BollingerBandsStrategy, MACDStrategy]:
    register_strategy(_cls)