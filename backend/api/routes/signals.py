"""
Signal API Routes — expose signal generation as REST endpoints.
POST /api/v1/signals/generate  → run a strategy on stored candles, return signals
GET  /api/v1/signals            → list available strategy names
GET  /api/v1/signals/history    → recent signals from backtest results table
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.data.candle_store import CandleStore
from services.signals.registry import (
    BaseStrategy,
    get_strategy,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class SignalGenerateRequest(BaseModel):
    exchange: str = Field(default="binance", description="Exchange ID")
    symbol: str = Field(default="BTC/USDT", description="Trading pair")
    timeframe: str = Field(default="1h", description="Candle timeframe")
    strategy: str = Field(..., description="Strategy name: ma_cross, rsi, bollinger, macd")
    lookback: int = Field(default=200, description="Number of candles to analyse")
    params: dict = Field(default_factory=dict, description="Strategy-specific parameters")


class SignalItem(BaseModel):
    timestamp: str
    symbol: str
    direction: str
    strength: float
    price: float
    indicators: dict
    strategy: str


class SignalGenerateResponse(BaseModel):
    signals: list[SignalItem]
    strategy: str
    symbol: str
    timeframe: str
    count: int


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_signals():
    """List available strategies and their indicator types."""
    return {
        "strategies": [
            {
                "name": "ma_cross",
                "description": "Moving Average Crossover",
                "indicators": ["SMA(fast)", "SMA(slow)"],
                "params": {"fast_period": 10, "slow_period": 30},
            },
            {
                "name": "rsi",
                "description": "RSI Mean-Reversion",
                "indicators": ["RSI(period)"],
                "params": {"period": 14, "oversold": 30, "overbought": 70},
            },
            {
                "name": "bollinger",
                "description": "Bollinger Bands Breakout",
                "indicators": ["BB(upper, middle, lower)", "BB(width)"],
                "params": {"period": 20, "nb_dev": 2.0},
            },
            {
                "name": "macd",
                "description": "MACD Momentum",
                "indicators": ["MACD", "MACD(signal)", "MACD(hist)"],
                "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            },
        ]
    }


@router.post("/generate", response_model=SignalGenerateResponse)
async def generate_signals(req: SignalGenerateRequest):
    """
    Fetch stored candles for the given pair/timeframe and run the selected
    strategy to produce trading signals.
    """
    # Fetch candles from DB
    candles = await CandleStore.get(
        req.exchange,
        req.symbol,
        req.timeframe,
        limit=req.lookback,
    )
    if len(candles) < 20:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough candles: {len(candles)} stored. Need at least 20.",
        )

    # Build DataFrame
    import pandas as pd

    df = pd.DataFrame(candles)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    df = df.sort_index()
    df["symbol"] = req.symbol

    # Resolve strategy
    try:
        strategy_cls = get_strategy(req.strategy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{req.strategy}'. Available: ma_cross, rsi, bollinger, macd",
        )

    # Merge params
    config = {**req.params}
    if req.strategy == "ma_cross":
        config.setdefault("fast_period", 10)
        config.setdefault("slow_period", 30)
    elif req.strategy == "rsi":
        config.setdefault("period", 14)
        config.setdefault("oversold", 30)
        config.setdefault("overbought", 70)
    elif req.strategy == "bollinger":
        config.setdefault("period", 20)
        config.setdefault("nb_dev", 2.0)

    strategy: BaseStrategy = strategy_cls(config)

    # Compute indicators and generate signals
    df = strategy.warmup(df)
    raw_signals = strategy.generate_signals(df)

    # Convert to serialisable format — newest first
    signals = sorted(raw_signals, key=lambda s: s.timestamp, reverse=True)

    return SignalGenerateResponse(
        signals=[
            SignalItem(
                timestamp=s.timestamp.isoformat(),
                symbol=s.symbol,
                direction=s.direction,
                strength=round(s.strength, 3),
                price=round(float(s.price), 4),
                indicators={k: round(float(v), 6) for k, v in s.indicators.items()},
                strategy=s.strategy,
            )
            for s in signals
        ],
        strategy=req.strategy,
        symbol=req.symbol,
        timeframe=req.timeframe,
        count=len(signals),
    )


@router.get("/history", response_model=dict)
async def signal_history(
    exchange: str = Query("binance"),
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("1h"),
    limit: int = Query(20, ge=1, le=500),
):
    """
    Fetch recent regime + price data as a lightweight signal proxy when no
    backtest results exist yet.
    """
    candles = await CandleStore.get(exchange, symbol, timeframe, limit=limit)
    if not candles:
        return {"signals": [], "note": "No candle data found"}

    latest = candles[-1]
    regime = await CandleStore.detect_regime(exchange, symbol, timeframe, lookback=min(100, len(candles)))

    return {
        "signals": [
            {
                "timestamp": c["timestamp"],
                "symbol": symbol,
                "direction": "neutral",
                "price": c["close"],
            }
            for c in candles[-limit:]
        ],
        "regime": regime,
        "count": len(candles),
    }
