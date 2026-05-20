"""
Backtest Models - Section 5 Database Schema from PLAN-v2.md

Includes: backtest_configs, backtest_results
"""

from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import String, DateTime, Date, Integer, Numeric, Boolean, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.user import User


class BacktestConfig(Base):
    """Backtest configuration model."""
    
    __tablename__ = "backtest_configs"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategies: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        default=list,
    )
    pairs: Mapped[list] = mapped_column(
        ARRAY(String),
        default=list,
    )
    timeframes: Mapped[list] = mapped_column(
        ARRAY(String),
        default=list,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    exchange: Mapped[str] = mapped_column(
        String(50),
        default="binance",
    )
    initial_capital: Mapped[float] = mapped_column(
        Numeric(20, 4),
        default=Decimal("10000.0000"),
    )
    leverage: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=Decimal("1.0000"),
    )
    position_sizing: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    max_positions: Mapped[int] = mapped_column(
        Integer,
        default=5,
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        default="both",
    )
    fees: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    slippage_model: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    walk_forward: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    monte_carlo: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    risk_limits: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Relationships
    owner = relationship("User", back_populates="backtest_configs")
    results = relationship("BacktestResult", back_populates="config")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "owner_id": str(self.owner_id),
            "strategies": [str(s) for s in self.strategies],
            "pairs": self.pairs,
            "timeframes": self.timeframes,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "exchange": self.exchange,
            "initial_capital": float(self.initial_capital),
            "leverage": float(self.leverage),
            "position_sizing": self.position_sizing,
            "max_positions": self.max_positions,
            "direction": self.direction,
            "fees": self.fees,
            "slippage_model": self.slippage_model,
            "walk_forward": self.walk_forward,
            "monte_carlo": self.monte_carlo,
            "risk_limits": self.risk_limits,
            "created_at": self.created_at.isoformat(),
        }


class BacktestResult(Base):
    """Backtest result model with all metrics from Section 20."""
    
    __tablename__ = "backtest_results"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    config_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pair: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
    )
    strategy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="running",
        index=True,
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Performance metrics
    initial_capital: Mapped[float] = mapped_column(
        Numeric(20, 4),
        default=Decimal("10000.0000"),
    )
    final_equity: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=True,
    )
    total_return: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    annualized_return: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    max_drawdown: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    max_drawdown_pct: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    max_drawdown_duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    sharpe_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    sortino_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    calmar_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    sterling_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    burke_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    profit_factor: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    win_rate: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    avg_win_pct: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    avg_loss_pct: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    expectancy: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    total_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    winning_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    losing_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    avg_trade_duration_hours: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    tail_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    skewness: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    kurtosis: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    information_ratio: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    
    # Detailed data
    equity_curve: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    trades: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    signals: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    mae_by_trade: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    mfe_by_trade: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    overfit_score: Mapped[float] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    warnings: Mapped[list] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    settings_used: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Relationships
    config = relationship("BacktestConfig", back_populates="results")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "config_id": str(self.config_id),
            "pair": self.pair,
            "timeframe": self.timeframe,
            "strategy_id": str(self.strategy_id) if self.strategy_id else None,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "initial_capital": float(self.initial_capital) if self.initial_capital else None,
            "final_equity": float(self.final_equity) if self.final_equity else None,
            "total_return": float(self.total_return) if self.total_return else None,
            "annualized_return": float(self.annualized_return) if self.annualized_return else None,
            "max_drawdown": float(self.max_drawdown) if self.max_drawdown else None,
            "max_drawdown_pct": float(self.max_drawdown_pct) if self.max_drawdown_pct else None,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "sharpe_ratio": float(self.sharpe_ratio) if self.sharpe_ratio else None,
            "sortino_ratio": float(self.sortino_ratio) if self.sortino_ratio else None,
            "calmar_ratio": float(self.calmar_ratio) if self.calmar_ratio else None,
            "sterling_ratio": float(self.sterling_ratio) if self.sterling_ratio else None,
            "burke_ratio": float(self.burke_ratio) if self.burke_ratio else None,
            "profit_factor": float(self.profit_factor) if self.profit_factor is not None else None,
            "win_rate": float(self.win_rate) if self.win_rate is not None else None,
            "avg_win_pct": float(self.avg_win_pct) if self.avg_win_pct else None,
            "avg_loss_pct": float(self.avg_loss_pct) if self.avg_loss_pct else None,
            "expectancy": float(self.expectancy) if self.expectancy else None,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_duration_hours": float(self.avg_trade_duration_hours) if self.avg_trade_duration_hours else None,
            "tail_ratio": float(self.tail_ratio) if self.tail_ratio else None,
            "skewness": float(self.skewness) if self.skewness else None,
            "kurtosis": float(self.kurtosis) if self.kurtosis else None,
            "information_ratio": float(self.information_ratio) if self.information_ratio else None,
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "signals": self.signals,
            "mae_by_trade": self.mae_by_trade,
            "mfe_by_trade": self.mfe_by_trade,
            "overfit_score": float(self.overfit_score) if self.overfit_score else None,
            "warnings": self.warnings,
            "settings_used": self.settings_used,
        }