"""
Database tables — candles, market_regimes, positions, trades.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Index, Table
)
from sqlalchemy.dialects.postgresql import UUID, JSON

from core.database import Base


# ─── Candles ───────────────────────────────────────────────────────────────

candles_table = Table(
    "candles",
    Base.metadata,
    Column("id", UUID, primary_key=True),
    Column("exchange", String(50), nullable=False),
    Column("symbol", String(50), nullable=False),
    Column("timeframe", String(20), nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Float, nullable=False),
    Index("ix_candles_exchange_symbol_timeframe_timestamp",
          "exchange", "symbol", "timeframe", "timestamp", unique=True),
    Index("ix_candles_exchange_symbol_timeframe", "exchange", "symbol", "timeframe"),
    extend_existing=True,
)


# ─── Market Regimes ─────────────────────────────────────────────────────────

market_regimes_table = Table(
    "market_regimes",
    Base.metadata,
    Column("id", UUID, primary_key=True),
    Column("pair", String(50), nullable=False),
    Column("timeframe", String(20), nullable=False),
    Column("date", DateTime(timezone=True), nullable=False),
    Column("regime", String(50), nullable=False),
    Column("trend_strength", Float, nullable=False),
    Column("volatility_rank", Float, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_market_regimes_pair", "pair"),
    extend_existing=True,
)