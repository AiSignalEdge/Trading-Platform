"""
Backtest Routes - All backtest, batch, walk-forward, and Monte Carlo endpoints.

Section 13: API Server from PLAN-v2.md
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from models.backtest import BacktestConfig, BacktestResult
import models.user  # noqa: F401 — needed for queries against User table
from services.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


# ====================
# Pydantic Schemas
# ====================

class BacktestConfigCreate(BaseModel):
    name: str
    strategies: list[UUID] = []
    pairs: list[str] = []
    timeframes: list[str] = ["1h", "4h", "1d"]
    start_date: str
    end_date: str
    exchange: str = "binance"
    initial_capital: float = 10000.0
    leverage: float = 1.0
    position_sizing: dict = {}
    max_positions: int = 5
    direction: str = "both"
    fees: dict = {}
    slippage_model: dict = {}
    walk_forward: Optional[dict] = None
    monte_carlo: Optional[dict] = None
    risk_limits: dict = {}


class BacktestConfigResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    strategies: list[str]
    pairs: list[str]
    timeframes: list[str]
    start_date: str
    end_date: str
    exchange: str
    initial_capital: float
    leverage: float
    position_sizing: dict
    max_positions: int
    direction: str
    fees: dict
    slippage_model: dict
    walk_forward: Optional[dict]
    monte_carlo: Optional[dict]
    risk_limits: dict
    created_at: str

    class Config:
        from_attributes = True


class BacktestRunRequest(BaseModel):
    """Request to run a single backtest."""
    config_id: UUID


class BacktestRunResponse(BaseModel):
    """Response with job_id for async backtest run."""
    job_id: str
    config_id: str
    status: str
    message: str


class BacktestResultResponse(BaseModel):
    """Full backtest result with all metrics."""
    id: str
    config_id: str
    pair: Optional[str]
    timeframe: Optional[str]
    strategy_id: Optional[str]
    status: str
    progress_pct: int
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_ms: Optional[int]
    initial_capital: Optional[float]
    final_equity: Optional[float]
    total_return: Optional[float]
    annualized_return: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_pct: Optional[float]
    max_drawdown_duration_days: Optional[int]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    sterling_ratio: Optional[float]
    burke_ratio: Optional[float]
    profit_factor: Optional[float]
    win_rate: Optional[float]
    avg_win_pct: Optional[float]
    avg_loss_pct: Optional[float]
    expectancy: Optional[float]
    total_trades: Optional[int]
    winning_trades: Optional[int]
    losing_trades: Optional[int]
    avg_trade_duration_hours: Optional[float]
    tail_ratio: Optional[float]
    skewness: Optional[float]
    kurtosis: Optional[float]
    information_ratio: Optional[float]
    equity_curve: Optional[dict]
    trades: Optional[dict]
    signals: Optional[dict]
    mae_by_trade: Optional[dict]
    mfe_by_trade: Optional[dict]
    overfit_score: Optional[float]
    warnings: Optional[list[str]]
    settings_used: Optional[dict]

    class Config:
        from_attributes = True


class EquityCurvePoint(BaseModel):
    date: str
    equity: float
    drawdown: float


class TradeDetail(BaseModel):
    trade_id: str
    entry_date: str
    exit_date: Optional[str]
    side: str
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: float
    pnl_pct: float
    mae: Optional[float]
    mfe: Optional[float]
    duration_hours: Optional[float]


class BatchRunRequest(BaseModel):
    """Request to run a batch of backtests."""
    configs: list[BacktestConfigCreate]


class BatchRunResponse(BaseModel):
    """Response for batch backtest initiation."""
    job_id: str
    count: int
    status: str


class BatchProgressResponse(BaseModel):
    """Progress of a batch backtest job."""
    job_id: str
    status: str
    total: int
    completed: int
    failed: int
    progress_pct: float


class BacktestQuickRunRequest(BaseModel):
    """Run a backtest directly from params — creates a config and runs immediately."""
    name: str = "Quick Backtest"
    strategy: str = "ma_cross"
    strategy_params: Optional[dict] = None
    pairs: list[str] = ["BTC/USDT"]
    timeframes: list[str] = ["1h"]
    start_date: str
    end_date: str
    exchange: str = "binance"
    initial_capital: float = 10000.0
    leverage: float = 1.0
    position_sizing: str = "pct_equal"
    max_positions: int = 5
    direction: str = "both"
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_model: str = "dynamic"
    slippage_bps: Optional[float] = None
    walk_forward: str = "off"
    walk_forward_train_days: Optional[int] = None
    walk_forward_test_days: Optional[int] = None
    walk_forward_skip_days: Optional[int] = None
    monte_carlo: str = "off"
    monte_carlo_runs: Optional[int] = None


# ====================
# Routes
# ====================

@router.post("", response_model=BacktestRunResponse)
async def run_backtest(
    request: BacktestRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a single backtest asynchronously.
    Returns job_id for tracking progress.
    """
    # Verify config exists
    result = await db.execute(
        select(BacktestConfig).where(BacktestConfig.id == request.config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Backtest config not found")
    
    # TODO: Enqueue backtest job to background worker
    job_id = str(config.id)  # Placeholder
    
    return BacktestRunResponse(
        job_id=job_id,
        config_id=str(request.config_id),
        status="running",
        message="Backtest job queued successfully",
    )


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest_now(
    request: BacktestRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a single backtest synchronously using the vectorbt engine.
    Returns job_id and status. Use GET /api/backtest/{job_id} to fetch results.
    """
    from datetime import datetime, timedelta, timezone

    # Verify config exists
    result = await db.execute(
        select(BacktestConfig).where(BacktestConfig.id == request.config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Backtest config not found")

    # Map model config to engine config
    engine_cfg = EngineConfig(
        strategy_name=config.name,
        symbols=config.pairs or ["BTC/USDT"],
        timeframe=config.timeframes[0] if config.timeframes else "1h",
        initial_cash=config.initial_capital,
        leverage=config.leverage,
        commission=config.fees.get("taker", 0.001),
        slippage=config.slippage_model.get("spread", 0.0005),
        exchange=config.exchange,
        start_date=datetime.fromisoformat(config.start_date.replace("Z", "+00:00")) if config.start_date else datetime.now(timezone.utc) - timedelta(days=90),
        end_date=datetime.fromisoformat(config.end_date.replace("Z", "+00:00")) if config.end_date else datetime.now(timezone.utc),
    )

    engine = BacktestEngine(engine_cfg)
    job_id = str(config.id)

    try:
        results = await engine.run()
        # Store results in DB
        for r in results:
            db_result = BacktestResult(
                config_id=config.id,
                pair=r.symbol,
                timeframe=r.timeframe,
                status="completed",
                progress_pct=100,
                initial_capital=r.initial_cash,
                final_equity=r.final_equity,
                total_return=r.total_return,
                annualized_return=r.total_return,
                max_drawdown=r.max_drawdown,
                max_drawdown_pct=r.max_drawdown_pct,
                sharpe_ratio=r.sharpe_ratio,
                sortino_ratio=r.sortino_ratio,
                calmar_ratio=r.calmar_ratio,
                profit_factor=r.profit_factor,
                win_rate=r.win_rate,
                total_trades=r.total_trades,
                winning_trades=r.winning_trades,
                losing_trades=r.losing_trades,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(db_result)

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")

    return BacktestRunResponse(
        job_id=job_id,
        config_id=str(request.config_id),
        status="completed",
        message=f"Backtest completed. {len(results)} result(s) generated.",
    )


@router.get("/{backtest_id}", response_model=BacktestResultResponse)
async def get_backtest_result(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a backtest result by ID.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    
    return BacktestResultResponse.model_validate(backtest)


@router.get("/{backtest_id}/equity")
async def get_backtest_equity(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get equity curve points for a backtest.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    
    equity_curve = backtest.equity_curve or []
    return {
        "backtest_id": str(backtest_id),
        "equity_curve": equity_curve,
    }


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get trade log for a backtest.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    
    trades = backtest.trades or []
    return {
        "backtest_id": str(backtest_id),
        "trades": trades,
        "total_trades": len(trades),
    }


@router.delete("/{backtest_id}")
async def delete_backtest_result(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a backtest result.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    
    await db.delete(backtest)
    await db.flush()
    
    return {"message": "Backtest result deleted successfully"}


@router.post("/batch", response_model=BatchRunResponse)
async def run_batch_backtest(
    request: BatchRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a batch of backtests.
    Returns job_id and count of backtests to run.
    """
    # TODO: Create configs and enqueue batch job
    job_id = "batch-" + str(datetime.utcnow().timestamp())
    
    return BatchRunResponse(
        job_id=job_id,
        count=len(request.configs),
        status="queued",
    )


@router.get("/batch/{job_id}", response_model=BatchProgressResponse)
async def get_batch_progress(
    job_id: str,
):
    """
    Get progress of a batch backtest job.
    """
    # TODO: Query batch job status from Redis/db
    return BatchProgressResponse(
        job_id=job_id,
        status="running",
        total=0,
        completed=0,
        failed=0,
        progress_pct=0.0,
    )


@router.get("/batch/{job_id}/results")
async def get_batch_results(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all results from a batch backtest job.
    """
    # TODO: Query results by batch job_id
    return {
        "job_id": job_id,
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("/walk-forward", response_model=BacktestRunResponse)
async def run_walk_forward(
    config_data: BacktestConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Run walk-forward analysis.
    Trains on in-sample data, tests on out-of-sample.
    Returns overfit score.
    """
    # TODO: Create config with walk_forward settings and enqueue job
    job_id = "wf-" + str(datetime.utcnow().timestamp())
    
    return BacktestRunResponse(
        job_id=job_id,
        config_id=job_id,
        status="running",
        message="Walk-forward analysis job queued",
    )


@router.get("/walk-forward/{job_id}", response_model=BacktestResultResponse)
async def get_walk_forward_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get walk-forward analysis result with overfit score.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == job_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Walk-forward result not found")
    
    return BacktestResultResponse.model_validate(backtest)


@router.post("/monte-carlo", response_model=BacktestRunResponse)
async def run_monte_carlo(
    config_data: BacktestConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Run Monte Carlo simulation with randomized parameters.
    """
    # TODO: Create config with monte_carlo settings and enqueue job
    job_id = "mc-" + str(datetime.utcnow().timestamp())
    
    return BacktestRunResponse(
        job_id=job_id,
        config_id=job_id,
        status="running",
        message="Monte Carlo simulation job queued",
    )


@router.get("/monte-carlo/{job_id}", response_model=BacktestResultResponse)
async def get_monte_carlo_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get Monte Carlo simulation result.
    """
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == job_id)
    )
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Monte Carlo result not found")
    
    return BacktestResultResponse.model_validate(backtest)


@router.post("/quick-run")
async def quick_run_backtest(
    request: BacktestQuickRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a BacktestConfig from raw params, then run it immediately.
    Returns full result with all metrics — no config_id pre-creation needed.
    """
    from datetime import date
    from uuid import uuid4 as uuid_gen

    # Get or create a default user for this demo
    try:
        user_result = await db.execute(select(func.max(models.user.id)))
        default_user_id = user_result.scalar() or uuid_gen()
    except Exception:
        default_user_id = uuid_gen()

    # Build fees dict
    fees = {"maker": request.maker_fee, "taker": request.taker_fee}

    # Build slippage dict
    slippage = {"model": request.slippage_model}
    if request.slippage_bps:
        slippage["spread"] = request.slippage_bps / 10000.0

    # Build walk_forward dict
    walk_forward_cfg = None
    if request.walk_forward != "off":
        walk_forward_cfg = {
            "mode": request.walk_forward,
            "train_days": request.walk_forward_train_days or 60,
            "test_days": request.walk_forward_test_days or 14,
            "skip_days": request.walk_forward_skip_days or 0,
        }

    # Build monte_carlo dict
    monte_carlo_cfg = None
    if request.monte_carlo != "off":
        runs = int(request.monte_carlo) if request.monte_carlo.isdigit() else (request.monte_carlo_runs or 500)
        monte_carlo_cfg = {"runs": runs}

    # Create config in DB
    config = BacktestConfig(
        id=uuid_gen(),
        name=request.name,
        owner_id=default_user_id,
        strategies=[],
        pairs=request.pairs,
        timeframes=request.timeframes,
        start_date=date.fromisoformat(request.start_date),
        end_date=date.fromisoformat(request.end_date),
        exchange=request.exchange,
        initial_capital=request.initial_capital,
        leverage=request.leverage,
        position_sizing={"type": request.position_sizing},
        max_positions=request.max_positions,
        direction=request.direction,
        fees=fees,
        slippage_model=slippage,
        walk_forward=walk_forward_cfg,
        monte_carlo=monte_carlo_cfg,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Build engine config
    from datetime import datetime, timedelta, timezone as tz
    engine_cfg = EngineConfig(
        strategy_name=request.strategy,
        symbols=request.pairs,
        timeframe=request.timeframes[0] if request.timeframes else "1h",
        initial_cash=request.initial_capital,
        leverage=request.leverage,
        commission=request.taker_fee,
        slippage=request.slippage_bps / 10000.0 if request.slippage_bps else 0.0005,
        exchange=request.exchange,
        start_date=datetime.fromisoformat(request.start_date.replace("Z", "+00:00")) if request.start_date else datetime.now(tz.utc) - timedelta(days=60),
        end_date=datetime.fromisoformat(request.end_date.replace("Z", "+00:00")) if request.end_date else datetime.now(tz.utc),
    )

    engine = BacktestEngine(engine_cfg)

    try:
        engine_results = await engine.run()
        if not engine_results:
            raise HTTPException(status_code=500, detail="Backtest produced no results")

        r = engine_results[0]

        # Serialize trade log
        trade_log = [
            {
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "entry_price": t.entry_price,
                "side": t.side,
                "size": t.size,
                "pnl": t.pnl,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "exit_price": t.exit_price,
                "commission": t.commission,
            }
            for t in r.trades
        ]

        # Persist result
        db_result = BacktestResult(
            config_id=config.id,
            pair=r.symbol,
            timeframe=r.timeframe,
            status="completed",
            progress_pct=100,
            initial_capital=r.initial_cash,
            final_equity=r.final_equity,
            total_return=r.total_return,
            annualized_return=r.total_return,
            max_drawdown=r.max_drawdown,
            max_drawdown_pct=r.max_drawdown_pct,
            sharpe_ratio=r.sharpe_ratio,
            sortino_ratio=r.sortino_ratio,
            calmar_ratio=r.calmar_ratio,
            profit_factor=r.profit_factor,
            win_rate=r.win_rate,
            avg_win_pct=r.avg_win_pct,
            avg_loss_pct=r.avg_loss_pct,
            expectancy=r.expectancy,
            total_trades=r.total_trades,
            winning_trades=r.winning_trades,
            losing_trades=r.losing_trades,
            equity_curve={"curve": r.equity_curve},
            trades={"trades": trade_log},
            settings_used={
                "strategy": request.strategy,
                "maker_fee": request.maker_fee,
                "taker_fee": request.taker_fee,
                "slippage": slippage,
            },
        )
        db.add(db_result)
        await db.commit()
        await db.refresh(db_result)

        # Build response from to_dict to ensure proper str serialization
        result_dict = db_result.to_dict()
        # Flatten metrics into top-level response
        return {
            "backtest_id": result_dict["id"],
            "config_id": result_dict["config_id"],
            "pair": result_dict["pair"],
            "timeframe": result_dict["timeframe"],
            "status": result_dict["status"],
            "message": "Backtest completed successfully",
            "metrics": {
                "total_return": result_dict.get("total_return"),
                "annualized_return": result_dict.get("annualized_return"),
                "max_drawdown": result_dict.get("max_drawdown"),
                "max_drawdown_pct": result_dict.get("max_drawdown_pct"),
                "sharpe_ratio": result_dict.get("sharpe_ratio"),
                "sortino_ratio": result_dict.get("sortino_ratio"),
                "calmar_ratio": result_dict.get("calmar_ratio"),
                "profit_factor": result_dict.get("profit_factor"),
                "win_rate": result_dict.get("win_rate"),
                "expectancy": result_dict.get("expectancy"),
                "total_trades": result_dict.get("total_trades"),
                "winning_trades": result_dict.get("winning_trades"),
                "losing_trades": result_dict.get("losing_trades"),
                "avg_win_pct": result_dict.get("avg_win_pct"),
                "avg_loss_pct": result_dict.get("avg_loss_pct"),
            },
            "equity_curve": result_dict.get("equity_curve", {}).get("curve", []) if result_dict.get("equity_curve") else [],
            "trade_log": result_dict.get("trades", {}).get("trades", []) if result_dict.get("trades") else [],
            "metadata": {
                "strategy": request.strategy,
                "initial_capital": result_dict.get("initial_capital"),
                "final_equity": result_dict.get("final_equity"),
                "started_at": result_dict.get("started_at"),
                "completed_at": result_dict.get("completed_at"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        # Save failed result
        db_result = BacktestResult(
            config_id=config.id,
            pair=request.pairs[0] if request.pairs else "BTC/USDT",
            timeframe=request.timeframes[0] if request.timeframes else "1h",
            status="failed",
            progress_pct=0,
            settings_used={"strategy": request.strategy, "error": str(e)},
        )
        db.add(db_result)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")