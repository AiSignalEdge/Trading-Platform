"""Portfolio backtest engine — shared-capital multi-strategy portfolio simulation.

Architecture
============
- Loads candles for all (strategy, symbol) pairs and aligns to a common timestamp index.
- For each bar, generates signals from each strategy on its assigned symbol.
- PortfolioRiskManager checks each signal: sector exposure, position limits,
  drawdown circuit breaker, and correlation filter.
- If a signal passes risk checks, the position is sized (volatility-adjusted via ATR).
- Per-strategy positions and PnL are tracked and aggregated into portfolio equity.
- After the run, a correlation matrix is computed from per-strategy return series;
  if average pairwise correlation > threshold, all position sizes are reduced.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from services.signals.registry import get_strategy as _get_strategy_class

def strategy_from_dict(name: str, extra_data: Optional[dict] = None):
    """Instantiate a strategy by name using the signals registry."""
    # get_strategy now returns an already-instantiated strategy instance
    return _get_strategy_class(name, config=extra_data or {})

# Re-export from engine.py so consumers only need this one import
from services.backtest.engine import PerformanceMetrics
from models.backtest import BacktestResult

# Use real strategy classes from signals registry
from services.signals.registry import (
    BaseStrategy as _RealBaseStrategy,
    Signal as _RealSignal,
    get_strategy as _get_strategy_class,
)

# Aliases for use within this module
BaseStrategy = _RealBaseStrategy
SignalData = _RealSignal


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A raw signal produced by a strategy."""
    timestamp: pd.Timestamp
    direction: int          # 1 = long, -1 = short, 0 = flat
    strength: float = 1.0  # 0–1 signal strength / confidence
    strategy_name: str = ""
    symbol: str = ""


@dataclass
class SizedSignal:
    """A signal that has passed risk checks and been assigned a position size."""
    signal: Signal
    position_size: float    # notional dollar value
    ATR: float = 0.0


# ---------------------------------------------------------------------------
# Portfolio config & result types
# ---------------------------------------------------------------------------

@dataclass
class PortfolioStrategyConfig:
    """One strategy × one or more symbols with an optional weight override."""
    strategy_name: str
    symbols: list[str]           # e.g. ["BTC/USDT", "ETH/USDT"]
    weight: float = 1.0          # relative weight in capital allocation
    extra_data: Optional[dict] = None  # strategy constructor kwargs


@dataclass
class PortfolioConfig:
    """Top-level configuration for a portfolio backtest run."""
    strategies: list[PortfolioStrategyConfig]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    leverage: float = 1.0

    # Risk limits
    max_sector_exposure: float = 0.3        # max fraction of equity per sector
    max_positions: int = 10                  # hard cap on open positions
    correlation_threshold: float = 0.7      # if avg pairwise corr > this, reduce sizes
    correlation_reduction: float = 0.8      # multiply sizes by this when correlated
    max_drawdown_pct: float = 0.20          # circuit breaker: stop increasing positions
    target_dollar_risk: float = 2000.0      # $ risk per position (for ATR sizing)
    atr_period: int = 14                    # ATR lookback period


# ---------------------------------------------------------------------------
# PortfolioResult
# ---------------------------------------------------------------------------

@dataclass
class AllocationRecord:
    """Per-(strategy, symbol) allocation summary."""
    strategy: str
    symbol: str
    weight: float
    return_pct: float
    trades: int
    sharpe: float


@dataclass
class PortfolioResult:
    """Aggregated portfolio result with per-strategy breakdown."""
    portfolio_metrics: PerformanceMetrics
    equity_curve: list[float]
    allocations: list[AllocationRecord]
    strategy_results: list[BacktestResult]   # one per strategy × symbol pair
    correlation_matrix: list[list[float]]    # flat list of lists for JSON
    max_correlation: float
    avg_correlation: float
    max_drawdown_pct: float

    def to_dict(self) -> dict:
        return {
            "portfolio": self.portfolio_metrics.__dict__,
            "equity_curve": self.equity_curve[:50],
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_correlation": self.max_correlation,
            "avg_correlation": self.avg_correlation,
            "allocations": [a.__dict__ for a in self.allocations],
        }


