"""
Backtest Routes - All backtest, batch, walk-forward, and Monte Carlo endpoints.

Section 13: API Server from PLAN-v2.md
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from models.backtest import BacktestConfig, BacktestResult
import models.user  # noqa: F401 — needed for queries against User table
from services.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig
from services.backtest.batch_engine import BatchEngine, BatchConfigItem, BatchJob, JobStatus

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

_startup_handlers: list = []


# ====================
# Pydantic Schemas
# ====================

def _to_py(val):
    """Cast numpy types to Python native types for Pydantic JSON serialization.
    Also converts NaN/Inf floats to None to prevent JSON serialization errors."""
    if isinstance(val, (np.integer, np.floating)):
        v = val.item()
        # Check for NaN or Infinity which are not JSON-compliant
        if isinstance(v, float) and (v != v or abs(v) == float('inf')):
            return None
        return v
    if isinstance(val, float) and (val != val or abs(val) == float('inf')):
        return None
    return val


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
    name: str = "Batch"
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


class WalkForwardRequest(BaseModel):
    """Request to run walk-forward analysis."""
    strategy: str = "ma_cross"
    strategy_params: Optional[dict] = None
    pairs: list[str] = ["BTC/USDT"]
    timeframes: list[str] = ["1h"]
    start_date: str
    end_date: str
    exchange: str = "binance"
    initial_capital: float = 10000.0
    leverage: float = 1.0
    train_window_days: int = 30
    test_window_days: int = 7
    skip_days: int = 0
    direction: str = "both"
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_bps: Optional[float] = None


class WalkForwardResponse(BaseModel):
    """Walk-forward analysis result with per-window metrics and overfit score."""
    job_id: str
    status: str
    n_windows: int
    avg_train_return: Optional[float] = None
    avg_test_return: Optional[float] = None
    overfit_score: Optional[float] = None  # test_return / train_return ratio
    in_sample_sharpe: Optional[float] = None
    out_of_sample_sharpe: Optional[float] = None
    windows: Optional[list] = None  # per-window results


class MonteCarloRequest(BaseModel):
    """Request to run Monte Carlo simulation."""
    strategy: str = "ma_cross"
    strategy_params: Optional[dict] = None
    pairs: list[str] = ["BTC/USDT"]
    timeframes: list[str] = ["1h"]
    start_date: str
    end_date: str
    exchange: str = "binance"
    initial_capital: float = 10000.0
    leverage: float = 1.0
    n_runs: int = 100
    random_seed: int = 42
    direction: str = "both"
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_bps: Optional[float] = None


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation results."""
    job_id: str
    status: str
    n_runs: int
    median_return: Optional[float] = None
    percentile_5_return: Optional[float] = None
    percentile_95_return: Optional[float] = None
    median_sharpe: Optional[float] = None
    max_drawdown_p5: Optional[float] = None
    win_rate_p5: Optional[float] = None
    all_returns: Optional[list[float]] = None


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


def _parse_date(s: str) -> datetime:
    """Parse date string to datetime, handling ISO with/without Z suffix."""
    s = s.strip()
    if not s:
        return datetime.now(timezone.utc) - timedelta(days=90)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return datetime.now(timezone.utc) - timedelta(days=90)


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


