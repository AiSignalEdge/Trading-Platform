"""Strategy registry — maps strategy name to concrete strategy class."""

from typing import Optional


class BaseStrategy:
    """Abstract base for all strategies."""

    def __init__(self, candles: dict, **params):
        self.candles = candles
        self.params = params

    def generate_signals(self, close: "np.ndarray") -> tuple["np.ndarray", "np.ndarray"]:
        raise NotImplementedError


class SMACross(BaseStrategy):
    """Simple moving average crossover."""

    def __init__(self, candles: dict, sma_short: int = 10, sma_long: int = 30, **kwargs):
        super().__init__(candles, **kwargs)
        self.sma_short = sma_short
        self.sma_long = sma_long

    def generate_signals(self, close: "np.ndarray"):
        import talib
        import numpy as np

        ma_fast = talib.SMA(close, self.sma_short)
        ma_slow = talib.SMA(close, self.sma_long)

        entries = (ma_fast > ma_slow) & (np.roll(ma_fast, 1) <= ma_slow)
        exits = (ma_fast < ma_slow) & (np.roll(ma_fast, 1) >= ma_slow)
        entries[0] = False
        exits[0] = False

        return entries, exits


class TrendFollowingStrategy(BaseStrategy):
    """Trend-following with EMA filter."""

    def __init__(self, candles: dict, ema_fast: int = 12, ema_slow: int = 26, ema_filter: int = 50, **kwargs):
        super().__init__(candles, **kwargs)
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_filter = ema_filter

    def generate_signals(self, close: "np.ndarray"):
        import talib
        import numpy as np

        ema_f = talib.EMA(close, self.ema_fast)
        ema_s = talib.EMA(close, self.ema_slow)
        ema_filter = talib.EMA(close, self.ema_filter)

        long_cond = (ema_f > ema_s) & (ema_f > ema_filter)
        entries = long_cond & (np.roll(long_cond, 1) == False)
        exits = (ema_f < ema_s)
        entries[0] = False
        exits[0] = False

        return entries, exits


STRATEGY_REGISTRY = {
    "ma_cross": SMACross,
    "trend_following": TrendFollowingStrategy,
}


def strategy_from_dict(name: str, extra_data: Optional[dict] = None) -> BaseStrategy:
    """Factory: instantiate a strategy by name with params from extra_data."""
    strategy_cls = STRATEGY_REGISTRY.get(name, SMACross)
    params = (extra_data or {}).get("strategy_params", {})
    return strategy_cls({}, **params)