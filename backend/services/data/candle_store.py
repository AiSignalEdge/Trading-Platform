"""
Candle storage service — persists OHLCV data to PostgreSQL for backtesting.
Stores candles in the `candles` table and caches hot data in Redis.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import insert, select, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tqdm import tqdm

from core.database import get_session
from core.tables import candles_table, market_regimes_table
from core.redis import redis_manager

logger = logging.getLogger(__name__)


class CandleStore:
    """
    Persists and retrieves OHLCV candles from PostgreSQL.
    Also caches recent candles in Redis for fast read access.
    """

    @staticmethod
    async def store(exchange_id: str, symbol: str, timeframe: str, candles: list):
        """
        Bulk insert candles. Uses upsert (ON CONFLICT DO NOTHING) so
        duplicate candles (same exchange/symbol/timeframe/timestamp) are ignored.
        """
        if not candles:
            return 0

        rows = [
            {
                "id": uuid.uuid4(),
                "exchange": exchange_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]

        async with get_session() as session:
            # Upsert
            stmt = pg_insert(candles_table).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=[
                candles_table.c.exchange,
                candles_table.c.symbol,
                candles_table.c.timeframe,
                candles_table.c.timestamp,
            ])
            await session.execute(stmt)
            await session.commit()

        # Cache latest candles in Redis for quick access
        if rows:
            cache_key = f"candles:{exchange_id}:{symbol}:{timeframe}"
            # Convert datetime to ISO strings for JSON serialization
            recent = []
            for c in rows[-500:]:
                row = dict(c._mapping) if hasattr(c, '_mapping') else dict(c)
                if hasattr(row["timestamp"], "isoformat"):
                    row["timestamp"] = row["timestamp"].isoformat()
                if hasattr(row["id"], "__str__"):
                    row["id"] = str(row["id"])
                recent.append(row)
            await redis_manager.set_json(cache_key, recent, expire=3600)

        logger.info(f"Stored {len(rows)} candles {exchange_id}:{symbol} {timeframe}")
        return len(rows)

    @staticmethod
    async def get(
        exchange_id: str,
        symbol: str,
        timeframe: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 5000,
    ) -> list[dict]:
        """
        Retrieve candles from DB. Checks Redis cache first for recent data.
        """
        cache_key = f"candles:{exchange_id}:{symbol}:{timeframe}"

        # Try cache first (only for recent data without time range filter)
        if since is None and until is None:
            try:
                cached = await redis_manager.get_json(cache_key)
                if cached:
                    return cached[:limit]
            except Exception:
                pass  # Redis unavailable, fall through to DB

        async with get_session() as session:
            stmt = (
                select(candles_table)
                .where(candles_table.c.exchange == exchange_id)
                .where(candles_table.c.symbol == symbol)
                .where(candles_table.c.timeframe == timeframe)
                .order_by(candles_table.c.timestamp.asc())
            )

            if since:
                stmt = stmt.where(candles_table.c.timestamp >= since)
            if until:
                stmt = stmt.where(candles_table.c.timestamp <= until)

            stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            rows = result.fetchall()

        return [dict(row._mapping) for row in rows]

    @staticmethod
    async def get_latest(
        exchange_id: str,
        symbol: str,
        timeframe: str,
    ) -> Optional[dict]:
        """Get the most recent candle."""
        candles = await CandleStore.get(
            exchange_id, symbol, timeframe, limit=1
        )
        return candles[-1] if candles else None

    @staticmethod
    async def count(exchange_id: str, symbol: str, timeframe: str) -> int:
        """Count stored candles for a given pair/timeframe."""
        async with get_session() as session:
            stmt = select(func.count()).select_from(candles_table).where(
                candles_table.c.exchange == exchange_id,
                candles_table.c.symbol == symbol,
                candles_table.c.timeframe == timeframe,
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    @staticmethod
    async def delete_old(
        exchange_id: str,
        symbol: str,
        timeframe: str,
        keep_days: int = 365,
    ) -> int:
        """Delete candles older than keep_days to manage storage."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)

        async with get_session() as session:
            stmt = delete(candles_table).where(
                candles_table.c.exchange == exchange_id,
                candles_table.c.symbol == symbol,
                candles_table.c.timeframe == timeframe,
                candles_table.c.timestamp < cutoff,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    @staticmethod
    async def bulk_backfill(
        exchange_id: str,
        symbol: str,
        timeframe: str,
        days_back: int = 90,
        batch_size: int = 1000,
    ) -> int:
        """
        Backfill candles from exchange to DB for historical analysis.
        Returns total candles stored.
        """
        from services.data.exchange_manager import get_exchange_manager, OHLCV

        mgr = get_exchange_manager()
        total = 0

        since = int((
            datetime.now(timezone.utc).timestamp() - (days_back * 86400)
        ) * 1000)

        with tqdm(desc=f"{exchange_id} {symbol} {timeframe}") as pbar:
            while True:
                try:
                    loop = asyncio.get_running_loop()
                    raw = await loop.run_in_executor(
                        None,
                        lambda: mgr.exchanges.get(exchange_id).fetchOHLCV(
                            symbol, timeframe, since, batch_size
                        )
                    )
                    if not raw:
                        break

                    candles = [
                        OHLCV(
                            symbol=symbol,
                            timeframe=timeframe,
                            timestamp=datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc),
                            open=float(r[1]),
                            high=float(r[2]),
                            low=float(r[3]),
                            close=float(r[4]),
                            volume=float(r[5]),
                        )
                        for r in raw
                    ]

                    n = await CandleStore.store(exchange_id, symbol, timeframe, candles)
                    total += n
                    pbar.update(len(candles))

                    since = raw[-1][0] + 1
                    await asyncio.sleep(0.2)  # rate limit respect

                    if len(raw) < batch_size:
                        break

                except Exception as e:
                    logger.error(f"Backfill error: {e}")
                    break

        return total

    # ─── Market Regime ─────────────────────────────────────────────────────

    @staticmethod
    async def detect_regime(
        exchange_id: str,
        symbol: str,
        timeframe: str,
        lookback: int = 100,
    ) -> dict:
        """
        Simple regime detection based on recent candle data.
        Classifies into: trending_up, trending_down, ranging, volatile.
        """
        candles = await CandleStore.get(
            exchange_id, symbol, timeframe, limit=lookback
        )
        if len(candles) < 20:
            return {"regime": "unknown", "trend_strength": 0, "volatility_rank": 0}

        closes = [c["close"] for c in candles]

        # Trend: ADX-like
        sma = sum(closes[-20:]) / 20
        trend = abs(closes[-1] - sma) / sma

        # Volatility: CV of last 20
        import statistics
        mean_v = statistics.mean(closes[-20:])
        std_v = statistics.stdev(closes[-20:]) if len(closes) > 1 else 0
        cv = std_v / mean_v if mean_v else 0

        # Classify
        if trend > 0.03 and closes[-1] > sma:
            regime = "trending_up"
        elif trend > 0.03 and closes[-1] < sma:
            regime = "trending_down"
        elif cv > 0.02:
            regime = "volatile"
        else:
            regime = "ranging"

        # Normalise strengths to 0–1
        trend_strength = min(1.0, trend / 0.05)
        volatility_rank = min(1.0, cv / 0.04)

        return {
            "regime": regime,
            "trend_strength": round(trend_strength, 3),
            "volatility_rank": round(volatility_rank, 3),
            "current_price": closes[-1],
        }

    @staticmethod
    async def store_regime(
        exchange_id: str,
        symbol: str,
        timeframe: str,
        regime: dict,
    ) -> None:
        import uuid
        async with get_session() as session:
            stmt = insert(market_regimes_table).values(
                id=uuid.uuid4(),
                pair=symbol,
                timeframe=timeframe,
                date=datetime.now(timezone.utc),
                regime=regime["regime"],
                trend_strength=regime["trend_strength"],
                volatility_rank=regime["volatility_rank"],
                created_at=datetime.now(timezone.utc),
            )
            await session.execute(stmt)
            await session.commit()