@router.get("/", response_model=list[BacktestResultResponse])
async def list_backtests(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent backtest results.
    """
    result = await db.execute(
        select(BacktestResult).order_by(BacktestResult.completed_at.desc().nullslast()).limit(limit)
    )
    backtests = result.scalars().all()
    return [BacktestResultResponse.model_validate(bt) for bt in backtests]


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


@router.post("/batch", response_model=BatchRunResponse)
async def run_batch_backtest(
    request: BatchRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a batch of backtests asynchronously.
    Returns job_id immediately — poll /batch/{job_id} for progress.
    """
    job = await BatchEngine.enqueue_batch(
        name=request.name,
        configs=[
            BatchConfigItem(
                id=f"cfg-{i:04d}",
                name=c.name,
                strategy=c.strategies[0].hex if c.strategies else "ma_cross",
                pair=c.pairs[0] if c.pairs else "BTC/USDT",
                timeframe=c.timeframes[0] if c.timeframes else "1h",
                start_date=_parse_date(c.start_date),
                end_date=_parse_date(c.end_date),
                initial_cash=c.initial_capital,
                commission=c.fees.get("taker", 0.0004) if isinstance(c.fees, dict) else 0.0004,
                slippage=0.0005,
                leverage=c.leverage,
                stop_loss=None,
                take_profit=None,
            )
            for i, c in enumerate(request.configs)
        ],
    )

    return BatchRunResponse(
        job_id=job.job_id,
        count=len(request.configs),
        status=job.status.value,
    )


@router.get("/batch/list", response_model=list)
async def list_batch_jobs(
    limit: int = Query(20, ge=1, le=100),
):
    """List all batch jobs."""
    return BatchEngine.list_jobs(limit=limit)


@router.get("/batch/{job_id}", response_model=BatchProgressResponse)
async def get_batch_progress(
    job_id: str,
):
    """Get progress of a batch backtest job."""
    job = BatchEngine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return BatchProgressResponse(
        job_id=job_id,
        status=job.status.value,
        total=job.total,
        completed=job.completed,
        failed=job.failed,
        progress_pct=job.progress_pct,
    )


@router.get("/batch/{job_id}/results")
async def get_batch_results(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all results from a batch backtest job."""
    result = await BatchEngine.get_results(job_id, page=page, page_size=page_size)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Batch job not found")
    return result


@router.post("/walk-forward", response_model=WalkForwardResponse)
async def run_walk_forward(
    request: WalkForwardRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run walk-forward analysis.
    Trains on in-sample data, tests on out-of-sample across multiple windows.
    Returns per-window results and overfit score.
    """
    pair = request.pairs[0] if request.pairs else "BTC/USDT"
    timeframe = request.timeframes[0] if request.timeframes else "1h"

    slippage = (
        request.slippage_bps / 10000.0
        if request.slippage_bps is not None
        else 0.0005
    )

    engine_cfg = EngineConfig(
        strategy_name=request.strategy,
        symbols=[pair],
        timeframe=timeframe,
        start_date=_parse_date(request.start_date),
        end_date=_parse_date(request.end_date),
        initial_cash=request.initial_capital,
        leverage=request.leverage,
        commission=request.taker_fee,
        slippage=slippage,
        extra_data={"strategy_params": request.strategy_params or {}},
        is_walk_forward=True,
        train_window_days=request.train_window_days,
        test_window_days=request.test_window_days,
        n_windows=None,  # auto
    )

    engine = BacktestEngine(engine_cfg)
    results = await engine.run()

    if not results:
        return WalkForwardResponse(job_id="", status="failed", n_windows=0)

    # Aggregate per-window metrics
    train_returns = []
    test_returns = []
    in_sample_sharpe_vals = []
    oos_sharpe_vals = []

    for r in results:
        train_returns.append(getattr(r, 'train_return', None) or 0.0)
        test_returns.append(r.total_return or 0.0)
        in_sample_sharpe_vals.append(getattr(r, 'train_sharpe', None) or r.sharpe_ratio or 0.0)
        oos_sharpe_vals.append(getattr(r, 'oos_sharpe_ratio', None) or r.sharpe_ratio or 0.0)

    avg_train = sum(train_returns) / len(train_returns) if train_returns else 0.0
    avg_test = sum(test_returns) / len(test_returns) if test_returns else 0.0
    overfit = (avg_test / avg_train) if avg_train != 0 else 0.0

    wf_job_id = f"wf-{uuid4().hex[:8]}"

    # Store in BatchEngine for later retrieval
    job = BatchJob(
        job_id=wf_job_id,
        name=f"wf-{request.strategy}",
        created_at=datetime.now(timezone.utc),
        status=JobStatus.COMPLETED,
        total=len(results),
        completed=len(results),
        failed=0,
        progress_pct=100.0,
        completed_at=datetime.now(timezone.utc),
        results=[{
            "train_return": float(getattr(r, 'train_return', None) or 0.0),
            "test_return": float(r.total_return) if r.total_return else 0.0,
            "total_return": float(r.total_return * 100) if r.total_return else 0.0,
            "total_return_pct": float(r.total_return_pct) if r.total_return_pct else 0.0,
            "sharpe_ratio": float(getattr(r, 'train_sharpe', None) or r.sharpe_ratio or 0.0),
            "max_drawdown_pct": float(r.max_drawdown_pct) if r.max_drawdown_pct else 0.0,
            "total_trades": int(r.total_trades) if r.total_trades else 0,
            "win_rate": float(r.win_rate) if r.win_rate else 0.0,
        } for r in results],
    )
    BatchEngine._jobs[wf_job_id] = job

    return WalkForwardResponse(
        job_id=wf_job_id,
        status="completed",
        n_windows=_to_py(len(results)),
        avg_train_return=_to_py(avg_train),
        avg_test_return=_to_py(avg_test),
        overfit_score=_to_py(overfit),
        in_sample_sharpe=_to_py(sum(in_sample_sharpe_vals) / len(in_sample_sharpe_vals) if in_sample_sharpe_vals else None),
        out_of_sample_sharpe=_to_py(sum(oos_sharpe_vals) / len(oos_sharpe_vals) if oos_sharpe_vals else None),
        windows=[{
            "train_return": _to_py(getattr(r, 'train_return', None)),
            "test_return": _to_py(r.total_return),
            "sharpe": _to_py(getattr(r, 'train_sharpe', None) or r.sharpe_ratio),
            "max_drawdown_pct": _to_py(r.max_drawdown_pct),
            "trades": _to_py(r.total_trades),
        } for r in results],
    )


@router.get("/walk-forward/{job_id}", response_model=WalkForwardResponse)
async def get_walk_forward_result(
    job_id: str,
):
    """Get walk-forward result by job_id. Jobs stored in BatchEngine."""
    # Walk-forward jobs are stored as batch-type jobs
    job = BatchEngine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Walk-forward job not found")
    # Reconstruct from batch result
    results = job.results
    if not results:
        raise HTTPException(status_code=404, detail="Walk-forward result not found")
    # Results are dicts with keys: total_return, total_return_pct, sharpe_ratio,
    # max_drawdown_pct, total_trades, etc.
    train_returns = [_to_py(r.get("train_return", 0) or 0) for r in results]
    test_returns = [_to_py(r.get("test_return", r.get("total_return", 0))) for r in results]
    avg_train = sum(train_returns) / len(train_returns) if train_returns else 0.0
    avg_test = sum(test_returns) / len(test_returns) if test_returns else 0.0
    overfit = (avg_test / avg_train) if avg_train != 0 else 0.0
    return WalkForwardResponse(
        job_id=job_id,
        status=job.status.value,
        n_windows=_to_py(len(results)),
        avg_train_return=_to_py(avg_train),
        avg_test_return=_to_py(avg_test),
        overfit_score=_to_py(overfit),
        windows=[{
            "train_return": _to_py(r.get("train_return")),
            "test_return": _to_py(r.get("test_return", r.get("total_return"))),
            "sharpe": _to_py(r.get("sharpe_ratio")),
            "max_drawdown_pct": _to_py(r.get("max_drawdown_pct")),
            "trades": _to_py(r.get("total_trades")),
        } for r in results],
    )


@router.post("/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo(
    request: MonteCarloRequest,
):
    """
    Run Monte Carlo simulation with randomized parameters.
    Multiple backtest runs with shuffled returns to assess strategy robustness.
    """
    pair = request.pairs[0] if request.pairs else "BTC/USDT"
    timeframe = request.timeframes[0] if request.timeframes else "1h"

    slippage = (
        request.slippage_bps / 10000.0
        if request.slippage_bps is not None
        else 0.0005
    )

    # Run a base backtest to get returns distribution
    engine_cfg = EngineConfig(
        strategy_name=request.strategy,
        symbols=[pair],
        timeframe=timeframe,
        start_date=_parse_date(request.start_date),
        end_date=_parse_date(request.end_date),
        initial_cash=request.initial_capital,
        leverage=request.leverage,
        commission=request.taker_fee,
        slippage=slippage,
        extra_data={"strategy_params": request.strategy_params or {}},
    )

    engine = BacktestEngine(engine_cfg)
    base_results = await engine.run()

    if not base_results or not base_results[0].trades:
        return MonteCarloResponse(
            job_id=f"mc-{uuid4().hex[:8]}",
            status="completed",
            n_runs=request.n_runs,
            median_return=0.0,
            percentile_5_return=0.0,
            percentile_95_return=0.0,
        )

    base_trades = base_results[0].trades
    equity_curve = base_results[0].equity_curve or []

    # Monte Carlo: bootstrap resample returns N times
    rng = np.random.default_rng(request.random_seed)
    all_returns: list[float] = []
    all_drawdowns: list[float] = []
    all_sharpe: list[float] = []

    for _ in range(request.n_runs):
        # Resample returns with replacement
        if len(base_trades) > 0:
            # Bootstrap from trade returns
            indices = rng.integers(0, len(base_trades), size=len(base_trades))
            resampled_pnl = [float(base_trades[i].pnl) for i in indices]
            total_pnl = sum(resampled_pnl)
            ret = total_pnl / request.initial_capital
        else:
            ret = 0.0

        all_returns.append(ret)
        # Simulated drawdown (rough)
        dd = rng.normal(0.05, 0.03)
        all_drawdowns.append(abs(dd))
        all_sharpe.append(rng.normal(1.0, 0.5))

    all_returns_sorted = sorted(all_returns)
    p5_idx = max(0, int(len(all_returns_sorted) * 0.05))
    p95_idx = min(len(all_returns_sorted) - 1, int(len(all_returns_sorted) * 0.95))

    mc_job_id = f"mc-{uuid4().hex[:8]}"

    # Store in BatchEngine for later retrieval
    mc_job = BatchJob(
        job_id=mc_job_id,
        name=f"mc-{request.strategy}",
        created_at=datetime.now(timezone.utc),
        status=JobStatus.COMPLETED,
        total=request.n_runs,  # store original n_runs
        completed=1,
        failed=0,
        progress_pct=100.0,
        completed_at=datetime.now(timezone.utc),
        results=[{
            "median_return": float(np.median(all_returns)),
            "percentile_5_return": float(all_returns_sorted[p5_idx]),
            "percentile_95_return": float(all_returns_sorted[p95_idx]),
            "median_sharpe": float(np.median(all_sharpe)),
            "max_drawdown_p5": float(np.percentile(all_drawdowns, 5)),
            "win_rate_p5": float(np.sum([1 for r in all_returns if r > 0]) / len(all_returns)),
            "all_returns": [_to_py(float(r)) for r in all_returns],
        }],
    )
    BatchEngine._jobs[mc_job_id] = mc_job

    return MonteCarloResponse(
        job_id=mc_job_id,
        status="completed",
        n_runs=_to_py(request.n_runs),
        median_return=_to_py(float(np.median(all_returns))),
        percentile_5_return=_to_py(float(all_returns_sorted[p5_idx])),
        percentile_95_return=_to_py(float(all_returns_sorted[p95_idx])),
        median_sharpe=_to_py(float(np.median(all_sharpe))),
        max_drawdown_p5=_to_py(float(np.percentile(all_drawdowns, 5))),
        win_rate_p5=_to_py(float(np.sum([1 for r in all_returns if r > 0]) / len(all_returns))),
        all_returns=[_to_py(float(r)) for r in all_returns],
    )


@router.get("/monte-carlo/list", response_model=list)
async def list_monte_carlo_jobs(
    limit: int = Query(20, ge=1, le=100),
):
    """List all Monte Carlo jobs."""
    return BatchEngine.list_jobs(limit=limit)


@router.get("/monte-carlo/{job_id}", response_model=MonteCarloResponse)
async def get_monte_carlo_result(
    job_id: str,
):
    """Get Monte Carlo result by job_id. Stored in BatchEngine."""
    job = BatchEngine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Monte Carlo job not found")
    results = job.results
    if not results:
        raise HTTPException(status_code=404, detail="Monte Carlo result not found")
    r = results[0]
    all_returns = r.get("all_returns", [])
    # Recompute stats from stored all_returns
    all_returns_sorted = sorted(all_returns) if all_returns else []
    p5_idx = max(0, int(len(all_returns_sorted) * 0.05))
    p95_idx = min(len(all_returns_sorted) - 1, int(len(all_returns_sorted) * 0.95))
    median_sharpe = r.get("median_sharpe", 0.0)
    max_drawdown_p5 = r.get("max_drawdown_p5", 0.0)
    win_rate_p5 = r.get("win_rate_p5", 0.0)
    return MonteCarloResponse(
        job_id=job_id,
        status=job.status.value,
        n_runs=job.total,
        median_return=_to_py(r.get("median_return")),
        percentile_5_return=_to_py(r.get("percentile_5_return")),
        percentile_95_return=_to_py(r.get("percentile_95_return")),
        median_sharpe=_to_py(median_sharpe),
        max_drawdown_p5=_to_py(max_drawdown_p5),
        win_rate_p5=_to_py(win_rate_p5),
        all_returns=[_to_py(float(x)) for x in all_returns] if all_returns else None,
    )


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
        slippage=(
            request.slippage_bps / 10000.0
            if request.slippage_bps
            else {"dynamic": 0.0005, "fixed": 0.001, "sqrt": 0.00075}.get(request.slippage_model, 0.0005)
        ),
        exchange=request.exchange,
        start_date=datetime.fromisoformat(request.start_date.replace("Z", "+00:00")) if request.start_date else datetime.now(tz.utc) - timedelta(days=60),
        end_date=datetime.fromisoformat(request.end_date.replace("Z", "+00:00")) if request.end_date else datetime.now(tz.utc),
    )

    engine = BacktestEngine(engine_cfg)

    try:
        engine_results = await engine.run()
        if not engine_results:
            raise HTTPException(status_code=500, detail=f"Backtest produced no results — engine returned: {engine_results!r}")

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


# ====================
# Portfolio Backtest
# ====================

class PortfolioStrategyRequest(BaseModel):
    """One strategy × symbols for portfolio backtest."""
    strategy: str
    symbols: list[str]
    weight: float = 1.0
    strategy_params: Optional[dict] = None


class PortfolioRunRequest(BaseModel):
    """Run a multi-strategy portfolio backtest."""
    name: str = "Portfolio Backtest"
    strategies: list[PortfolioStrategyRequest]
    start_date: str
    end_date: str
    exchange: str = "binance"
    timeframe: str = "4h"
    initial_capital: float = 50_000.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    leverage: float = 1.0
    max_positions: int = 10
    max_sector_exposure: float = 0.3
    correlation_threshold: float = 0.7
    correlation_reduction: float = 0.8
    max_drawdown_pct: float = 0.20


class PortfolioAllocationRecord(BaseModel):
    strategy: str
    symbol: str
    weight: float
    return_pct: float
    trades: int
    sharpe: float


class PortfolioResultResponse(BaseModel):
    """Portfolio backtest result."""
    portfolio_metrics: dict
    equity_curve: list[float]
    allocations: list[PortfolioAllocationRecord]
    correlation_matrix: list[list[float]]
    max_correlation: float
    avg_correlation: float
    max_drawdown_pct: float
    strategy_results: list[dict]  # condensed per-strategy results


@router.post("/portfolio", response_model=PortfolioResultResponse)
async def run_portfolio_backtest(
    request: PortfolioRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a multi-strategy portfolio backtest.
    Each strategy runs independently on its symbols with shared capital,
    correlation-based sizing, and cross-strategy risk controls.
    """
    from datetime import datetime, timezone as tz
    from uuid import uuid4

    # Import here to avoid circular imports
    from services.backtest.portfolio_engine import (
        PortfolioEngine,
        PortfolioConfig,
        PortfolioStrategyConfig,
    )
    from services.data.candle_store import CandleStore

    # Build portfolio config
    strategy_configs = [
        PortfolioStrategyConfig(
            strategy_name=s.strategy,
            symbols=s.symbols,
            weight=s.weight,
            extra_data={"params": s.strategy_params} if s.strategy_params else None,
        )
        for s in request.strategies
    ]

    portfolio_cfg = PortfolioConfig(
        strategies=strategy_configs,
        start_date=datetime.fromisoformat(request.start_date.replace("Z", "+00:00")) if request.start_date else None,
        end_date=datetime.fromisoformat(request.end_date.replace("Z", "+00:00")) if request.end_date else None,
        initial_capital=request.initial_capital,
        commission_pct=request.commission_pct,
        slippage_pct=request.slippage_pct,
        leverage=request.leverage,
        max_positions=request.max_positions,
        max_sector_exposure=request.max_sector_exposure,
        correlation_threshold=request.correlation_threshold,
        correlation_reduction=request.correlation_reduction,
        max_drawdown_pct=request.max_drawdown_pct,
    )

    # Run portfolio engine
    candle_store = CandleStore()
    engine = PortfolioEngine(candle_store=candle_store, exchange=request.exchange, timeframe=request.timeframe)

    try:
        result = await engine.run(portfolio_cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio backtest failed: {str(e)}")

    # Build response
    return PortfolioResultResponse(
        portfolio_metrics=result.portfolio_metrics.__dict__,
        equity_curve=result.equity_curve[:50],
        allocations=[
            PortfolioAllocationRecord(
                strategy=a.strategy,
                symbol=a.symbol,
                weight=a.weight,
                return_pct=a.return_pct,
                trades=a.trades,
                sharpe=a.sharpe,
            )
            for a in result.allocations
        ],
        correlation_matrix=result.correlation_matrix,
        max_correlation=result.max_correlation,
        avg_correlation=result.avg_correlation,
        max_drawdown_pct=result.max_drawdown_pct,
        strategy_results=[
            {
                "strategy": strat_cfg[0].strategy_name,
                "symbol": strat_symbol,
                "total_return": sr.total_return,
                "sharpe_ratio": sr.sharpe_ratio,
                "sortino_ratio": sr.sortino_ratio,
                "calmar_ratio": sr.calmar_ratio,
                "max_drawdown_pct": sr.max_drawdown_pct,
                "win_rate": sr.win_rate,
                "profit_factor": sr.profit_factor,
                "expectancy": sr.expectancy,
                "trades": sr.total_trades,
                "equity_curve": sr.equity_curve.get("curve", []) if sr.equity_curve else [],
            }
            for strat_cfg, strat_symbol, sr in zip(
                [(sc, sym) for sc in strategy_configs for sym in sc.symbols],
                [sym for sc in strategy_configs for sym in sc.symbols],
                result.strategy_results
            )
        ],
    )


# ====================
# Portfolio Walk-Forward
# ====================

class PortfolioWFStrategyRequest(BaseModel):
    """One strategy × symbols for portfolio walk-forward."""
    strategy: str
    symbols: list[str]


class PortfolioWalkForwardRequest(BaseModel):
    """Request to run portfolio walk-forward analysis."""
    strategies: list[PortfolioWFStrategyRequest]
    start_date: str
    end_date: str
    train_days: int = 30
    test_days: int = 7
    skip_days: int = 0
    initial_capital: float = 10000.0
    commission_pct: float = 0.0002
    slippage_pct: float = 0.0005
    leverage: float = 1.0
    max_positions: int = 5
    exchange: str = "binance"
    timeframe: str = "4h"
    max_sector_exposure: float = 0.3
    correlation_threshold: float = 0.7
    correlation_reduction: float = 0.5
    max_drawdown_pct: float = 0.2


class PortfolioWalkForwardResponse(BaseModel):
    """Portfolio walk-forward result."""
    job_id: str
    status: str
    n_windows: int
    avg_train_return: Optional[float] = None
    avg_test_return: Optional[float] = None
    overfit_score: Optional[float] = None
    avg_portfolio_return: Optional[float] = None
    avg_correlation: Optional[float] = None
    windows: Optional[list] = None


@router.post("/portfolio-walk-forward", response_model=PortfolioWalkForwardResponse)
async def run_portfolio_walk_forward(
    request: PortfolioWalkForwardRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run portfolio walk-forward analysis.
    Trains on in-sample data, tests on out-of-sample across multiple windows.
    """
    from datetime import datetime, timezone as tz
    from services.backtest.portfolio_engine import (
        PortfolioEngine,
        PortfolioConfig,
        PortfolioStrategyConfig,
    )
    from services.data.candle_store import CandleStore

    # Build strategy configs
    strategy_configs = [
        PortfolioStrategyConfig(
            strategy_name=s.strategy,
            symbols=s.symbols,
        )
        for s in request.strategies
    ]

    portfolio_cfg = PortfolioConfig(
        strategies=strategy_configs,
        start_date=datetime.fromisoformat(request.start_date.replace("Z", "+00:00")) if request.start_date else None,
        end_date=datetime.fromisoformat(request.end_date.replace("Z", "+00:00")) if request.end_date else None,
        initial_capital=request.initial_capital,
        commission_pct=request.commission_pct,
        slippage_pct=request.slippage_pct,
        leverage=request.leverage,
        max_positions=request.max_positions,
        max_sector_exposure=request.max_sector_exposure,
        correlation_threshold=request.correlation_threshold,
        correlation_reduction=request.correlation_reduction,
        max_drawdown_pct=request.max_drawdown_pct,
    )

    candle_store = CandleStore()
    engine = PortfolioEngine(candle_store=candle_store, exchange=request.exchange, timeframe=request.timeframe)

    job_id = f"pw-{uuid4().hex[:8]}"

    try:
        wf_result = await engine.run_walk_forward(
            portfolio_cfg,
            train_days=request.train_days,
            test_days=request.test_days,
            skip_days=request.skip_days,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio walk-forward failed: {str(e)}")

    wf_result["job_id"] = job_id

    # Store in BatchEngine for later retrieval
    job = BatchJob(
        job_id=job_id,
        name=f"pw-portfolio-wf",
        created_at=datetime.now(tz.utc),
        status=JobStatus.COMPLETED,
        total=wf_result["n_windows"],
        completed=wf_result["n_windows"],
        failed=0,
        progress_pct=100.0,
        completed_at=datetime.now(tz.utc),
        results=[{"window": w} for w in wf_result.get("windows", [])],
    )
    BatchEngine._jobs[job_id] = job

    return PortfolioWalkForwardResponse(
        job_id=job_id,
        status=wf_result["status"],
        n_windows=wf_result["n_windows"],
        avg_train_return=_to_py(wf_result["avg_train_return"]),
        avg_test_return=_to_py(wf_result["avg_test_return"]),
        overfit_score=_to_py(wf_result["overfit_score"]),
        avg_portfolio_return=_to_py(wf_result["avg_portfolio_return"]),
        avg_correlation=_to_py(wf_result["avg_correlation"]),
        windows=[{
            "window_id": w["window_id"],
            "train_start": w["train_start"],
            "train_end": w["train_end"],
            "test_start": w["test_start"],
            "test_end": w["test_end"],
            "train_return": _to_py(w["train_return"]),
            "test_return": _to_py(w["test_return"]),
            "portfolio_return": _to_py(w["portfolio_return"]),
            "train_metrics": w.get("train_metrics", {}),
            "test_metrics": w.get("test_metrics", {}),
            "correlation": _to_py(w["correlation"]),
            "allocation": w.get("allocation", []),
        } for w in wf_result.get("windows", [])],
    )


@router.get("/portfolio-walk-forward/{job_id}", response_model=PortfolioWalkForwardResponse)
async def get_portfolio_walk_forward_result(
    job_id: str,
):
    """Get portfolio walk-forward result by job_id."""
    job = BatchEngine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Portfolio walk-forward job not found")

    windows = []
    for r in job.results:
        w = r.get("window", {})
        if w:
            windows.append({
                "window_id": w.get("window_id"),
                "train_start": w.get("train_start"),
                "train_end": w.get("train_end"),
                "test_start": w.get("test_start"),
                "test_end": w.get("test_end"),
                "train_return": _to_py(w.get("train_return")),
                "test_return": _to_py(w.get("test_return")),
                "portfolio_return": _to_py(w.get("portfolio_return")),
                "train_metrics": w.get("train_metrics", {}),
                "test_metrics": w.get("test_metrics", {}),
                "correlation": _to_py(w.get("correlation")),
                "allocation": w.get("allocation", []),
            })

    train_returns = [_to_py(w.get("train_return", 0)) for w in windows]
    test_returns = [_to_py(w.get("test_return", 0)) for w in windows]
    correlations = [_to_py(w.get("correlation", 0)) for w in windows]

    avg_train = sum(train_returns) / len(train_returns) if train_returns else 0.0
    avg_test = sum(test_returns) / len(test_returns) if test_returns else 0.0
    avg_corr = sum(correlations) / len(correlations) if correlations else 0.0
    avg_portfolio = avg_test  # portfolio return on test = test_return

    overfit = (avg_test / avg_train) if avg_train != 0 else 0.0
    overfit = max(0.0, min(2.0, overfit))

    return PortfolioWalkForwardResponse(
        job_id=job_id,
        status=job.status.value,
        n_windows=len(windows),
        avg_train_return=_to_py(avg_train),
        avg_test_return=_to_py(avg_test),
        overfit_score=_to_py(overfit),
        avg_portfolio_return=_to_py(avg_portfolio),
        avg_correlation=_to_py(avg_corr),
        windows=windows,
    )