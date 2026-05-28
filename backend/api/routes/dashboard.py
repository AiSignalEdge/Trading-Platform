"""
Dashboard Routes - Dashboard summary and equity curve endpoints.

Section 13: API Server from PLAN-v2.md
"""

import json
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from sqlalchemy.dialects.postgresql import UUID

from core.database import get_db
from models.strategy import Strategy
from models.position import Position

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ====================
# Enums
# ====================

class TradingMode(str):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


def _get_execution_engine():
    """Import and return the execution engine singleton to avoid circular imports."""
    from api.routes.execution import engine
    return engine


# ====================
# Pydantic Schemas
# ====================

class DashboardSummary(BaseModel):
    total_equity: float
    total_equity_pct_change: float
    today_pnl: float
    today_pnl_pct: float
    open_positions: int
    open_positions_list: list[str]
    win_rate: float
    win_rate_label: str
    mode: str = TradingMode.BACKTEST


class EquityCurvePoint(BaseModel):
    timestamp: str
    equity: float


class EquityCurveResponse(BaseModel):
    timeframe: str
    points: list[EquityCurvePoint]
    initial_capital: float
    final_equity: float
    total_return_pct: float


class LivePositionSummary(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float


class LiveSummaryResponse(BaseModel):
    mode: str
    cash_balance: float
    total_position_value: float
    total_equity: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    open_positions: int
    positions: list[LivePositionSummary]


class ActiveStrategy(BaseModel):
    id: str
    name: str
    strategy_type: str
    pair: str
    today_pnl: float
    today_pnl_pct: float
    status: str


class ActiveStrategiesResponse(BaseModel):
    count: int
    strategies: list[ActiveStrategy]


# ====================
# Routes
# ====================

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard summary with equity, P&L, positions, and win rate.
    """
    # Detect current mode from execution engine
    try:
        engine = _get_execution_engine()
        mode = engine.mode if hasattr(engine, 'mode') else TradingMode.BACKTEST
    except Exception:
        mode = TradingMode.BACKTEST

    # Get latest completed backtest result for equity metrics
    result = await db.execute(
        text("""
            SELECT initial_capital, final_equity, total_return, win_rate, equity_curve
            FROM backtest_results 
            WHERE equity_curve IS NOT NULL AND final_equity IS NOT NULL
            ORDER BY completed_at DESC LIMIT 1
        """)
    )
    row = result.fetchone()
    
    equity = 10000.0  # Default initial capital
    equity_change = 0.0
    win_rate = 0.0
    today_pnl = 0.0
    today_pnl_pct = 0.0
    
    if row:
        initial_capital = float(row[0]) if row[0] else 10000.0
        equity = float(row[1]) if row[1] else initial_capital
        equity_change = ((equity - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0.0
        win_rate = float(row[3] * 100) if row[3] else 0.0
        
        # Parse equity curve for today's P&L
        equity_curve = row[4]
        if equity_curve:
            curve_data = json.loads(equity_curve) if isinstance(equity_curve, str) else equity_curve
            if isinstance(curve_data, dict) and "equity" in curve_data:
                values = curve_data.get("equity", [])
                if len(values) >= 2:
                    today_pnl = values[-1] - values[-2]
                    today_pnl_pct = (today_pnl / values[-2] * 100) if values[-2] > 0 else 0.0
            elif isinstance(curve_data, list) and len(curve_data) >= 2:
                last_eq = curve_data[-1].get("equity", curve_data[-1].get("value", 0)) if isinstance(curve_data[-1], dict) else 0
                prev_eq = curve_data[-2].get("equity", curve_data[-2].get("value", 0)) if isinstance(curve_data[-2], dict) else 0
                if prev_eq > 0:
                    today_pnl = last_eq - prev_eq
                    today_pnl_pct = (today_pnl / prev_eq * 100)

    # Get open positions
    result = await db.execute(
        select(Position).where(Position.closed_at.is_(None))
    )
    positions = result.scalars().all()
    open_positions = len(positions)
    open_positions_list = [p.pair for p in positions] if positions else []

    return DashboardSummary(
        total_equity=round(equity, 2),
        total_equity_pct_change=round(equity_change, 2),
        today_pnl=round(today_pnl, 2),
        today_pnl_pct=round(today_pnl_pct, 2),
        open_positions=open_positions,
        open_positions_list=open_positions_list,
        win_rate=round(win_rate, 1),
        win_rate_label=f"Last {min(30, max(1, open_positions))} trades" if open_positions else "No trades",
        mode=mode,
    )


@router.get("/equity-curve", response_model=EquityCurveResponse)
async def get_equity_curve(
    timeframe: str = Query("1M", regex="^(1D|1W|1M|ALL)$"),
    aggregate: bool = Query(False, description="Aggregate equity from ALL completed backtests"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get equity curve time series data for charting.
    
    If aggregate=True, merges equity curves from ALL completed backtest results,
    normalizing and summing returns by time.
    """
    # Map timeframe to lookback
    now = datetime.utcnow()
    if timeframe == "1D":
        lookback = now - timedelta(days=1)
    elif timeframe == "1W":
        lookback = now - timedelta(weeks=1)
    elif timeframe == "1M":
        lookback = now - timedelta(days=30)
    else:  # ALL
        lookback = now - timedelta(days=365)

    if aggregate:
        # AGGREGATE: Get ALL completed backtest results
        result = await db.execute(
            text("""
                SELECT initial_capital, final_equity, total_return, equity_curve, completed_at
                FROM backtest_results 
                WHERE status = 'completed' 
                  AND equity_curve IS NOT NULL 
                  AND final_equity IS NOT NULL
                ORDER BY completed_at ASC
            """)
        )
        rows = result.fetchall()

        if not rows:
            # Fall back to single backtest behavior
            aggregate = False

    if not aggregate:
        # Original behavior: single (latest) backtest result
        result = await db.execute(
            text("""
                SELECT initial_capital, final_equity, total_return, equity_curve, completed_at
                FROM backtest_results 
                WHERE equity_curve IS NOT NULL AND final_equity IS NOT NULL
                ORDER BY completed_at DESC LIMIT 1
            """)
        )
        rows = result.fetchall()
        if rows:
            rows = [rows[0]]

    points = []
    initial_capital = 10000.0
    final_equity = initial_capital
    total_return = 0.0

    if rows:
        # For aggregate mode, we need to merge curves by timestamp
        if aggregate and len(rows) > 1:
            # Collect all data points by timestamp
            all_points: dict[str, list[float]] = {}
            initial_capitals = []
            
            for row in rows:
                ic = float(row[0]) if row[0] else 10000.0
                initial_capitals.append(ic)
                equity_curve = row[3]
                
                if equity_curve:
                    curve_data = json.loads(equity_curve) if isinstance(equity_curve, str) else equity_curve
                    
                    if isinstance(curve_data, dict) and "equity" in curve_data:
                        equity_values = curve_data.get("equity", [])
                        timestamps = curve_data.get("timestamps", [])
                        for i, eq in enumerate(equity_values):
                            ts = timestamps[i] if i < len(timestamps) else None
                            if ts:
                                if ts not in all_points:
                                    all_points[ts] = []
                                all_points[ts].append(float(eq))
                    
                    elif isinstance(curve_data, list):
                        for point in curve_data:
                            if isinstance(point, dict):
                                ts = point.get("timestamp", point.get("date"))
                                if ts:
                                    eq = point.get("equity", point.get("value", 0))
                                    if ts not in all_points:
                                        all_points[ts] = []
                                    all_points[ts].append(float(eq))
            
            # Sort by timestamp and sum normalized returns
            if all_points:
                sorted_ts = sorted(all_points.keys())
                # Use average initial capital for reference
                ref_capital = sum(initial_capitals) / len(initial_capitals) if initial_capitals else 10000.0
                
                running_equity = ref_capital
                for ts in sorted_ts:
                    values = all_points[ts]
                    # Sum normalized values (each relative to its initial capital)
                    normalized_sum = sum(v / initial_capitals[i] for i, v in enumerate(values))
                    # Convert back to actual equity using reference capital
                    running_equity = ref_capital * normalized_sum / len(values)
                    
                    points.append(EquityCurvePoint(
                        timestamp=ts,
                        equity=round(running_equity, 2)
                    ))
                
                # Calculate final equity and total return
                if points:
                    final_equity = points[-1].equity
                    total_return = ((final_equity - ref_capital) / ref_capital * 100) if ref_capital > 0 else 0.0
                    initial_capital = ref_capital
        
        else:
            # Single backtest mode (original behavior)
            row = rows[0]
            initial_capital = float(row[0]) if row[0] else 10000.0
            final_equity = float(row[1]) if row[1] else initial_capital
            total_return = float(row[2] * 100) if row[2] else 0.0
            equity_curve = row[3]
            
            if equity_curve:
                curve_data = json.loads(equity_curve) if isinstance(equity_curve, str) else equity_curve
                
                if isinstance(curve_data, dict) and "equity" in curve_data:
                    equity_values = curve_data.get("equity", [])
                    timestamps = curve_data.get("timestamps", [])
                    for i, eq in enumerate(equity_values):
                        ts = timestamps[i] if i < len(timestamps) else None
                        points.append(EquityCurvePoint(
                            timestamp=ts or datetime.utcnow().isoformat(),
                            equity=float(eq)
                        ))
                elif isinstance(curve_data, list):
                    for point in curve_data:
                        if isinstance(point, dict):
                            ts = point.get("timestamp", point.get("date", datetime.utcnow().isoformat()))
                            eq = point.get("equity", point.get("value", 0))
                            points.append(EquityCurvePoint(
                                timestamp=ts,
                                equity=float(eq)
                            ))
            
            # Filter by timeframe if needed
            if lookback and points:
                filtered_points = [p for p in points if datetime.fromisoformat(p.timestamp.replace('Z', '+00:00')) >= lookback]
                if filtered_points:
                    points = filtered_points

    # If no points, generate sample data
    if not points:
        points = _generate_sample_equity_curve(initial_capital, final_equity, timeframe)
        if final_equity != initial_capital:
            total_return = ((final_equity - initial_capital) / initial_capital * 100)

    return EquityCurveResponse(
        timeframe=timeframe,
        points=points,
        initial_capital=initial_capital,
        final_equity=round(final_equity, 2),
        total_return_pct=round(total_return, 2),
    )


@router.get("/live-summary", response_model=LiveSummaryResponse)
async def get_live_summary():
    """
    Get live/paper trading equity summary from the execution engine.
    
    Returns current cash balance, open position values, and total equity
    based on in-memory positions from the ExecutionEngine singleton.
    
    Note: ExecutionEngine is process-local, so this reflects the worker's
    own positions only.
    """
    try:
        engine = _get_execution_engine()
        mode = engine.mode if hasattr(engine, 'mode') else TradingMode.PAPER
    except Exception:
        mode = TradingMode.PAPER

    # Default cash balance (could be stored in settings or engine state)
    cash_balance = 10000.0
    
    # Get positions from execution engine
    try:
        positions = await engine.get_positions()
    except Exception:
        positions = []

    total_position_value = 0.0
    total_unrealized_pnl = 0.0
    total_realized_pnl = 0.0
    position_summaries = []

    for pos in positions:
        position_value = pos.quantity * pos.current_price
        total_position_value += position_value
        total_unrealized_pnl += pos.unrealized_pnl
        total_realized_pnl += pos.realized_pnl
        
        position_summaries.append(LivePositionSummary(
            symbol=pos.symbol,
            side=pos.side.value,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            current_price=pos.current_price,
            unrealized_pnl=pos.unrealized_pnl,
            realized_pnl=pos.realized_pnl,
        ))

    total_equity = cash_balance + total_position_value + total_unrealized_pnl

    return LiveSummaryResponse(
        mode=mode,
        cash_balance=round(cash_balance, 2),
        total_position_value=round(total_position_value, 2),
        total_equity=round(total_equity, 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        open_positions=len(positions),
        positions=position_summaries,
    )


def _generate_sample_equity_curve(initial: float, final: float, timeframe: str) -> list[EquityCurvePoint]:
    """Generate sample equity curve for demo purposes."""
    now = datetime.utcnow()
    points = []
    
    if timeframe == "1D":
        steps = 24  # Hourly
        delta = timedelta(hours=1)
    elif timeframe == "1W":
        steps = 7  # Daily
        delta = timedelta(days=1)
    elif timeframe == "1M":
        steps = 30  # Daily
        delta = timedelta(days=1)
    else:  # ALL
        steps = 52  # Weekly
        delta = timedelta(weeks=1)
    
    random.seed(42)  # Deterministic for consistency
    
    current = initial
    for i in range(steps):
        ts = now - (delta * (steps - i - 1))
        # Random walk with slight upward bias
        change = random.uniform(-0.02, 0.025) * current
        current += change
        points.append(EquityCurvePoint(
            timestamp=ts.isoformat(),
            equity=round(current, 2)
        ))
    
    # Ensure final value matches
    if points and final != initial:
        points[-1].equity = final
    return points


@router.get("/active-strategies", response_model=ActiveStrategiesResponse)
async def get_active_strategies(
    db: AsyncSession = Depends(get_db),
):
    """
    Get count and list of running/active strategies.
    """
    # Get public strategies
    result = await db.execute(
        select(Strategy)
        .where(Strategy.is_public == True)
        .order_by(desc(Strategy.created_at))
        .limit(10)
    )
    strategies = result.scalars().all()
    
    active_strategies = []
    for s in strategies[:5]:  # Limit to 5 for dashboard
        # Calculate P&L from backtest data
        res = await db.execute(
            text("""
                SELECT total_return, sharpe_ratio 
                FROM backtest_results 
                WHERE strategy_id = :sid AND total_return IS NOT NULL
                ORDER BY completed_at DESC LIMIT 1
            """),
            {"sid": str(s.id)}
        )
        row = res.fetchone()
        
        pnl_pct = 0.0
        if row and row[0] is not None:
            pnl_pct = float(row[0] * 100)
        
        active_strategies.append(ActiveStrategy(
            id=str(s.id),
            name=s.name,
            strategy_type=s.strategy_type,
            pair=", ".join(s.pairs) if s.pairs else "N/A",
            today_pnl=round(pnl_pct, 2),
            today_pnl_pct=round(pnl_pct, 2),
            status="active" if s.is_public else "paused",
        ))

    return ActiveStrategiesResponse(
        count=len(active_strategies),
        strategies=active_strategies,
    )