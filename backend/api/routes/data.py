"""
Data API Routes — /api/v1/data/*
OHLCV fetch, candle storage, backfill, market regimes.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from services.data.exchange_manager import get_exchange_manager, ExchangeConfig
from services.data.candle_store import CandleStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/data", tags=["data"])


class OHLCVRequest(BaseModel):
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    since: Optional[int] = None  # Unix ms
    limit: int = 1000


class BackfillRequest(BaseModel):
    exchange: str = "binance"
    symbol: str
    timeframe: str = "1h"
    days_back: int = 90
    since_ms: Optional[int] = None  # Unix ms — overrides days_back if set


class BulkFetchRequest(BaseModel):
    exchange: str = "binance"
    pairs: list[str]
    timeframe: str = "1h"
    days_back: int = 30


# ─── Fetch from Exchange ─────────────────────────────────────────────────

@router.post("/fetch-ohlcv")
async def fetch_ohlcv(req: OHLCVRequest):
    """Fetch OHLCV from exchange (live, no storage)."""
    try:
        mgr = get_exchange_manager()
        candles = await mgr.fetch_ohlcv(
            req.exchange, req.symbol, req.timeframe, req.since, req.limit
        )
        return {
            "count": len(candles),
            "candles": [c.to_dict() for c in candles],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-ticker")
async def fetch_ticker(exchange: str = "binance", symbol: str = "BTC/USDT"):
    """Fetch current ticker."""
    try:
        mgr = get_exchange_manager()
        ticker = await mgr.fetch_ticker(exchange, symbol)
        return {
            "symbol": ticker.symbol,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "last": ticker.last,
            "volume": ticker.volume,
            "timestamp": ticker.timestamp.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickers")
async def get_tickers(exchange: str = "binance", symbols: str = "BTC/USDT,ETH/USDT,SOL/USDT"):
    """Fetch current prices for multiple symbols. symbols param is comma-separated."""
    try:
        mgr = get_exchange_manager()
        pairs = [s.strip() for s in symbols.split(",")]
        results = []
        for pair in pairs:
            try:
                ticker = await mgr.fetch_ticker(exchange, pair)
                results.append({
                    "symbol": pair.replace("/", ""),
                    "exchange": exchange,
                    "price": ticker.last,
                    "bid": ticker.bid,
                    "ask": ticker.ask,
                    "volume": ticker.volume,
                    "timestamp": ticker.timestamp.isoformat(),
                })
            except Exception:
                pass
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ticker")
async def get_ticker(req: OHLCVRequest):
    """Fetch current ticker for polling fallback."""
    try:
        mgr = get_exchange_manager()
        ticker = await mgr.fetch_ticker(req.exchange, req.symbol)
        return {
            "symbol": ticker.symbol,
            "exchange": req.exchange,
            "price": ticker.last,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "volume": ticker.volume,
            "timestamp": ticker.timestamp.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-orderbook")
async def fetch_orderbook(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    depth: int = 20,
):
    """Fetch orderbook."""
    try:
        mgr = get_exchange_manager()
        ob = await mgr.fetch_orderbook(exchange, symbol, depth)
        return {
            "symbol": ob.symbol,
            "bids": ob.bids[:depth],
            "asks": ob.asks[:depth],
            "timestamp": ob.timestamp.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-fetch")
async def bulk_fetch(req: BulkFetchRequest):
    """Fetch OHLCV for multiple pairs concurrently."""
    try:
        mgr = get_exchange_manager()
        results = await mgr.fetch_ohlcv_bulk(
            req.exchange, req.pairs, req.timeframe, req.days_back
        )
        return {
            "count": len(results),
            "pairs": {p: len(c) for p, c in results.items()},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Storage ──────────────────────────────────────────────────────────────

@router.post("/store-candles")
async def store_candles(req: OHLCVRequest):
    """Fetch from exchange and store in DB."""
    try:
        mgr = get_exchange_manager()
        candles = await mgr.fetch_ohlcv(
            req.exchange, req.symbol, req.timeframe, req.since, req.limit
        )
        n = await CandleStore.store(req.exchange, req.symbol, req.timeframe, candles)
        return {"stored": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles")
async def get_candles(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since_ts: Optional[int] = None,  # Unix ms
    until_ts: Optional[int] = None,
    limit: int = 5000,
):
    """Get candles from DB."""
    try:
        since = datetime.fromtimestamp(since_ts / 1000, tz=timezone.utc) if since_ts else None
        until = datetime.fromtimestamp(until_ts / 1000, tz=timezone.utc) if until_ts else None

        candles = await CandleStore.get(exchange, symbol, timeframe, since, until, limit)
        return {"count": len(candles), "candles": candles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles/count")
async def count_candles(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
):
    """Count stored candles."""
    try:
        n = await CandleStore.count(exchange, symbol, timeframe)
        return {"count": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Backfill ─────────────────────────────────────────────────────────────

@router.post("/backfill")
async def backfill(req: BackfillRequest):
    """
    Trigger a backfill job. Runs async, returns job_id.
    For large backfills, use the /jobs endpoint instead.
    """
    try:
        # For small backfills, run synchronously
        from datetime import datetime, timezone as tz
        from services.data.candle_store import CandleStore

        # If since_ms provided, use it; otherwise fall back to days_back
        if req.since_ms:
            since_dt = datetime.fromtimestamp(req.since_ms / 1000, tz=tz.utc)
            days_back = (datetime.now(tz.utc) - since_dt).days
            stored = await CandleStore.bulk_backfill(
                req.exchange, req.symbol, req.timeframe, days_back=days_back
            )
        else:
            stored = await CandleStore.bulk_backfill(
                req.exchange, req.symbol, req.timeframe, req.days_back
            )
        return {"stored": stored, "status": "done"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Market Regimes ───────────────────────────────────────────────────────

@router.get("/regime")
async def detect_regime(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    lookback: int = 100,
):
    """Detect market regime."""
    try:
        regime = await CandleStore.detect_regime(exchange, symbol, timeframe, lookback)
        return regime
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regime/store")
async def store_regime(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    lookback: int = 100,
):
    """Detect and store current market regime."""
    try:
        regime = await CandleStore.detect_regime(exchange, symbol, timeframe, lookback)
        await CandleStore.store_regime(exchange, symbol, timeframe, regime)
        return {"regime": regime, "stored": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Exchange Info ─────────────────────────────────────────────────────────

@router.get("/markets")
async def get_markets(exchange: str = "binance"):
    """List available markets on exchange."""
    try:
        mgr = get_exchange_manager()
        markets = await mgr.fetch_markets(exchange)
        spot = {
            sym: {
                "base": m["base"],
                "quote": m["quote"],
                "active": m.get("active", False),
            }
            for sym, m in markets.items()
            if m.get("type") == "spot" and m.get("active")
        }
        return {"count": len(spot), "markets": spot}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))