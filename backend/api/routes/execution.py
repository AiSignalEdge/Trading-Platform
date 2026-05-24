"""
Execution routes — market order execution and position/order queries.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from models.execution import OrderSide
from services.execution.execution_engine import ExecutionEngine

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])

# Singleton execution engine — paper mode by default
engine = ExecutionEngine(exchange="binance", mode="paper")


class MarketOrderRequest(BaseModel):
    symbol: str  # "BTC/USDT"
    side: str  # "buy" or "sell"
    quantity: float
    strategy_id: str  # UUID as string


@router.post("/orders/market")
async def place_market_order(req: MarketOrderRequest):
    """Place a market order in paper trading mode."""
    side = OrderSide.BUY if req.side.lower() == "buy" else OrderSide.SELL

    order = await engine.market_order(
        symbol=req.symbol,
        side=side,
        quantity=req.quantity,
        strategy_id=UUID(req.strategy_id),
    )

    return {
        "order_id": str(order.id),
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "filled_quantity": order.filled_quantity,
        "avg_fill_price": order.avg_fill_price,
        "status": order.status.value,
        "created_at": order.created_at.isoformat(),
        "filled_at": (
            order.filled_at.isoformat() if order.filled_at else None
        ),
    }


@router.get("/positions")
async def get_positions(strategy_id: Optional[str] = None):
    """Get current positions, optionally filtered by strategy."""
    sid = UUID(strategy_id) if strategy_id else None
    positions = await engine.get_positions(strategy_id=sid)

    return {
        "positions": [
            {
                "id": str(p.id),
                "strategy_id": str(p.strategy_id),
                "symbol": p.symbol,
                "side": p.side.value,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "realized_pnl": p.realized_pnl,
            }
            for p in positions
        ]
    }


@router.get("/orders")
async def get_orders(strategy_id: Optional[str] = None, limit: int = 50):
    """Get recent orders, optionally filtered by strategy."""
    sid = UUID(strategy_id) if strategy_id else None
    orders = await engine.get_orders(strategy_id=sid, limit=limit)

    return {
        "orders": [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": o.side.value,
                "order_type": o.order_type.value,
                "quantity": o.quantity,
                "filled_quantity": o.filled_quantity,
                "avg_fill_price": o.avg_fill_price,
                "status": o.status.value,
                "created_at": o.created_at.isoformat(),
                "filled_at": (
                    o.filled_at.isoformat() if o.filled_at else None
                ),
            }
            for o in orders
        ]
    }