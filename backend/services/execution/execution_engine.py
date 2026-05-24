"""
Execution engine — paper/live market order execution via CCXT.
"""

import asyncio
import logging

import ccxt
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from core.config import settings
from core.database import get_session
from models.execution import (
    Order, OrderSide, OrderStatus, OrderType,
    Position, PositionSide,
)

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Unified execution engine supporting paper and live trading modes.

    In paper mode, orders are simulated using real market prices from CCXT.
    In live mode, orders are placed against the exchange with real funds.
    """

    def __init__(self, exchange: str = "binance", mode: str = "paper"):
        self.exchange_name = exchange
        self.mode = mode  # "paper" or "live"
        self._exchange = None
        self._price_exchange = None
        self._positions: dict[str, Position] = {}  # key: f"{symbol}_{strategy_id}"
        self._orders: dict[UUID, Order] = {}  # order_id -> order

    async def _get_exchange(self):
        if self._exchange is None:
            # Paper mode: sandbox=True gives us simulated fills but NO real prices.
            # We need production ticker data for realistic fill prices, so we also
            # create a separate production exchange instance for price fetching.
            self._exchange = getattr(ccxt, self.exchange_name)({
                'apiKey': settings.binance_api_key or 'demo',
                'secret': settings.binance_secret or 'demo',
                'sandbox': self.mode == "paper",
                'enableRateLimit': True,
            })
            if self.mode == "paper":
                # Separate non-sandbox exchange for real-time prices
                self._price_exchange = getattr(ccxt, self.exchange_name)({
                    'apiKey': None,
                    'secret': None,
                    'sandbox': False,
                    'enableRateLimit': True,
                })
            else:
                self._price_exchange = self._exchange
        return self._exchange

    async def market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        strategy_id: UUID,
    ) -> Order:
        """
        Execute a market order in paper or live mode.

        Args:
            symbol: Trading pair, e.g. "BTC/USDT" (slashes are normalized away)
            side: BUY or SELL
            quantity: Amount in base currency (e.g. BTC for BTC/USDT)
            strategy_id: UUID of the strategy placing this order
        """
        order_id = uuid4()

        # Create pending order record
        order = Order(
            id=order_id,
            strategy_id=strategy_id,
            symbol=symbol.replace("/", ""),  # normalize: BTC/USDT → BTCUSDT
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=None,
            filled_quantity=0.0,
            avg_fill_price=0.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            filled_at=None,
        )
        self._orders[order_id] = order

        if self.mode == "paper":
            # Paper trading: fetch real market price from production CCXT, simulate fill
            # Must initialize exchanges first
            await self._get_exchange()
            fill_price = 0.0
            try:
                ticker = await asyncio.to_thread(self._price_exchange.fetch_ticker, symbol)
                fill_price = float(ticker.get('last') or ticker.get('close') or 0)
                if fill_price == 0:
                    raise ValueError(f"Ticker returned 0 for {symbol}")
            except Exception as e:
                logger.warning(f"[PAPER] Could not fetch ticker for {symbol}: {e}")

            order.filled_quantity = quantity
            order.avg_fill_price = fill_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)

            await self._update_position(order, fill_price)
            logger.info(
                f"[PAPER] {side.value.upper()} {quantity} {symbol} @ {fill_price}"
            )
        else:
            # Live trading — place real order via CCXT
            ex = await self._get_exchange()
            try:
                ccxt_side = side.value  # "buy" or "sell"
                result = await asyncio.to_thread(
                    ex.create_market_order, symbol, ccxt_side, quantity
                )
                order.filled_quantity = float(result.get('filled', quantity))
                order.avg_fill_price = float(result.get('average', 0))
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now(timezone.utc)
                await self._update_position(order, order.avg_fill_price)
                logger.info(
                    f"[LIVE] {side.value.upper()} {quantity} {symbol} @ "
                    f"{order.avg_fill_price}"
                )
            except Exception as e:
                order.status = OrderStatus.REJECTED
                logger.error(f"[LIVE] Order rejected for {symbol}: {e}")

        # Persist order to PostgreSQL
        await self._save_order(order)
        return order

    async def _update_position(self, order: Order, fill_price: float):
        """Update in-memory position after a filled order."""
        key = f"{order.symbol}_{order.strategy_id}"

        if order.side == OrderSide.BUY:
            if key not in self._positions:
                self._positions[key] = Position(
                    id=uuid4(),
                    strategy_id=order.strategy_id,
                    symbol=order.symbol,
                    side=PositionSide.LONG,
                    quantity=order.filled_quantity,
                    entry_price=fill_price,
                    current_price=fill_price,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    opened_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            else:
                pos = self._positions[key]
                total_qty = pos.quantity + order.filled_quantity
                pos.entry_price = (
                    pos.entry_price * pos.quantity + fill_price * order.filled_quantity
                ) / total_qty
                pos.quantity = total_qty
                pos.current_price = fill_price
                pos.updated_at = datetime.now(timezone.utc)

        elif order.side == OrderSide.SELL:
            if key in self._positions:
                pos = self._positions[key]
                sell_qty = min(order.filled_quantity, pos.quantity)
                pos.quantity -= sell_qty

                # Realized P&L
                pnl = sell_qty * (fill_price - pos.entry_price)
                pos.realized_pnl += pnl

                if pos.quantity <= 1e-9:
                    del self._positions[key]

                pos.updated_at = datetime.now(timezone.utc)

    async def _save_order(self, order: Order):
        """Persist order to PostgreSQL using raw SQL."""
        try:
            async with get_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text("""
                        INSERT INTO execution_orders
                        (id, strategy_id, symbol, side, order_type, quantity,
                         price, filled_quantity, avg_fill_price, status,
                         created_at, filled_at)
                        VALUES
                        (:id, :strategy_id, :symbol, :side, :order_type, :quantity,
                         :price, :filled_quantity, :avg_fill_price, :status,
                         :created_at, :filled_at)
                        ON CONFLICT (id) DO UPDATE SET
                            status = EXCLUDED.status,
                            filled_quantity = EXCLUDED.filled_quantity,
                            avg_fill_price = EXCLUDED.avg_fill_price,
                            filled_at = EXCLUDED.filled_at
                    """),
                    {
                        "id": str(order.id),
                        "strategy_id": str(order.strategy_id),
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "order_type": order.order_type.value,
                        "quantity": order.quantity,
                        "price": order.price,
                        "filled_quantity": order.filled_quantity,
                        "avg_fill_price": order.avg_fill_price,
                        "status": order.status.value,
                        "created_at": order.created_at.replace(tzinfo=None),
                        "filled_at": (
                            order.filled_at.replace(tzinfo=None)
                            if order.filled_at else None
                        ),
                    }
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to save order {order.id}: {e}")

    async def update_positions_from_ticker(self, symbol: str, current_price: float):
        """Refresh unrealized P&L for all positions on a symbol."""
        for key, pos in self._positions.items():
            if pos.symbol == symbol.replace("/", ""):
                pos.current_price = current_price
                pos.unrealized_pnl = (
                    (current_price - pos.entry_price) * pos.quantity
                )
                pos.updated_at = datetime.now(timezone.utc)

    async def get_positions(
        self, strategy_id: Optional[UUID] = None
    ) -> list[Position]:
        """Return open positions, optionally filtered by strategy."""
        return [
            p for p in self._positions.values()
            if strategy_id is None or p.strategy_id == strategy_id
        ]

    async def get_orders(
        self, strategy_id: Optional[UUID] = None, limit: int = 50
    ) -> list[Order]:
        """Return recent orders, newest first."""
        orders = list(self._orders.values())
        if strategy_id:
            orders = [o for o in orders if o.strategy_id == strategy_id]
        return orders[-limit:]