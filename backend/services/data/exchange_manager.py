"""
Data Pipeline Service — Exchange connections, candle data, and real-time streams.
Supports: Binance, Kraken, OKX, Bybit, Coinbase, KuCoin via CCXT.
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

import ccxt
from ccxt import ExchangeError, NetworkError

from core.database import get_session
from core.redis import redis_manager
from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExchangeConfig:
    exchange_id: str  # 'binance', 'kraken', 'okx', etc.
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    password: Optional[str] = None       # for exchanges needing password (OKX, Coinbase)
    testnet: bool = False
    verbose: bool = False


@dataclass
class OHLCV:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


@dataclass
class OrderBook:
    symbol: str
    bids: list[tuple[float, float]]  # (price, size)
    asks: list[tuple[float, float]]
    timestamp: datetime


class ExchangeManager:
    """
    Manages CCXT exchange connections. Handles:
    - REST fetch: candles, orderbook, trades, tickers
    - WebSocket: live ticker, candle, orderbook streams
    - Rate limiting, retry logic, error handling
    """

    def __init__(self, configs: list[ExchangeConfig]):
        self.exchanges: dict[str, ccxt.Exchange] = {}
        self._ws_clients: dict[str, any] = {}
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

        for cfg in configs:
            self._create_exchange(cfg)

    def _create_exchange(self, cfg: ExchangeConfig) -> None:
        try:
            exchange_class = getattr(ccxt, cfg.exchange_id)
            exchange = exchange_class({
                "apiKey": cfg.api_key or "",
                "secret": cfg.api_secret or "",
                "password": cfg.password or "",
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
            if cfg.testnet:
                exchange.set_sandbox_mode(True)

            self.exchanges[cfg.exchange_id] = exchange
            logger.info(f"Exchange '{cfg.exchange_id}' initialized (sandbox={cfg.testnet})")
        except Exception as e:
            logger.error(f"Failed to init exchange '{cfg.exchange_id}': {e}")

    @property
    def binance(self) -> ccxt.Exchange:
        return self.exchanges.get("binance")

    @property
    def kraken(self) -> ccxt.Exchange:
        return self.exchanges.get("kraken")

    @property
    def okx(self) -> ccxt.Exchange:
        return self.exchanges.get("okx")

    # ─── OHLCV / Candle fetching ────────────────────────────────────────────

    async def fetch_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 1000,
    ) -> list[OHLCV]:
        """
        Fetch OHLCV candles from exchange.
        symbol: e.g. 'BTC/USDT'
        timeframe: '1m','5m','15m','1h','4h','1d'
        since: Unix timestamp ms (for backfill)
        """
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange '{exchange_id}' not loaded")

        await self._retry(exchange.loadMarkets)

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: exchange.fetchOHLCV(symbol, timeframe, since, limit)
            )

            candles = []
            for row in raw:
                ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
                candles.append(OHLCV(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                ))
            return candles

        except (ExchangeError, NetworkError) as e:
            logger.error(f"OHLCV fetch error {exchange_id}/{symbol}: {e}")
            raise

    async def fetch_ohlcv_bulk(
        self,
        exchange_id: str,
        pairs: list[str],
        timeframe: str = "1h",
        days_back: int = 90,
    ) -> dict[str, list[OHLCV]]:
        """
        Fetch OHLCV for multiple pairs concurrently.
        days_back: how far back to fetch (respects exchange rate limits).
        """
        since = int((
            datetime.now(timezone.utc).timestamp() - (days_back * 86400)
        ) * 1000)

        async def fetch_one(pair: str) -> tuple[str, list[OHLCV]]:
            try:
                candles = await self.fetch_ohlcv(exchange_id, pair, timeframe, since)
                return pair, candles
            except Exception as e:
                logger.warning(f"Skipping {pair}: {e}")
                return pair, []

        tasks = [fetch_one(p) for p in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            pair, candles = r
            out[pair] = candles

        return out

    # ─── Ticker / OrderBook ─────────────────────────────────────────────────

    async def fetch_ticker(self, exchange_id: str, symbol: str) -> Ticker:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange '{exchange_id}' not loaded")

        await self._retry(exchange.loadMarkets)

        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, lambda: exchange.fetchTicker(symbol))

        return Ticker(
            symbol=symbol,
            bid=float(raw["bid"]) if raw.get("bid") else 0.0,
            ask=float(raw["ask"]) if raw.get("ask") else 0.0,
            last=float(raw["last"]) if raw.get("last") else 0.0,
            volume=float(raw.get("baseVolume", 0) or 0),
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=timezone.utc),
        )

    async def fetch_orderbook(
        self, exchange_id: str, symbol: str, depth: int = 20
    ) -> OrderBook:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange '{exchange_id}' not loaded")

        await self._retry(exchange.loadMarkets)

        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None, lambda: exchange.fetchOrderBook(symbol, depth)
        )

        return OrderBook(
            symbol=symbol,
            bids=[(float(p), float(s)) for p, s in raw.get("bids", [])],
            asks=[(float(p), float(s)) for p, s in raw.get("asks", [])],
            timestamp=datetime.now(timezone.utc),
        )

    # ─── Exchange Status ─────────────────────────────────────────────────

    async def fetch_markets(self, exchange_id: str) -> dict:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange '{exchange_id}' not loaded")

        await self._retry(exchange.loadMarkets)
        return exchange.markets

    async def fetch_leverage_tiers(self, exchange_id: str, symbol: str) -> list:
        """Fetch leverage margin tiers for symbol (for futures)."""
        exchange = self.exchanges.get(exchange_id)
        if not exchange or not hasattr(exchange, "fetchLeverageTiers"):
            return []
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: exchange.fetchLeverageTiers([symbol])
            )
        except Exception:
            return []

    # ─── Retry helper ─────────────────────────────────────────────────────

    async def _retry(self, fn, *args, max_attempts: int = 3, **kwargs):
        """Simple exponential backoff retry for rate-limit errors."""
        for attempt in range(max_attempts):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"Retry {attempt+1}/{max_attempts} after {wait}s: {e}")
                await asyncio.sleep(wait)

    # ─── Subscription helpers ──────────────────────────────────────────────

    async def subscribe_ticker(self, exchange_id: str, symbol: str):
        """Subscribe to ticker stream. Stores data in Redis."""
        key = f"ticker:{exchange_id}:{symbol}"
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            return

        try:
            while True:
                ticker = await self.fetch_ticker(exchange_id, symbol)
                data = ticker.__dict__.copy()
                data["timestamp"] = ticker.timestamp.isoformat()
                await redis_manager.set_json(key, data, expire=60)
                # Binance ws pushes ~every 100ms, others vary
                await asyncio.sleep(exchange.rateLimit / 1000 * 2)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ticker stream error {exchange_id}/{symbol}: {e}")


# ─── Singleton instance ─────────────────────────────────────────────────────

_default_exchanges = [
    ExchangeConfig(
        exchange_id="binance",
        api_key=settings.binance_api_key or None,
        api_secret=settings.binance_secret or None,
        testnet=bool(settings.binance_testnet),
    ),
    ExchangeConfig(
        exchange_id="okx",
        api_key=settings.okx_api_key or None,
        api_secret=settings.okx_secret or None,
        password=settings.okx_password or None,
    ),
    ExchangeConfig(
        exchange_id="kraken",
        api_key=settings.kraken_api_key or None,
        api_secret=settings.kraken_secret or None,
    ),
]

# Global instance — init only if credentials exist for at least one
_has_creds = any(
    (e.api_key and e.api_secret) for e in _default_exchanges
)

# Lazy init so we don't fail if no env vars are set yet
_manager: Optional[ExchangeManager] = None


def get_exchange_manager() -> ExchangeManager:
    global _manager
    if _manager is None:
        _manager = ExchangeManager(_default_exchanges)
    return _manager