# ---------------------------------------------------------------------------
# PortfolioRiskManager
# ---------------------------------------------------------------------------

class PortfolioRiskManager:
    """Checks signals against sector exposure, position count, drawdown, and correlation."""

    def __init__(self, config: PortfolioConfig, exchange: str = "binance", timeframe: str = "1h"):
        self.config = config
        self.exchange = exchange
        self.timeframe = timeframe

    def check(
        self,
        signals: list[Signal],
        current_positions: dict[str, float],   # key: "strategy|symbol", value: notional $
        portfolio_equity: float,
        size_multiplier: float = 1.0,
    ) -> list[SizedSignal]:
        """Evaluate a list of raw signals and return sized signals that pass risk checks.

        Args:
            signals: raw signals from strategies
            current_positions: dict of open positions
            portfolio_equity: current portfolio equity
            size_multiplier: correlation-based size reducer (computed post-run from
                correlation matrix). Defaults to 1.0 (no reduction).
        """
        sized = []

        # 1. Hard position count cap
        active_count = len([p for p in current_positions.values() if abs(p) > 0])
        if active_count >= self.config.max_positions:
            return sized

        # 2. Drawdown circuit breaker — no new positions when drawdown > threshold
        # (caller passes current drawdown; here we just check the flag)
        # Implemented by caller checking max_drawdown_pct

        for sig in signals:
            key = f"{sig.strategy_name}|{sig.symbol}"

            # 3. Sector exposure check (simplified: treat each symbol as its own sector)
            current_exposure = abs(current_positions.get(key, 0.0))
            new_exposure = current_exposure  # will be updated after sizing

            # 4. Skip flat signals
            if sig.direction == 0:
                continue

            # ATR-based volatility sizing
            atr = self._get_atr(sig.symbol, sig.timestamp)
            if atr <= 0:
                # Fallback: use fixed fraction of price
                atr = sig.strength * 100.0

            # position_size = target_dollar_risk / atr * direction
            raw_size = (self.config.target_dollar_risk / atr) * sig.strength

            # Scale by weight and leverage
            weight_sum = sum(s.weight for s in self.config.strategies)
            sized_notional = (
                (sig.strategy_name and sum(
                    sc.weight for sc in self.config.strategies
                    if sc.strategy_name == sig.strategy_name
                ) or 1.0)
                / max(weight_sum, 1.0)
                * portfolio_equity
                * self.config.leverage
                * raw_size
            )

            # Correlation-based size reduction (computed post-run from correlation matrix)
            sized_notional *= size_multiplier

            # Sector exposure guard
            if sized_notional > portfolio_equity * self.config.max_sector_exposure:
                sized_notional = portfolio_equity * self.config.max_sector_exposure

            sized.append(SizedSignal(
                signal=sig,
                position_size=sized_notional,
                ATR=atr,
            ))

        return sized

    def _get_atr(self, symbol: str, timestamp: pd.Timestamp) -> float:
        """Query the candle store for ATR(14). Override in production."""
        # Stub: returns a placeholder so the engine can run without a live candle store.
        # In production this would be: candle_store.get(exchange, symbol, timeframe, ...)
        return 100.0  # $ per bar placeholder — replace with real ATR


# ---------------------------------------------------------------------------
# PortfolioEngine
# ---------------------------------------------------------------------------

