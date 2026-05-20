"""
Backtest Result Domain Model - Section 4 and Section 20 from PLAN-v2.md

Includes all performance metrics defined in Metrics Reference.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class BacktestStatus(Enum):
    """Backtest run status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EquityPoint:
    """Single point on equity curve."""
    date: date
    equity: float
    drawdown: float = 0.0

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat() if isinstance(self.date, date) else str(self.date),
            "equity": self.equity,
            "drawdown": self.drawdown,
        }


@dataclass
class Trade:
    """Individual trade record."""
    trade_id: str
    pair: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    commission: float
    slippage_bps: float
    exit_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "pair": self.pair,
            "side": self.side,
            "entry_time": self.entry_time.isoformat() if isinstance(self.entry_time, datetime) else str(self.entry_time),
            "exit_time": self.exit_time.isoformat() if isinstance(self.exit_time, datetime) else str(self.exit_time),
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "commission": self.commission,
            "slippage_bps": self.slippage_bps,
            "exit_reason": self.exit_reason,
        }


@dataclass
class SignalRecord:
    """Signal generated during backtest."""
    signal_id: str
    timestamp: datetime
    pair: str
    direction: str
    strength: float
    strategy_id: str

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "pair": self.pair,
            "direction": self.direction,
            "strength": self.strength,
            "strategy_id": self.strategy_id,
        }


@dataclass
class PerformanceMetrics:
    """All performance metrics from Section 20."""
    # Return metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    
    # Drawdown metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0
    
    # Risk-adjusted metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sterling_ratio: float = 0.0
    burke_ratio: float = 0.0
    
    # Win/loss metrics
    profit_factor: float = 0.0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    expectancy: float = 0.0
    
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Trade timing
    avg_trade_duration_hours: float = 0.0
    
    # Distribution metrics
    tail_ratio: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    information_ratio: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "sterling_ratio": self.sterling_ratio,
            "burke_ratio": self.burke_ratio,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "avg_win_pct": self.avg_win_pct,
            "avg_loss_pct": self.avg_loss_pct,
            "expectancy": self.expectancy,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "tail_ratio": self.tail_ratio,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "information_ratio": self.information_ratio,
        }


@dataclass
class BacktestResult:
    """Complete backtest result domain model."""
    id: UUID = field(default_factory=uuid4)
    config_id: UUID = field(default_factory=uuid4)
    pair: str = ""
    timeframe: str = ""
    initial_capital: float = 10000.0
    final_equity: float = 10000.0
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    signals: list[SignalRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overfit_score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "config_id": str(self.config_id),
            "pair": self.pair,
            "timeframe": self.timeframe,
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "metrics": self.metrics.to_dict(),
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "trades": [t.to_dict() for t in self.trades],
            "signals": [s.to_dict() for s in self.signals],
            "warnings": self.warnings,
            "overfit_score": self.overfit_score,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MAEEntry:
    """Maximum Adverse Excursion per trade."""
    trade_id: str
    mae: float  # as percentage

    def to_dict(self) -> dict:
        return {"trade_id": self.trade_id, "mae": self.mae}


@dataclass
class MFEEntry:
    """Maximum Favorable Excursion per trade."""
    trade_id: str
    mfe: float  # as percentage

    def to_dict(self) -> dict:
        return {"trade_id": self.trade_id, "mfe": self.mfe}