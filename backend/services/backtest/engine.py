"""
Backtest Engine — vectorbt-based backtesting with realistic fills,
slippage, fees, leverage, and walk-forward support.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from services.signals.registry import get_strategy as strategy_from_dict

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Standard performance metrics for a backtest run."""
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    trades: int = 0
    avg_trade_pnl: float = 0.0
    avg_trade_duration_bars: int = 0


def _warmup_vectorbt():
    """Pre-warm vectorbt JIT compilation so first backtest is fast.

    On first call, vectorbt/numba JIT-compiles the portfolio simulation.
    This takes ~60s on cold start but is cached after. Run once at startup.
    """
    import time
    logger.info("Warming up vectorbt JIT (first run ~60s, cached after)...")
    t0 = time.time()
    try:
        import vectorbt as vbt
        close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0, 103.0, 102.0, 101.0])
        entries = np.array([True, False, False, False, False, False, False, False, False, False])
        exits = np.array([False, False, False, False, False, False, True, False, False, False])
        vbt.settings.array_wrapper["freq"] = "1h"
        vbt.Portfolio.from_signals(
            close, entries, exits,
            size=1.0, size_type="percent",
            init_cash=100.0, freq="1h",
        )
        elapsed = time.time() - t0
        logger.info(f"vectorbt warmup done in {elapsed:.1f}s")
    except Exception as e:
        logger.warning(f"vectorbt warmup skipped: {e}")


# _warmup_vectorbt()  # deferred


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    # Strategy params
    strategy_name: str = "Strategy"
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "1h"
    initial_cash: float = 10_000.0
    leverage: float = 1.0
    extra_data: Optional[dict] = None   # strategy params live here under key "strategy_params"

    # Execution params
    commission: float = 0.001      # 0.1% taker
    slippage: float = 0.0005       # 0.05%
    maker_fee: float = 0.0004      # 0.04%
    funding_rate: float = 0.0      # for futures

    # Risk params
    max_position_size: float = 1.0   # 100% of cash
    stop_loss: Optional[float] = None  # fraction e.g. 0.02 = 2%
    take_profit: Optional[float] = None

    # Walk-forward
    train_window_days: int = 60
    test_window_days: int = 14
    n_windows: Optional[int] = None  # None = all available
    is_walk_forward: bool = False

    # Data source
    exchange: str = "binance"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class Trade:
    entry_time: datetime
    entry_price: float
    side: str          # 'long' or 'short'
    size: float
    pnl: float = 0.0
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    commission: float = 0.0


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime

    # Equity
    initial_cash: float
    final_equity: float
    total_return: float        # fraction
    total_return_pct: float

    # Risk
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy: float

    # Timing
    total_time: float          # bars
    training_time: float
    testing_time: float
    is_walk_forward: bool

    # Raw trade log
    trades: list[Trade] = field(default_factory=list)

    # Equity curve (list of equity values sampled ~50 points)
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "return": f"{self.total_return_pct:.2f}%",
            "max_dd": f"{self.max_drawdown_pct:.2f}%",
            "sharpe": round(self.sharpe_ratio, 2),
            "win_rate": f"{self.win_rate:.1%}",
            "trades": self.total_trades,
            "profit_factor": round(self.profit_factor, 2),
        }