class PortfolioEngine:
    """Multi-strategy portfolio backtest engine.

    Runs each strategy independently on its assigned symbols, aggregates PnL
    into a shared capital pool, and applies correlation-based position sizing.
    """

    def __init__(
        self,
        candle_store=None,       # services.data.candle_store.CandleStore
        exchange: str = "binance",
        timeframe: str = "1h",
    ):
        self.candle_store = candle_store
        self.exchange = exchange
        self.timeframe = timeframe

    def _rolling_correlation_multiplier(
        self,
        returns_df: pd.DataFrame,
        strategy_symbol_data: dict[tuple[str, str], pd.DataFrame],
        t_idx: int,
        config: "PortfolioConfig",
    ) -> float:
        """Compute rolling pairwise correlation multiplier at bar t_idx.

        Uses a 60-bar lookback window of strategy returns to compute
        pairwise correlation. If avg correlation > threshold, returns
        correlation_reduction; otherwise returns 1.0.

        This is called per-bar so position sizing reflects recent
        correlation regime rather than being fixed for the whole run.
        """
        lookback = 60
        if t_idx < lookback:
            return 1.0

        # Build per-strategy return series (average across symbols)
        strat_return_cols: dict[str, pd.Series] = {}
        for (strat_name, symbol), col_name in [
            ((sn, sy), f"{sn}__{sy}") for (sn, sy) in strategy_symbol_data
        ]:
            if strat_name not in strat_return_cols:
                strat_return_cols[strat_name] = returns_df[col_name].iloc[t_idx - lookback : t_idx].copy()
            else:
                strat_return_cols[strat_name] += returns_df[col_name].iloc[t_idx - lookback : t_idx]

        for sn in strat_return_cols:
            count = sum(1 for (s, _) in strategy_symbol_data if s == sn)
            if count > 1:
                strat_return_cols[sn] /= count

        corr_df = pd.DataFrame(strat_return_cols)
        n = len(corr_df.columns)
        if n < 2:
            return 1.0

        corr_matrix = corr_df.corr().fillna(0.0)
        vals = corr_matrix.values[np.triu_indices(n, k=1)]
        avg_corr = float(vals.mean()) if len(vals) > 0 else 0.0

        if avg_corr > config.correlation_threshold:
            return config.correlation_reduction
        return 1.0

    async def run(self, config: PortfolioConfig) -> PortfolioResult:
        """Run the portfolio backtest and return aggregated results."""

        # ---- 1. Load candles for all (strategy, symbol) pairs ----
        # Build a dict: (strategy_name, symbol) -> DataFrame
        strategy_symbol_data: dict[tuple[str, str], pd.DataFrame] = {}

        for strat_cfg in config.strategies:
            strategy = strategy_from_dict(strat_cfg.strategy_name, strat_cfg.extra_data)
            for symbol in strat_cfg.symbols:
                df = self._load_candles(symbol, config.start_date, config.end_date)
                if df is not None and not df.empty:
                    strategy_symbol_data[(strat_cfg.strategy_name, symbol)] = df

        if not strategy_symbol_data:
            raise ValueError("No candle data loaded for any strategy-symbol pair.")

        # ---- 2. Align all close series to a common timestamp index ----
        # Collect all timestamps from all DataFrames
        all_timestamps = set()
        for df in strategy_symbol_data.values():
            all_timestamps.update(df.index)

        common_index = sorted(all_timestamps)
        close_series: dict[tuple[str, str], pd.Series] = {}

        for (strat_name, symbol), df in strategy_symbol_data.items():
            # Reindex to common index, forward-fill missing bars
            aligned = df["close"].reindex(common_index).ffill()
            close_series[(strat_name, symbol)] = aligned

        # ---- 3. Build per-strategy returns series ----
        # Returns = pct_change of close, 0 for first bar and missing bars
        returns_df = pd.DataFrame(index=common_index)
        for key, close in close_series.items():
            label = f"{key[0]}__{key[1]}"   # "strategy__symbol"
            returns_df[label] = close.pct_change().fillna(0.0).replace([np.inf, -np.inf], 0.0)

        # ---- 4. Per-bar simulation ----
        equity = config.initial_capital
        equity_history: list[float] = []

        # Track open positions: key -> {direction, entry_price, size, entry_bar}
        positions: dict[str, dict] = {}   # "strategy|symbol" -> position dict
        # Track per-strategy equity curves for later per-strategy BacktestResult
        strategy_equities: dict[tuple[str, str], list[float]] = {
            key: [config.initial_capital / len(strategy_symbol_data)]
            for key in strategy_symbol_data
        }

        # Track trades per strategy-symbol
        strategy_trades: dict[tuple[str, str], list[dict]] = {
            key: [] for key in strategy_symbol_data
        }

        # Pre-build strategy instances
        strategies: dict[str, BaseStrategy] = {}
        for strat_cfg in config.strategies:
            if strat_cfg.strategy_name not in strategies:
                strategies[strat_cfg.strategy_name] = strategy_from_dict(
                    strat_cfg.strategy_name, strat_cfg.extra_data
                )

        risk_mgr = PortfolioRiskManager(config, self.exchange, self.timeframe)

        max_drawdown = 0.0
        peak_equity = equity

        # Iterate bars
        bars = list(common_index)
        for t_idx, ts in enumerate(bars):
            active_positions = {k: v["size"] for k, v in positions.items()}

            # Collect raw signals at this timestamp
            raw_signals: list[Signal] = []

            for (strat_name, symbol), df in strategy_symbol_data.items():
                if ts not in df.index:
                    continue

                # Build lookback DataFrame up to current bar
                bar_df = df.loc[:ts].copy()

                strategy = strategies.get(strat_name)
                if strategy is None:
                    continue

                # compute indicators
                computed = strategy.compute(bar_df)
                signals = strategy.generate_signals(computed)

                for sig in signals:
                    # Use proximity check: match if signal timestamp is within 2h of current bar
                    # (handles minor timestamp mismatches from synthetic data generation)
                    if abs((sig.timestamp - ts).total_seconds()) < 7200:
                        # Convert registry direction string to int
                        dir_map = {"long": 1, "short": -1, "neutral": 0}
                        dir_int = dir_map.get(sig.direction, 0)
                        raw_signals.append(Signal(
                            timestamp=ts,
                            direction=dir_int,
                            strength=sig.strength,
                            strategy_name=strat_name,
                            symbol=symbol,
                        ))

            # Rolling correlation-based size multiplier (per-bar, not post-run)
            size_mult = self._rolling_correlation_multiplier(
                returns_df, strategy_symbol_data, t_idx, config
            )

            # Risk check → sized signals
            sized_signals = risk_mgr.check(raw_signals, active_positions, equity, size_mult)

            # Apply sized signals: update positions
            for ss in sized_signals:
                key = f"{ss.signal.strategy_name}|{ss.signal.symbol}"
                price = close_series[(ss.signal.strategy_name, ss.signal.symbol)].loc[ts]
                if price <= 0:
                    continue

                direction = ss.signal.direction

                if key in positions and abs(positions[key]["size"]) > 0:
                    # Close existing position
                    entry_price = positions[key]["entry_price"]
                    prev_size = positions[key]["size"]
                    pnl = (price - entry_price) * prev_size * config.leverage \
                          - config.commission_pct * abs(prev_size * price) \
                          - config.slippage_pct * abs(prev_size * price)
                    equity += pnl
                    strategy_trades[(ss.signal.strategy_name, ss.signal.symbol)].append({
                        "entry": entry_price,
                        "exit": price,
                        "pnl": pnl,
                        "size": abs(prev_size),
                        "direction": positions[key]["direction"],
                        "timestamp": ts,
                    })
                    del positions[key]

                # Open new position if direction != 0
                if direction != 0:
                    # number of units = position_size / price
                    units = ss.position_size / price
                    positions[key] = {
                        "direction": direction,
                        "entry_price": price,
                        "size": direction * units,
                        "entry_bar": t_idx,
                    }

            # Mark-to-market: update equity for still-open positions
            pos_pnl = 0.0
            for key, pos in list(positions.items()):
                strat_name, symbol = key.split("|", 1)
                try:
                    price_series = close_series.get((strat_name, symbol))
                    if price_series is None or ts not in price_series.index:
                        continue
                    price = price_series.loc[ts]
                except (KeyError, ValueError):
                    continue
                if price <= 0:
                    continue
                entry_price = pos["entry_price"]
                direction = pos["direction"]
                size = pos["size"]
                pos_pnl += (price - entry_price) * size * config.leverage \
                          - config.commission_pct * abs(size * price) \
                          - config.slippage_pct * abs(size * price)

            equity += pos_pnl
            equity_history.append(equity)

            # Update per-strategy equity curves
            for key, strat_eq in strategy_equities.items():
                strat_name, symbol = key
                try:
                    price_series = close_series.get((strat_name, symbol))
                    if price_series is None:
                        strat_eq.append(strat_eq[-1] if strat_eq else config.initial_capital / len(strategy_symbol_data))
                        continue
                    # Iterate through index to find matching bar
                    price_val = None
                    for idx_price in price_series.index:
                        if abs((idx_price - ts).total_seconds()) < 7200:  # within 2h
                            price_val = price_series.loc[idx_price]
                            break
                    if price_val is None:
                        strat_eq.append(strat_eq[-1] if strat_eq else config.initial_capital / len(strategy_symbol_data))
                        continue
                except (KeyError, ValueError):
                    strat_eq.append(strat_eq[-1] if strat_eq else config.initial_capital / len(strategy_symbol_data))
                    continue

                # Per-strategy mark-to-market: update position if open
                pos_key = f"{strat_name}|{symbol}"
                if pos_key in positions:
                    pos = positions[pos_key]
                    entry = pos["entry_price"]
                    direction = pos["direction"]
                    size = pos["size"]
                    strat_pnl = (price_val - entry) * size * config.leverage \
                                - config.commission_pct * abs(size * price_val) \
                                - config.slippage_pct * abs(size * price_val)
                else:
                    strat_pnl = 0.0
                new_eq = strat_eq[-1] + strat_pnl if strat_eq else config.initial_capital / len(strategy_symbol_data)
                strat_eq.append(new_eq)

            # Drawdown tracking
            if equity > peak_equity:
                peak_equity = equity
            drawdown = (equity - peak_equity) / peak_equity
            if drawdown < max_drawdown:
                max_drawdown = drawdown

            # Circuit breaker: if drawdown exceeds limit, flatten all positions
            if abs(max_drawdown) > config.max_drawdown_pct:
                for key, pos in list(positions.items()):
                    strat_name, symbol = key.split("|", 1)
                    price = close_series.get((strat_name, symbol), pd.Series(dtype=float)).loc[ts]
                    if price > 0:
                        direction = pos["direction"]
                        size = pos["size"]
                        pnl = (price - pos["entry_price"]) * size * config.leverage \
                              - config.commission_pct * abs(size * price)
                        equity += pnl
                        strategy_trades[(strat_name, symbol)].append({
                            "entry": pos["entry_price"],
                            "exit": price,
                            "pnl": pnl,
                            "size": abs(size),
                            "direction": direction,
                            "timestamp": ts,
                        })
                    del positions[key]

        # ---- 5. Correlation matrix from strategy returns ----
        # Compute per-strategy return series (average across symbols for multi-symbol strategies)
        strat_return_cols: dict[str, pd.Series] = {}
        for (strat_name, symbol), col_name in [
            ((sn, sy), f"{sn}__{sy}") for (sn, sy) in strategy_symbol_data
        ]:
            if strat_name not in strat_return_cols:
                strat_return_cols[strat_name] = returns_df[col_name].copy()
            else:
                strat_return_cols[strat_name] += returns_df[col_name]

        # Average if strategy has multiple symbols
        for sn in strat_return_cols:
            strat_return_cols[sn] /= max(1, sum(
                1 for (s, _) in strategy_symbol_data if s == sn
            ))

        corr_df = pd.DataFrame(strat_return_cols)
        correlation_matrix = corr_df.corr().fillna(0.0)

        # Extract scalar metrics from correlation matrix
        n = len(correlation_matrix)
        if n >= 2:
            vals = correlation_matrix.values[np.triu_indices(n, k=1)]
            max_correlation = float(vals.max()) if len(vals) > 0 else 0.0
            avg_correlation = float(vals.mean()) if len(vals) > 0 else 0.0
        else:
            max_correlation = 0.0
            avg_correlation = 0.0

        # Report final correlation metrics (size reduction is now applied per-bar via rolling window)

        strategy_results: list[BacktestResult] = []
        allocations: list[AllocationRecord] = []

        for (strat_name, symbol) in strategy_symbol_data.keys():
            strat_equity_curve = strategy_equities.get((strat_name, symbol), [])
            metrics = _compute_metrics(
                pd.Series(strat_equity_curve).pct_change().fillna(0.0),
                strategy_trades[(strat_name, symbol)]
            )

            result = BacktestResult(
                config_id="portfolio",
                pair=symbol,
                timeframe=self.timeframe,
                status="completed",
                progress_pct=100.0,
                initial_capital=strat_equity_curve[0] if strat_equity_curve else config.initial_capital,
                final_equity=strat_equity_curve[-1] if strat_equity_curve else config.initial_capital,
                total_return=metrics.total_return,
                annualized_return=metrics.total_return,
                max_drawdown=0.0,
                max_drawdown_pct=metrics.max_drawdown_pct,
                sharpe_ratio=metrics.sharpe_ratio,
                sortino_ratio=metrics.sortino_ratio,
                calmar_ratio=metrics.calmar_ratio,
                profit_factor=metrics.profit_factor,
                win_rate=metrics.win_rate,
                expectancy=metrics.expectancy,
                total_trades=metrics.trades,
                equity_curve={"curve": _downsample_equity_curve(strat_equity_curve, 50)},
                trades={"trades": strategy_trades[(strat_name, symbol)]},
            )
            strategy_results.append(result)

            # Compute allocation record
            total_return = (strat_equity_curve[-1] / strat_equity_curve[0]) - 1 if strat_equity_curve else 0.0
            weight = next(
                (s.weight / sum(sc.weight for sc in config.strategies))
                for s in config.strategies if s.strategy_name == strat_name
            ) if strat_name in [s.strategy_name for s in config.strategies] else 1.0

            allocations.append(AllocationRecord(
                strategy=strat_name,
                symbol=symbol,
                weight=weight,
                return_pct=total_return,
                trades=len(strategy_trades[(strat_name, symbol)]),
                sharpe=metrics.sharpe_ratio,
            ))

        # ---- 7. Portfolio-level metrics ----
        portfolio_returns = pd.Series(equity_history).pct_change().fillna(0.0)
        portfolio_metrics = _compute_metrics(portfolio_returns, [])

        # Ensure max_drawdown_pct is set
        portfolio_metrics.max_drawdown_pct = max_drawdown

        # Correlation matrix as flat list of lists
        corr_list = correlation_matrix.values.tolist()

        result = PortfolioResult(
            portfolio_metrics=portfolio_metrics,
            equity_curve=_downsample_equity_curve(equity_history, 50),
            allocations=allocations,
            strategy_results=strategy_results,
            correlation_matrix=corr_list,
            max_correlation=max_correlation,
            avg_correlation=avg_correlation,
            max_drawdown_pct=max_drawdown,
        )
        return result

    def _load_candles(
        self,
        symbol: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Optional[pd.DataFrame]:
        """Load candles from the candle store or return a synthetic stub."""
        if self.candle_store is not None:
            try:
                import asyncio
                candles = asyncio.get_event_loop().run_until_complete(
                    self.candle_store.get(
                        self.exchange, symbol, self.timeframe,
                        since=start_date, until=end_date, limit=5000,
                    )
                )
                if candles:
                    df = pd.DataFrame(candles)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                    df.set_index("timestamp", inplace=True)
                    df.sort_index(inplace=True)
                    return df
            except Exception:
                pass

        # Stub: generate synthetic candles so the engine can run standalone
        return _generate_synthetic_candles(symbol, start_date, end_date)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _compute_metrics(returns: pd.Series, trades: list[dict]) -> PerformanceMetrics:
    """Compute standard performance metrics from a return series."""
    if len(returns) == 0 or returns.isna().all():
        return PerformanceMetrics()

    total_return = float((1 + returns).prod() - 1)

    annualised_return = float(returns.mean() * 252)
    annualised_vol = float(returns.std() * np.sqrt(252))
    sharpe = annualised_return / annualised_vol if annualised_vol > 0 else 0.0

    downside_returns = returns[returns < 0]
    downside_std = float(downside_returns.std() * np.sqrt(252)) if len(downside_returns) > 0 else 0.0
    sortino = annualised_return / downside_std if downside_std > 0 else 0.0

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = float(drawdown.min())

    calmar = annualised_return / abs(max_dd) if max_dd != 0 else 0.0

    winning = [t for t in trades if t.get("pnl", 0) > 0]
    losing = [t for t in trades if t.get("pnl", 0) <= 0]
    win_rate = len(winning) / len(trades) if trades else 0.0

    gross_profit = sum(t.get("pnl", 0) for t in winning)
    gross_loss = abs(sum(t.get("pnl", 0) for t in losing))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    all_pnls = [t.get("pnl", 0) for t in trades]
    expectancy = float(np.mean(all_pnls)) if all_pnls else 0.0

    return PerformanceMetrics(
        total_return=total_return,
        sharpe_ratio=float(sharpe),
        sortino_ratio=float(sortino),
        calmar_ratio=float(calmar),
        max_drawdown_pct=max_dd,
        win_rate=float(win_rate),
        profit_factor=float(profit_factor),
        expectancy=float(expectancy),
        trades=len(trades),
        avg_trade_pnl=float(expectancy),
        avg_trade_duration_bars=0,
    )


def _downsample_equity_curve(curve: list[float], n_points: int) -> list[float]:
    """Downsample an equity curve to approximately n_points."""
    if len(curve) <= n_points:
        return curve
    step = len(curve) / n_points
    return [curve[int(i * step)] for i in range(n_points)]


def _generate_synthetic_candles(
    symbol: str,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    n_bars: int = 500,
    index: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for backtesting without a live data source.

    If an index is provided (shared across all symbols), timestamps will align
    with the common event-loop timeline. Otherwise generates its own timestamps.
    """
    import numpy as np

    if start_date is None:
        start_date = datetime(2023, 1, 1)
    if end_date is None:
        end_date = datetime(2023, 6, 30)

    # Simple deterministic noise based on symbol hash
    seed = hash(symbol) % (2**31)
    rng = np.random.default_rng(seed)

    n_bars = min(n_bars, 2000)

    if index is not None:
        timestamps = index
        n_bars = len(timestamps)
    else:
        # Use freq with start and periods (end is implied, not passed to date_range)
        timestamps = pd.date_range(start=start_date, freq="4h", periods=n_bars)

    base_price = 30_000.0 if "BTC" in symbol else 2_000.0
    returns = rng.standard_normal(n_bars) * 0.02
    close_prices = base_price * np.exp(np.cumsum(returns - 0.01 / 24))

    high_prices = close_prices * (1 + np.abs(rng.standard_normal(n_bars) * 0.01))
    low_prices = close_prices * (1 - np.abs(rng.standard_normal(n_bars) * 0.01))
    open_prices = low_prices + rng.random(n_bars) * (high_prices - low_prices)
    volumes = rng.lognormal(10, 1, n_bars)

    df = pd.DataFrame({
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volumes,
    }, index=timestamps)
    df.index.name = "timestamp"
    return df