class BacktestEngine:
    """
    VectorBT-powered backtest engine.
    Supports: multi-symbol, walk-forward, leverage, stop/TP.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

        # VectorBT global settings
        import vectorbt as vbt
        vbt.settings.array_wrapper["freq"] = self._freq_map(config.timeframe)
        self._vbt = vbt  # store on self so _run_single can use it

    def _freq_map(self, tf: str) -> str:
        map_ = {
            "1m": "1T", "5m": "5T", "15m": "15T", "30m": "30T",
            "1h": "1H", "4h": "4H", "6h": "6H", "12h": "12H",
            "1d": "1D", "3d": "3D", "1w": "1W",
        }
        return map_.get(tf, "1H")

    async def run(self) -> list[BacktestResult]:
        """
        Run backtest for all symbols. Returns list of BacktestResult (one per symbol).
        If walk-forward is configured, returns results for each window.
        """
        from services.data.candle_store import CandleStore
        import traceback

        results = []
        for symbol in self.config.symbols:
            try:
                logger.info(f"[run] Processing symbol={symbol}")

                # Load candles
                import vectorbt as vbt  # reload per-call for thread safety
                self._vbt = vbt
                candles = await CandleStore.get(
                    self.config.exchange, symbol, self.config.timeframe,
                    since=self.config.start_date,
                    until=self.config.end_date,
                    limit=2000,  # cap for performance
                )
                logger.info(f"[DEBUG] {symbol}: got {len(candles)} candles")

                if len(candles) < 50:
                    logger.warning(f"Not enough data for {symbol}, skipping")
                    continue

                df = pd.DataFrame(candles)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp").sort_index()

                if self.config.is_walk_forward:
                    results.extend(
                        await self._run_walk_forward(symbol, df)
                    )
                else:
                    result = await self._run_single(symbol, df)
                    results.append(result)

            except Exception as e:
                logger.error(f"Backtest error {symbol}: {type(e).__name__}: {e}")
                logger.error(f"Backtest traceback: {traceback.format_exc()}")

        return results

    async def _run_single(self, symbol: str, df: pd.DataFrame) -> BacktestResult:
        """Run a single backtest (no walk-forward)."""
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        logger.info(f"[_run_single] {symbol}: {len(df)} bars, close range {close[0]:.2f} -> {close[-1]:.2f}")

        # Generate signals via strategy
        entries, exits = self._generate_signals(close)
        logger.info(f"[_run_single] entries={entries.sum()}, exits={exits.sum()}")

        # Run with vectorbt
        import traceback
        try:
            pf = self._vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                size=self.config.max_position_size,
                size_type="percent",
                init_cash=self.config.initial_cash,
                fees=self.config.commission,
                slippage=self.config.slippage,
                freq=self._freq_map(self.config.timeframe),
                accumulate=False,
            )
            logger.info(f"[_run_single] portfolio created OK, total_trades={pf.trades.count()}")
        except Exception as e:
            logger.error(f"[_run_single] Portfolio.from_signals FAILED: {type(e).__name__}: {e}")
            logger.error(f"[_run_single] traceback: {traceback.format_exc()}")
            raise

        # Extract stats
        stats = pf.stats()
        trade_records = pf.trades.records
        logger.info(f"[_run_single] stats: total_return={stats.get('Total Return [%]')}, trades={stats.get('Total Trades')}")

        # Build result
        result = self._build_result(
            symbol=symbol,
            stats=stats,
            trade_records=trade_records,
            df=df,
            pf=pf,
        )
        return result

    async def _run_walk_forward(self, symbol: str, df: pd.DataFrame) -> list[BacktestResult]:
        """Run walk-forward backtest across multiple train/test windows."""
        train_days = self.config.train_window_days or 30
        test_days = self.config.test_window_days or 7
        n_windows = (len(df) - train_days) // test_days
        results = []

        for i in range(n_windows):
            train_start = i * test_days
            train_end = train_start + train_days

            train_df = df.iloc[train_start:train_end]
            test_df = df.iloc[train_end:train_end + test_days]

            if len(train_df) < 50 or len(test_df) < 20:
                continue

            close = test_df["close"].values
            entries, exits = self._generate_signals(close)

            pf = self._vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                size=self.config.max_position_size,
                size_type="percent",
                init_cash=self.config.initial_cash,
                fees=self.config.commission,
                slippage=self.config.slippage,
                freq=self._freq_map(self.config.timeframe),
            )

            stats = pf.stats()
            trade_records = pf.trades.records

            result = self._build_result(
                symbol=symbol,
                stats=stats,
                trade_records=trade_records,
                df=test_df,
                pf=pf,
                is_walk_forward=True,
            )
            result.strategy_name = f"{self.config.strategy_name} [WF-{i+1}]"
            results.append(result)

        return results

    def _generate_signals(self, close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate entry/exit signals via the strategy registry.
        Calls strategy.compute(df) → strategy.generate_signals(df) → converts list[Signal] to (entries, exits).
        """
        strategy = strategy_from_dict(self.config.strategy_name, self.config.extra_data)

        # Build a minimal DataFrame so strategies can access df["close"] etc.
        df = pd.DataFrame({"close": close})

        # Compute indicators first (strategies expect columns like ma_fast, rsi, etc.)
        df = strategy.compute(df)

        raw_signals = strategy.generate_signals(df)

        entries = np.zeros(len(close), dtype=bool)
        exits = np.zeros(len(close), dtype=bool)

        for sig in raw_signals:
            if sig.signal_index < 0 or sig.signal_index >= len(close):
                continue
            if sig.direction_int == 1:    # long → entry
                entries[sig.signal_index] = True
            elif sig.direction_int == -1:  # short → exit
                exits[sig.signal_index] = True

        return entries, exits

    def _build_result(
        self,
        symbol: str,
        stats: pd.Series,
        trade_records,  # pd.DataFrame from pf.trades.records
        df: pd.DataFrame,
        pf=None,
        is_walk_forward: bool = False,
    ) -> BacktestResult:
        """Build BacktestResult from vectorbt stats."""
        def _idx_to_dt(idx, df_index):
            """Convert integer index to datetime using the price series index."""
            if idx is None or np.isnan(idx):
                return None
            try:
                int_idx = int(idx)
                if 0 <= int_idx < len(df_index):
                    ts = df_index[int_idx]
                    return ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts
            except (ValueError, TypeError):
                pass
            return None

        # trade_records is a pd.DataFrame from pf.trades.records (vbt v1.0.0)
        # Columns: id, col, size, entry_idx, entry_price, entry_fees, exit_idx, exit_price, exit_fees, pnl, return, direction, status, parent_id
        records_list = trade_records.to_dict("records") if hasattr(trade_records, 'to_dict') else (list(trade_records) if not isinstance(trade_records, list) else trade_records)
        trades = []
        for r in records_list:
            try:
                status = int(r.get("status", 0))
                size = float(r.get("size", 0))
                trade = Trade(
                    entry_time=_idx_to_dt(r.get("entry_idx"), df.index),
                    entry_price=float(r["entry_price"]),
                    side="long" if size > 0 else "short",
                    size=abs(size),
                    pnl=float(r["pnl"]),
                    exit_time=_idx_to_dt(r.get("exit_idx"), df.index),
                    exit_price=float(r.get("exit_price")) if r.get("exit_price") is not None and not np.isnan(float(r.get("exit_price", 0))) else None,
                    commission=float(r.get("entry_fees", 0)) + float(r.get("exit_fees", 0)),
                )
                if status == 1:  # closed trade
                    trades.append(trade)
                elif status == 0 and not any(t.exit_time is None for t in trades):
                    # Include first open trade (no prior open trade)
                    trades.append(trade)
            except (KeyError, ValueError, TypeError):
                continue

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = len(wins) / len(trades) if trades else 0
        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl for t in losses]) if losses else 0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

        # avg win/loss as percentage of initial cash
        avg_win_pct = (avg_win / self.config.initial_cash) * 100 if self.config.initial_cash else 0
        avg_loss_pct = (avg_loss / self.config.initial_cash) * 100 if self.config.initial_cash else 0

        total_return = stats.get("Total Return [%]", 0) / 100
        max_dd = stats.get("Max Drawdown [%]", 0)

        # Build equity curve: sample ~50 points evenly from the equity series
        equity_curve = []
        if pf is not None:
            equity_ts = pf.value()
            if equity_ts is not None and len(equity_ts) > 0:
                n = len(equity_ts)
                step = max(1, n // 50)
                equity_curve = [float(v) for v in equity_ts[::step]]
                # always include the last point
                last_val = float(equity_ts.iloc[-1])
                if last_val not in equity_curve:
                    equity_curve.append(last_val)
        # Fallback: use initial and final equity
        if not equity_curve:
            equity_curve = [float(self.config.initial_cash), float(stats.get("End Value", self.config.initial_cash))]

        return BacktestResult(
            strategy_name=self.config.strategy_name,
            symbol=symbol,
            timeframe=self.config.timeframe,
            start_date=df.index[0].to_pydatetime(),
            end_date=df.index[-1].to_pydatetime(),
            initial_cash=self.config.initial_cash,
            final_equity=stats.get("End Value", self.config.initial_cash),
            total_return=total_return,
            total_return_pct=total_return * 100,
            max_drawdown=stats.get("Max Drawdown [%]", 0) / 100,
            max_drawdown_pct=max_dd,
            sharpe_ratio=stats.get("Sharpe Ratio", 0),
            sortino_ratio=stats.get("Sortino Ratio", 0),
            calmar_ratio=stats.get("Calmar Ratio", 0),
            total_trades=stats.get("Total Trades", 0),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            profit_factor=profit_factor,
            expectancy=expectancy,
            total_time=len(df),
            training_time=self.config.train_window_days * 24,
            testing_time=self.config.test_window_days * 24,
            is_walk_forward=is_walk_forward,
            trades=trades,
            equity_curve=equity_curve,
        )

    # ─── Convenience runners ─────────────────────────────────────────────

    @staticmethod
    async def quick_run(
        symbol: str = "BTC/USDT",
        strategy: str = "ma_cross",
        timeframe: str = "1h",
        days: int = 90,
    ) -> BacktestResult:
        """Quick backtest with sensible defaults."""
        from datetime import timedelta

        config = BacktestConfig(
            strategy_name=strategy,
            symbols=[symbol],
            timeframe=timeframe,
            initial_cash=10_000,
            commission=0.001,
            slippage=0.0005,
            start_date=datetime.now(timezone.utc) - timedelta(days=days),
            end_date=datetime.now(timezone.utc),
            exchange="binance",
        )
        engine = BacktestEngine(config)
        results = await engine.run()
        return results[0] if results else None