# Trading System — Full Implementation Plan
**Version 2.0 — Production Grade**
*Incorporates: Event-Driven Architecture, Risk Engine, OMS, Strategy Versioning, Multi-Strategy Portfolios, Advanced Slippage, Point-in-Time Validation, Market Regime Analysis, Proper Walk-Forward, All Missing Metrics, Batch Throttling, Backtest State Persistence*

---

## Table of Contents

1. [Concept & Vision](#1-concept--vision)
2. [System Architecture](#2-system-architecture)
3. [Event Pipeline](#3-event-pipeline)
4. [Domain Models](#4-domain-models)
5. [Database Schema](#5-database-schema)
6. [Core Services](#6-core-services)
7. [Strategy Library](#7-strategy-library)
8. [Backtest Engine](#8-backtest-engine)
9. [Risk Management Engine](#9-risk-management-engine)
10. [Order Management System (OMS)](#10-order-management-system-oms)
11. [Execution Layer](#11-execution-layer)
12. [Frontend Pages](#12-frontend-pages)
13. [API Server](#13-api-server)
14. [Real-time Features](#14-real-time-features)
15. [AI Strategy Generation](#15-ai-strategy-generation)
16. [File Structure](#16-file-structure)
17. [Tech Stack](#17-tech-stack)
18. [Implementation Phases](#18-implementation-phases)
19. [Environment Setup](#19-environment-setup)
20. [Metrics Reference](#20-metrics-reference)
21. [Advanced Features](#21-advanced-features)
22. [Risk Registry](#22-risk-registry)
23. [Gaps Fixed From v1](#23-gaps-fixed-from-v1)

---

## 1. Concept & Vision

A **production-grade quantitative trading research lab** — not a toy backtester.

The system is built around one core principle: **a strategy's behavior must be identical from backtest to live execution**. This is achieved through event-driven architecture where every signal, order, fill, and position update flows through the same pipeline regardless of context.

**Core capabilities:**
- Browse, search, and filter thousands of community strategies
- Run event-driven backtests across any combination of pair, timeframe, and date range
- Multi-strategy portfolio backtesting with cross-strategy risk controls
- Schedule automated batch backtesting with intelligent throttling
- Compare strategies with full statistical rigor
- Export to TradingView / connect to live execution
- Walk-forward validation with overfit scoring
- Monte Carlo simulation with regime awareness

**Personality:** Dense, data-rich, professional. Dark theme. Every number is traceable. Every decision is logged. No black boxes.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                    │
│  Next.js 14 + Tailwind + Lightweight Charts + TanStack Query        │
│  WebSocket for live updates, React Query for REST polling            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼─────────────────────────────────────────┐
│                         API SERVER (FastAPI)                          │
│  Strategies  Backtest  Jobs  Pairs  Auth  AI  Health                 │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────▼────────┐ ┌────────▼────────┐ ┌──────▼──────┐
│ Data Ingestion  │ │  Strategy       │ │  Risk       │
│ Service         │ │  Engine         │ │  Engine     │
│ (CCXT +         │ │  (Signal →      │ │  (Pre-trade │
│  Validation)    │ │   Order)        │ │   checks)   │
└────────┬────────┘ └────────┬────────┘ └──────┬──────┘
         │                   │                 │
┌────────▼────────┐ ┌────────▼────────┐ ┌──────▼──────┐
│ Market Regime   │ │  OMS            │ │  Execution  │
│ Analyzer        │ │  (Order state,  │ │  Adapter    │
│ (trend/range/  │ │   fills, pos)   │ │  (Binance)  │
│  vol regime)   │ │                 │ │             │
└─────────────────┘ └─────────────────┘ └─────────────┘
         │                   │                 │
         └───────────────────┼─────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     DATA LAYER              │
              │  PostgreSQL (state, results) │
              │  Redis (cache, queue, pub/sub)│
              │  Local filesystem (candles)  │
              └─────────────────────────────┘
```

**Design Principles:**
1. **Separation of concerns** — Strategy engine doesn't know how orders are routed; Execution doesn't know what generated the signal
2. **Determinism** — Same inputs → Same outputs. All RNG is seedable.
3. **Fail-safe defaults** — If a risk check fails, pause. Cost of missed opportunity < cost of catastrophic error
4. **Point-in-time correctness** — No look-ahead bias anywhere in the system
5. **Identical behavior** — Same strategy runs the same way in backtest and live

---

## 3. Event Pipeline

All system state changes flow through this event bus (in-memory + Redis pub/sub for multi-process):

```python
# Event types — all events are immutable dataclasses
class EventType(Enum):
    TICK = "tick"                    # Raw market data tick
    CANDLE = "candle"                # OHLCV candle closed
    SIGNAL = "signal"                # Strategy signal generated
    ORDER_REQUEST = "order_request"  # Order proposed (pre-risk)
    ORDER_REJECTED = "order_rejected" # Risk engine rejected
    ORDER_SUBMITTED = "order_submitted" # Sent to exchange
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_UPDATE = "portfolio_update"  # Equity changed
    REGIME_CHANGE = "regime_change"        # Market regime shifted

@dataclass
class BaseEvent:
    event_id: UUID
    timestamp: datetime
    event_type: EventType
    source: str  # strategy_id, exchange, etc.

@dataclass
class CandleEvent(BaseEvent):
    pair: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class SignalEvent(BaseEvent):
    pair: str
    direction: Literal["long", "short", "close"]
    strength: float  # 0.0–1.0
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    strategy_id: UUID
    signal_id: UUID

@dataclass
class OrderEvent(BaseEvent):
    order_id: UUID
    signal_id: UUID | None
    pair: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop", "take_profit"]
    quantity: float
    price: float | None
    filled_price: float | None
    filled_quantity: float
    commission: float
    slippage_bps: float

@dataclass
class PositionEvent(BaseEvent):
    position_id: UUID
    pair: str
    side: Literal["long", "short"]
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
```

### Event Bus Implementation

```python
class EventBus:
    """In-memory event bus with Redis pub/sub for multi-process"""

    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)
        self._handlers: dict[EventType, list[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, event: BaseEvent):
        # Persist to Redis for cross-process subscribers
        await self.redis.publish(
            "events",
            json.dumps(self._serialize(event))
        )
        # Process locally
        for handler in self._handlers.get(event.event_type, []):
            await handler(event)

    def subscribe(self, event_type: EventType, handler: Callable):
        self._handlers.setdefault(event_type, []).append(handler)
```

### Pipeline Flow

```
CandleEvent (exchange)
    → DataValidationLayer (stale check, crossed market, spread sanity)
    → CandleStore (persist)
    → MarketRegimeAnalyzer (update regime)
    → StrategyEngine (for each active strategy)
    → SignalScoring + PortfolioConstruction
    → RiskManager (pre-trade checks: exposure, correlation, drawdown)
    → OMS.order_request()
    → ExchangeAdapter (Binance/Coinbase/etc.)
    → OrderEvent (fill/partial/reject)
    → PositionTracker
    → PortfolioUpdate
    → PerformanceAnalyst (update metrics)
```

---

## 4. Domain Models

```python
@dataclass
class Strategy:
    id: UUID
    name: str
    description: str
    author: str
    version: int
    strategy_type: StrategyType  # momentum, mean_reversion, etc.
    asset_class: AssetClass
    pairs: list[str]
    timeframes: list[str]
    parameters: dict  # JSON-serializable params
    pine_script: str
    tags: list[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    current_version_id: UUID  # points to StrategyVersion.id

@dataclass
class StrategyVersion:
    id: UUID
    strategy_id: UUID
    version: int
    parameters: dict
    pine_script: str
    created_at: datetime
    created_by: str
    changelog: str

@dataclass
class Order:
    id: UUID
    signal_id: UUID | None
    strategy_id: UUID
    pair: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None  # None = market order
    filled_quantity: float
    avg_fill_price: float
    commission: float
    slippage_bps: float
    status: OrderStatus  # pending, submitted, partial, filled, cancelled, failed
    created_at: datetime
    updated_at: datetime
    exchange_order_id: str | None  # exchange's order ID
    error_message: str | None

@dataclass
class Position:
    id: UUID
    strategy_id: UUID
    pair: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    updated_at: datetime

@dataclass
class Portfolio:
    id: UUID
    name: str
    strategies: list[UUID]  # strategy IDs in this portfolio
    initial_capital: float
    current_equity: float
    cash: float
    positions: list[Position]
    total_unrealized_pnl: float
    leverage: float

@dataclass
class BacktestConfig:
    id: UUID
    name: str
    strategies: list[UUID]  # can be 1 or many
    portfolio_config: PortfolioConfig
    pairs: list[str]
    timeframes: list[str]
    start_date: date
    end_date: date
    exchange: str
    fees: FeeConfig
    slippage_model: SlippageModel
    walk_forward: WalkForwardConfig | None
    monte_carlo: MonteCarloConfig | None
    risk_limits: RiskLimits

@dataclass
class BacktestResult:
    id: UUID
    config_id: UUID
    pair: str
    timeframe: str
    initial_capital: float
    final_equity: float
    metrics: PerformanceMetrics  # see Metrics Reference
    equity_curve: list[EquityPoint]  # daily
    trades: list[Trade]
    signals: list[SignalRecord]
    warnings: list[str]  # e.g. "data gap detected at day 45"
    overfit_score: float | None  # walk-forward only
    created_at: datetime
```

---

## 5. Database Schema

### `strategy_versions`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| strategy_id | UUID | FK → strategies |
| version | INT | Sequential version number |
| parameters | JSONB | Snapshot of strategy params |
| pine_script | TEXT | Snapshot of Pine Script |
| created_at | TIMESTAMP | Version creation time |
| created_by | VARCHAR(255) | Author |
| changelog | TEXT | What changed |

### `strategies`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(255) | Display name |
| description | TEXT | Long description |
| author | VARCHAR(255) | Creator |
| current_version_id | UUID | FK → strategy_versions |
| strategy_type | ENUM | momentum, mean_reversion, grid, arbitrage, moon_phase, breakout, custom |
| asset_class | ENUM | crypto, forex, stocks, commodities |
| pairs | TEXT[] | Supported pairs |
| timeframes | TEXT[] | Supported timeframes |
| tags | TEXT[] | Searchable tags |
| rating | FLOAT | 0–5 |
| backtest_count | INT | Number of backtests run |
| is_public | BOOLEAN | Community visibility |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### `backtest_configs`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(255) | |
| owner_id | UUID | FK → users |
| strategies | UUID[] | Array of strategy IDs |
| pairs | TEXT[] | |
| timeframes | TEXT[] | |
| start_date | DATE | |
| end_date | DATE | |
| exchange | VARCHAR(50) | |
| initial_capital | DECIMAL | |
| leverage | DECIMAL | |
| position_sizing | JSONB | |
| max_positions | INT | |
| direction | ENUM | long, short, both |
| fees | JSONB | |
| slippage_model | JSONB | |
| walk_forward | JSONB | |
| monte_carlo | JSONB | |
| risk_limits | JSONB | |
| created_at | TIMESTAMP | |

### `backtest_results`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| config_id | UUID | FK → backtest_configs |
| pair | VARCHAR(50) | |
| timeframe | VARCHAR(20) | |
| strategy_id | UUID | FK → strategies (denormalized for queries) |
| status | ENUM | running, completed, failed, cancelled |
| progress_pct | INT | 0–100 |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| duration_ms | INT | |
| initial_capital | DECIMAL | |
| final_equity | DECIMAL | |
| total_return | DECIMAL | |
| annualized_return | DECIMAL | |
| max_drawdown | DECIMAL | |
| max_drawdown_pct | DECIMAL | |
| max_drawdown_duration_days | INT | |
| sharpe_ratio | DECIMAL | |
| sortino_ratio | DECIMAL | |
| calmar_ratio | DECIMAL | |
| sterling_ratio | DECIMAL | |
| burke_ratio | DECIMAL | |
| profit_factor | DECIMAL | |
| win_rate | DECIMAL | |
| avg_win_pct | DECIMAL | |
| avg_loss_pct | DECIMAL | |
| expectancy | DECIMAL | |
| total_trades | INT | |
| winning_trades | INT | |
| losing_trades | INT | |
| avg_trade_duration_hours | DECIMAL | |
| tail_ratio | DECIMAL | |
| skewness | DECIMAL | |
| kurtosis | DECIMAL | |
| tail_ratio | DECIMAL | |
| information_ratio | DECIMAL | |
| equity_curve | JSONB | [{date, equity, drawdown}] |
| trades | JSONB | Full trade log |
| signals | JSONB | Full signal log |
| mae_by_trade | JSONB | [{trade_id, mae}] |
| mfe_by_trade | JSONB | [{trade_id, mfe}] |
| overfit_score | DECIMAL | Walk-forward metric |
| warnings | TEXT[] | Data quality issues |
| settings_used | JSONB | Exact config snapshot |

### `orders`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| backtest_result_id | UUID | FK → backtest_results (null if live) |
| order_type | ENUM | market, limit, stop, take_profit |
| side | ENUM | buy, sell |
| pair | VARCHAR(50) | |
| quantity | DECIMAL | |
| price | DECIMAL | |
| filled_quantity | DECIMAL | |
| avg_fill_price | DECIMAL | |
| commission | DECIMAL | |
| slippage_bps | DECIMAL | |
| status | ENUM | pending, submitted, partial, filled, cancelled, failed |
| exchange_order_id | VARCHAR(255) | |
| error_message | TEXT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### `positions`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| order_id | UUID | FK → orders |
| strategy_id | UUID | FK |
| pair | VARCHAR(50) | |
| side | ENUM | long, short |
| quantity | DECIMAL | |
| entry_price | DECIMAL | |
| current_price | DECIMAL | |
| unrealized_pnl | DECIMAL | |
| stop_loss | DECIMAL | |
| take_profit | DECIMAL | |
| opened_at | TIMESTAMP | |
| closed_at | TIMESTAMP | |

### `automated_jobs`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(255) | |
| backtest_config_id | UUID | FK → backtest_configs |
| schedule | CRON | Cron expression |
| params | JSONB | Overrides |
| status | ENUM | active, paused, failed |
| consecutive_failures | INT | |
| total_runs | INT | |
| last_run_at | TIMESTAMP | |
| next_run_at | TIMESTAMP | |
| last_result_id | UUID | FK → backtest_results |
| created_by | VARCHAR(255) | |

### `market_regimes`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| pair | VARCHAR(50) | |
| timeframe | VARCHAR(20) | |
| date | DATE | |
| regime | ENUM | trending_up, trending_down, ranging, high_vol, low_vol |
| trend_strength | DECIMAL | ADX or similar |
| volatility_rank | DECIMAL | percentile |
| created_at | TIMESTAMP | |

### `users`
| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| username | VARCHAR(255) | Unique |
| email | VARCHAR(255) | |
| password_hash | VARCHAR(255) | |
| plan | ENUM | free, pro, enterprise |
| telegram_chat_id | VARCHAR(255) | For notifications |
| notification_prefs | JSONB | |
| created_at | TIMESTAMP | |

---

## 6. Core Services

### 6.1 Data Ingestion Service

```python
class DataIngestionService:
    """Fetches, validates, and stores market data"""

    def __init__(self, exchange: ExchangeAdapter, candle_store: CandleStore):
        self.exchange = exchange
        self.candle_store = candle_store

    async def fetch_and_validate(
        self,
        pair: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> list[Candle]:
        """Fetch from exchange, validate, store"""
        candles = await self.exchange.fetch_ohlcv(pair, timeframe, start, end)
        validated = []
        for c in candles:
            if not self._validate(c):
                self._log_warning(f"Invalid candle at {c.timestamp}: {c}")
                continue
            validated.append(c)
        await self.candle_store.store_many(validated)
        return validated

    def _validate(self, candle: Candle) -> bool:
        """Point-in-time validation — no look-ahead possible"""
        # 1. Crossed market (high < low)
        if candle.high < candle.low:
            return False
        # 2. Zero or negative prices
        if candle.close <= 0 or candle.open <= 0:
            return False
        # 3. Abnormal spread (> 5% of price)
        spread_pct = (candle.high - candle.low) / candle.close
        if spread_pct > 0.05:
            return False
        # 4. Abnormal volume (0 when shouldn't be)
        # 5. Close outside high/low (data error)
        if candle.close < candle.low or candle.close > candle.high:
            return False
        return True

    async def backfill_gaps(self, pair: str, timeframe: str):
        """Detect and fill gaps in historical data"""
        stored = await self.candle_store.get_range(pair, timeframe, start, end)
        gaps = self._find_gaps(stored)
        for gap in gaps:
            await self.fetch_and_validate(pair, timeframe, gap.start, gap.end)
```

### 6.2 Market Regime Analyzer

```python
class MarketRegimeAnalyzer:
    """Determines market regime for each pair/timeframe"""

    REGIMES = {
        "trending_up":   {"description": "Strong uptrend"},
        "trending_down": {"description": "Strong downtrend"},
        "ranging":      {"description": "Sideways / mean-reversion environment"},
        "high_vol":     {"description": "High volatility regardless of direction"},
        "low_vol":      {"description": "Low volatility / consolidation"},
    }

    def __init__(self, candle_store: CandleStore):
        self.candle_store = candle_store

    async def analyze(
        self,
        pair: str,
        timeframe: str,
        as_of: datetime
    ) -> MarketRegime:
        """
        Determine current regime using multiple indicators:
        - ADX for trend strength
        - Bollinger Band width for volatility
        - Slope of 200-period SMA for direction
        """
        candles = await self.candle_store.get_recent(
            pair, timeframe, as_of, lookback=200
        )
        adx = self._calculate_adx(candles)
        bb_width = self._calculate_bb_width(candles)
        sma_slope = self._calculate_sma_slope(candles, period=200)

        # Regime classification
        if adx > 25 and sma_slope > 0.001:
            return "trending_up"
        elif adx > 25 and sma_slope < -0.001:
            return "trending_down"
        elif adx < 20 and bb_width < 0.02:
            return "low_vol"
        elif adx < 20 and bb_width > 0.05:
            return "high_vol"
        else:
            return "ranging"

    def get_regime_adjustment(self, regime: str, strategy_type: str) -> float:
        """
        Returns a multiplier to adjust strategy signal strength based on regime.
        E.g., mean-reversion strategies should reduce size in trending markets.
        """
        adjustments = {
            ("mean_reversion", "trending_up"): 0.5,
            ("mean_reversion", "trending_down"): 0.5,
            ("mean_reversion", "ranging"): 1.0,
            ("momentum", "trending_up"): 1.0,
            ("momentum", "trending_down"): 0.7,
            ("momentum", "ranging"): 0.6,
            ("breakout", "high_vol"): 1.2,
            ("breakout", "low_vol"): 0.8,
        }
        return adjustments.get((strategy_type, regime), 1.0)
```

### 6.3 Strategy Engine

```python
class StrategyEngine:
    """Runs strategies and generates signals"""

    def __init__(
        self,
        event_bus: EventBus,
        indicator_registry: IndicatorRegistry,
        risk_manager: RiskManager,
    ):
        self.event_bus = event_bus
        self.indicator_registry = indicator_registry
        self.risk_manager = risk_manager

    async def on_candle(self, event: CandleEvent):
        """Called on each new candle — compute indicators + signals"""
        for strategy in self._get_active_strategies(pair=event.pair):
            signals = strategy.compute(event.candle)

            for signal in signals:
                # Apply regime adjustment
                regime = await self.regime_analyzer.analyze(
                    event.pair, event.timeframe, event.timestamp
                )
                adj = self.regime_analyzer.get_regime_adjustment(
                    regime, strategy.strategy_type
                )
                signal.strength *= adj

                # Risk pre-check
                risk_result = await self.risk_manager.check_signal(signal)
                if not risk_result.approved:
                    await self.event_bus.publish(SignalRejectedEvent(...))
                    continue

                await self.event_bus.publish(SignalEvent(...))


class BaseStrategy(ABC):
    """All strategies inherit from this"""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.indicators = {}
        self.position_state = None

    @abstractmethod
    def compute(self, candle: Candle) -> list[Signal]:
        """Return signals for this candle"""
        pass

    @abstractmethod
    def get_required_indicators(self) -> list[str]:
        """List indicator names needed (for efficient computation)"""
        pass

    def load_state(self, state: dict):
        """Resume from saved state (for backtest continuity)"""
        self.position_state = state.get("position")
        for name, value in state.get("indicators", {}).items():
            self.indicators[name] = value

    def save_state(self) -> dict:
        """Save state for backtest persistence"""
        return {
            "position": self.position_state,
            "indicators": self.indicators,
        }
```

### 6.4 Strategy Registry

Built-in strategies with full parameter definitions:

| Strategy | Type | Key Params |
|---|---|---|
| **MA Crossover** | momentum | fast_period, slow_period, ma_type, direction |
| **Bollinger + RSI** | mean_reversion | bb_period, bb_std, rsi_period, rsi_entry, rsi_exit |
| **MACD Momentum** | momentum | macd_fast, macd_slow, macd_signal, volume_threshold |
| **Grid Trading** | range | grid_spacing_pct, num_levels, auto_rebalance, base_quantity |
| **Donchian Breakout** | breakout | breakout_period, confirmation_bars, stop_pct |
| **RSI Divergence** | mean_reversion | rsi_period, divergence_lookback, rsi_threshold |
| **Moon Phase** | custom | phase_sensitivity, entry_offset, exit_after_n |
| **Kelly Sizing** | risk | kelly_fraction, max_position_pct |
| **Supertrend** | trend | supertrend_period, supertrend_multiplier |
| **VWAP Mean Reversion** | mean_reversion | vwap_period, deviation_threshold, session_start |

---

## 7. Strategy Library

### 7.1 CRUD + Versioning

```python
class StrategyRepository:
    """Full versioning support — every edit creates a new version"""

    async def update_strategy(self, strategy_id: UUID, params: dict, user: str) -> Strategy:
        # 1. Get current version
        current = await self.get(strategy_id)
        new_version = current.version + 1

        # 2. Create new version record
        version = StrategyVersion(
            id=uuid4(),
            strategy_id=strategy_id,
            version=new_version,
            parameters=params,
            created_at=now(),
            created_by=user,
            changelog=f"Updated params at {now()}",
        )

        # 3. Update strategy pointer to new version
        strategy = await self.db.update(
            Strategy,
            id=strategy_id,
            {"current_version_id": version.id, "version": new_version}
        )
        return strategy

    async def get_version_history(self, strategy_id: UUID) -> list[StrategyVersion]:
        return await self.db.query(
            StrategyVersion,
            where={"strategy_id": strategy_id},
            order_by="version DESC"
        )

    async def revert_to_version(self, strategy_id: UUID, version: int) -> Strategy:
        """Restore a previous version as a new version"""
        old = await self.get_version(strategy_id, version)
        return await self.update_strategy(
            strategy_id,
            params=old.parameters,
            user="system",
        )
```

### 7.2 Search & Filter

```python
class StrategySearch:
    """Full-text + structured search"""

    async def search(
        self,
        query: str | None,
        strategy_type: list[str] | None,
        pairs: list[str] | None,
        min_sharpe: float | None,
        max_drawdown: float | None,
        tags: list[str] | None,
        sort_by: str = "rating",
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResult:
        # PostgreSQL full-text search on name + description + tags
        # Structured filters on JSONB columns
        # denormalized backtest_summary for fast filtering
        pass
```

---

## 8. Backtest Engine

### 8.1 Event-Driven Backtest Loop

```python
class BacktestEngine:
    """
    Event-driven backtester.
    Same code path as live trading — guarantees identical behavior.
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_service: DataIngestionService,
        strategy_engine: StrategyEngine,
        risk_engine: RiskManager,
        oms: OrderManagementSystem,
        portfolio_tracker: PortfolioTracker,
    ):
        self.config = config
        self.data = data_service
        self.strategy = strategy_engine
        self.risk = risk_engine
        self.oms = oms
        self.portfolio = portfolio_tracker

    async def run(self, progress_callback: Callable | None = None):
        """Main backtest loop — processes candles sequentially"""
        candles = await self.data.fetch_and_validate(
            pair=self.config.pair,
            timeframe=self.config.timeframe,
            start=self.config.start_date,
            end=self.config.end_date,
        )

        state = self._load_state()  # Resume from saved state
        total = len(candles)
        last_progress = 0

        for i, candle in enumerate(candles):
            event = CandleEvent(
                event_id=uuid4(),
                timestamp=candle.timestamp,
                event_type=EventType.CANDLE,
                pair=self.config.pair,
                timeframe=self.config.timeframe,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )

            # Process through pipeline
            await self.strategy.on_candle(event)
            await self.oms.process_fills(event)  # Check for limit order fills
            await self.portfolio.update(event)

            # Persist state every N candles
            if i % 100 == 0:
                await self._save_state(state)

            # Progress reporting
            pct = int((i / total) * 100)
            if pct > last_progress:
                last_progress = pct
                if progress_callback:
                    await progress_callback(ProgressEvent(
                        pct=pct,
                        equity=self.portfolio.current_equity,
                        trades=len(self.portfolio.trades),
                        open_positions=len(self.portfolio.open_positions),
                    ))

        # Final metrics computation
        result = await self._compute_metrics(state)
        await self._save_result(result)
        return result

    async def _compute_metrics(self, state: BacktestState) -> BacktestResult:
        """Compute all performance metrics after run"""
        equity_curve = state.equity_curve
        trades = state.trades

        return BacktestResult(
            id=uuid4(),
            config_id=self.config.id,
            pair=self.config.pair,
            timeframe=self.config.timeframe,
            metrics=PerformanceMetrics(
                total_return=self._total_return(equity_curve),
                annualized_return=self._annualized_return(equity_curve),
                max_drawdown=self._max_drawdown(equity_curve),
                max_drawdown_pct=self._max_drawdown_pct(equity_curve),
                max_drawdown_duration_days=self._max_drawdown_duration(equity_curve),
                sharpe_ratio=self._sharpe_ratio(equity_curve),
                sortino_ratio=self._sortino_ratio(equity_curve),
                calmar_ratio=self._calmar_ratio(equity_curve),
                sterling_ratio=self._sterling_ratio(equity_curve),
                burke_ratio=self._burke_ratio(equity_curve),
                profit_factor=self._profit_factor(trades),
                win_rate=self._win_rate(trades),
                avg_win_pct=self._avg_win_pct(trades),
                avg_loss_pct=self._avg_loss_pct(trades),
                expectancy=self._expectancy(trades),
                total_trades=len(trades),
                winning_trades=len([t for t in trades if t.pnl > 0]),
                losing_trades=len([t for t in trades if t.pnl <= 0]),
                avg_trade_duration_hours=self._avg_trade_duration(trades),
                tail_ratio=self._tail_ratio(equity_curve),
                skewness=self._skewness(equity_curve),
                kurtosis=self._kurtosis(equity_curve),
                information_ratio=self._information_ratio(equity_curve),
            ),
            equity_curve=equity_curve,
            trades=[t.to_dict() for t in trades],
            warnings=state.warnings,
        )
```

### 8.2 Batch Backtesting with Throttling

```python
class BatchBacktestRunner:
    """Runs multiple backtests with rate limiting"""

    def __init__(self, redis: Redis, backtest_engine: BacktestEngine):
        self.redis = redis
        self.engine = backtest_engine
        self.rate_limiter = RateLimiter(
            max_calls=1100,  # Stay under Binance 1200/min limit
            window_seconds=60,
            redis=self.redis,
        )

    async def run_batch(
        self,
        configs: list[BacktestConfig],
        progress_callback: Callable | None = None,
    ):
        """Queue + execute with automatic throttling"""
        queue = asyncio.Queue()
        for config in configs:
            await queue.put(config)

        # Process up to 3 in parallel (avoid rate limits)
        semaphore = asyncio.Semaphore(3)

        async def worker():
            while True:
                config = await queue.get()
                if config is None:
                    break
                async with semaphore:
                    # Wait for rate limiter
                    await self.rate_limiter.acquire()
                    result = await self.engine.run(config, progress_callback)
                    await self._store_result(result)

        workers = [asyncio.create_task(worker()) for _ in range(3)]
        await asyncio.gather(*workers)


class RateLimiter:
    """Redis-based token bucket rate limiter"""

    def __init__(self, max_calls: int, window_seconds: int, redis: Redis):
        self.max_calls = max_calls
        self.window = window_seconds
        self.redis = redis

    async def acquire(self):
        key = f"rate_limit:binance:{int(time.time() // self.window)}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, self.window + 1)
        if current >= self.max_calls:
            sleep_time = self.window - (time.time() % self.window) + 1
            await asyncio.sleep(sleep_time)
```

### 8.3 Walk-Forward Testing

```python
class WalkForwardEngine:
    """
    Proper walk-forward with expanding or rolling windows.
    Computes overfit score = mean(test_metrics) / std(test_metrics).
    Higher ratio = more stable (less overfit).
    """

    async def run(
        self,
        config: BacktestConfig,
        train_pct: float = 0.6,
        test_pct: float = 0.2,
        step_pct: float = 0.1,
        mode: Literal["expanding", "rolling"] = "expanding",
    ) -> WalkForwardResult:
        """
        train_pct: % of data used for training
        test_pct: % of data used for testing
        step_pct: % to step forward each iteration
        """
        all_candles = await self.data.get_range(...)
        n = len(all_candles)

        train_size = int(n * train_pct)
        test_size = int(n * test_pct)
        step_size = int(n * step_pct)

        results = []

        if mode == "expanding":
            for i in range(train_size, n - test_size, step_size):
                train_end = i
                test_start = i
                test_end = min(i + test_size, n)

                train_candles = all_candles[:train_end]
                test_candles = all_candles[test_start:test_end]

                # Optimize on train
                best_params = await self._optimize_params(config, train_candles)

                # Test on train_params → test
                result = await self.backtest_engine.run(
                    config.with_params(best_params),
                    test_candles,
                )
                results.append({
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "params": best_params,
                    "test_metrics": result.metrics,
                    "train_metrics": result.metrics,  # from train run
                })

        elif mode == "rolling":
            for i in range(0, n - train_size, step_size):
                train_candles = all_candles[i:i + train_size]
                test_candles = all_candles[i + train_size:i + train_size + test_size]
                # ... same optimization + testing

        # Compute overfit score
        sharpe_train = [r["train_metrics"].sharpe_ratio for r in results]
        sharpe_test = [r["test_metrics"].sharpe_ratio for r in results]

        overfit_score = np.mean(sharpe_test) / (np.std(sharpe_test) + 1e-9)
        # overfit_score > 1.0 = good (test performance is stable)
        # overfit_score < 0.5 = likely overfit

        return WalkForwardResult(
            iterations=results,
            overfit_score=overfit_score,
            avg_train_sharpe=np.mean(sharpe_train),
            avg_test_sharpe=np.mean(sharpe_test),
            stability_rating=self._rate_stability(overfit_score),
        )
```

### 8.4 Monte Carlo Simulation

```python
class MonteCarloSimulation:
    """Shuffles trade returns to model distribution of outcomes"""

    async def run(
        self,
        trades: list[Trade],
        n_runs: int = 1000,
        initial_capital: float = 10000,
    ) -> MonteCarloResult:
        returns = [t.pnl_pct for t in trades]

        equity_curves = []
        for _ in range(n_runs):
            shuffled = np.random.choice(returns, size=len(returns), replace=True)
            curve = [initial_capital]
            for r in shuffled:
                curve.append(curve[-1] * (1 + r / 100))
            equity_curves.append(curve)

        final_equities = [c[-1] for c in equity_curves]
        max_drawdowns = [self._max_drawdown_from_curve(c) for c in equity_curves]

        return MonteCarloResult(
            run_count=n_runs,
            median_final_equity=np.median(final_equities),
            percentile_5_equity=np.percentile(final_equities, 5),
            percentile_95_equity=np.percentile(final_equities, 95),
            median_max_drawdown=np.median(max_drawdowns),
            probability_of_ruin=len([e for e in final_equities if e < initial_capital * 0.5]) / n_runs,
            best_case=np.max(final_equities),
            worst_case=np.min(final_equities),
        )
```

### 8.5 Advanced Slippage Model

```python
class SlippageModel:
    """
    Tiered slippage model:
    - Small orders: minimal slippage
    - Large orders relative to ADV: significant slippage
    - Volatility-adjusted: wider in volatile markets
    """

    def __init__(
        self,
        base_bps: float = 2.0,
        adv_pct_threshold: float = 0.01,  # order > 1% of ADV → extra slippage
        vol_multiplier: float = 1.5,
    ):
        self.base_bps = base_bps
        self.adv_pct_threshold = adv_pct_threshold
        self.vol_multiplier = vol_multiplier

    def compute(
        self,
        order_quantity: float,
        current_price: float,
        adv: float,  # Average Daily Volume
        current_volatility: float,
        order_side: str,
    ) -> SlippageResult:
        # 1. Base slippage
        slippage_bps = self.base_bps

        # 2. Liquidity adjustment — large order relative to ADV
        order_adv_pct = (order_quantity * current_price) / adv
        if order_adv_pct > self.adv_pct_threshold:
            excess = order_adv_pct - self.adv_pct_threshold
            slippage_bps += excess * 100  # penalty proportional to order size

        # 3. Volatility adjustment
        avg_vol = 0.01  # 1% average daily vol
        if current_volatility > avg_vol * 2:
            slippage_bps *= self.vol_multiplier

        # 4. Side asymmetry — sells hit the ask, buys hit the bid
        if order_side == "sell":
            slippage_bps *= 1.1
        else:
            slippage_bps *= 1.05

        return SlippageResult(
            slippage_bps=round(slippage_bps, 2),
            estimated_slippage_cost=order_quantity * current_price * (slippage_bps / 10000),
        )
```

---

## 9. Risk Management Engine

Risk management is a **separate service** that intercepts every order before it reaches the exchange. It is the most critical component of the system.

```python
@dataclass
class RiskLimits:
    max_portfolio_drawdown_pct: float = 20.0       # Pause all trading if portfolio DD exceeds this
    max_position_drawdown_pct: float = 5.0         # Close individual position if DD exceeds this
    max_correlation: float = 0.7                   # Max correlation between strategy positions
    max_leverage: float = 3.0                      # Portfolio-level max leverage
    max_open_positions: int = 10                  # Max total open positions
    max_position_size_pct: float = 20.0            # Max % of equity in single position
    daily_loss_limit_pct: float = 5.0              # Stop trading for the day if exceeded
    max_pairs_per_strategy: int = 5               # Max pairs per single strategy
    circuit_breaker_trades: int = 5               # Auto-pause after N consecutive losses

@dataclass
class RiskCheckResult:
    approved: bool
    reason: str | None
    adjustments: dict | None  # e.g. reduce size by 50% if near limit

class RiskManager:
    """Pre-trade risk checks — all orders must pass through this"""

    def __init__(
        self,
        limits: RiskLimits,
        portfolio_tracker: PortfolioTracker,
        regime_analyzer: MarketRegimeAnalyzer,
    ):
        self.limits = limits
        self.portfolio = portfolio_tracker
        self.regime = regime_analyzer
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.is_paused = False

    async def check_signal(self, signal: SignalEvent) -> RiskCheckResult:
        if self.is_paused:
            return RiskCheckResult(False, "Circuit breaker active — system paused")

        # 1. Position size check
        position_value = signal.strength * self.portfolio.current_equity
        max_position_value = self.portfolio.current_equity * (self.limits.max_position_size_pct / 100)
        if position_value > max_position_value:
            return RiskCheckResult(
                approved=True,
                adjustments={"quantity_scaled": max_position_value / signal.entry_price}
            )

        # 2. Open positions limit
        if len(self.portfolio.open_positions) >= self.limits.max_open_positions:
            return RiskCheckResult(False, "Max open positions reached")

        # 3. Daily loss limit
        if self.daily_pnl < -(self.portfolio.initial_equity * (self.limits.daily_loss_limit_pct / 100)):
            self.is_paused = True
            return RiskCheckResult(False, f"Daily loss limit ({self.limits.daily_loss_limit_pct}%) exceeded")

        # 4. Correlation check
        existing_pairs = [p.pair for p in self.portfolio.open_positions]
        if signal.pair in existing_pairs:
            return RiskCheckResult(False, f"Position already open for {signal.pair}")

        # 5. Portfolio drawdown check
        current_dd = self.portfolio.current_drawdown_pct
        if current_dd > self.limits.max_portfolio_drawdown_pct:
            self.is_paused = True
            return RiskCheckResult(False, f"Portfolio drawdown {current_dd:.1f}% exceeds limit")

        # 6. Consecutive loss circuit breaker
        if self.consecutive_losses >= self.limits.circuit_breaker_trades:
            return RiskCheckResult(False, f"Circuit breaker: {self.consecutive_losses} consecutive losses")

        # 7. Leverage check
        total_exposure = self.portfolio.total_exposure
        if total_exposure / self.portfolio.current_equity > self.limits.max_leverage:
            return RiskCheckResult(False, "Max leverage exceeded")

        return RiskCheckResult(approved=True)

    async def check_order(self, order: Order) -> RiskCheckResult:
        """Called when order is about to be submitted to exchange"""
        # Same checks as check_signal, plus:
        # - Price sanity check (order price too far from market)
        # - Quantity precision check
        return RiskCheckResult(approved=True)

    def on_trade_result(self, trade: Trade):
        """Called after trade closes — update risk state"""
        if trade.pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self.daily_pnl += trade.pnl

    def reset_daily(self):
        """Called at start of new trading day"""
        self.daily_pnl = 0.0
        self.is_paused = False
        self.consecutive_losses = 0

    async def get_risk_report(self) -> RiskReport:
        return RiskReport(
            portfolio_drawdown=self.portfolio.current_drawdown_pct,
            total_exposure=self.portfolio.total_exposure,
            leverage=self.portfolio.total_exposure / self.portfolio.current_equity,
            open_positions=len(self.portfolio.open_positions),
            daily_pnl=self.daily_pnl,
            is_paused=self.is_paused,
            consecutive_losses=self.consecutive_losses,
        )
```

### Pre-Trade vs Post-Trade Risk

| Check | Timing | Example |
|---|---|---|
| Pre-trade | Before order submission | Position size, max DD, leverage, correlation |
| Post-trade | After fill | MAE/MFE analysis, stop loss breach |
| Continuous | Every tick | Real-time P&L, drawdown monitoring |

---

## 10. Order Management System (OMS)

```python
class OrderManagementSystem:
    """
    Tracks all orders across their lifecycle.
    Maintains authoritative state for all positions.
    """

    def __init__(self, db: AsyncSession, event_bus: EventBus):
        self.db = db
        self.event_bus = event_bus

    async def submit_market_order(
        self,
        signal: SignalEvent,
        quantity: float,
    ) -> Order:
        order = Order(
            id=uuid4(),
            signal_id=signal.signal_id,
            strategy_id=signal.strategy_id,
            pair=signal.pair,
            side="buy" if signal.direction == "long" else "sell",
            order_type="market",
            quantity=quantity,
            status="pending",
            created_at=now(),
        )
        await self.db.save(order)
        await self.event_bus.publish(OrderSubmittedEvent(order=order))
        return order

    async def submit_limit_order(
        self,
        signal: SignalEvent,
        quantity: float,
        price: float,
    ) -> Order:
        order = Order(
            id=uuid4(),
            signal_id=signal.signal_id,
            strategy_id=signal.strategy_id,
            pair=signal.pair,
            side="buy" if signal.direction == "long" else "sell",
            order_type="limit",
            price=price,
            quantity=quantity,
            status="pending",
            created_at=now(),
        )
        await self.db.save(order)
        return order

    async def on_fill(
        self,
        exchange_order_id: str,
        filled_quantity: float,
        avg_fill_price: float,
        commission: float,
        slippage_bps: float,
    ):
        """Called when exchange reports a fill"""
        order = await self.db.query(Order, where={"exchange_order_id": exchange_order_id})
        order.filled_quantity = filled_quantity
        order.avg_fill_price = avg_fill_price
        order.commission = commission
        order.slippage_bps = slippage_bps
        order.status = "filled" if filled_quantity >= order.quantity else "partial"
        order.updated_at = now()
        await self.db.save(order)

        await self.event_bus.publish(OrderFilledEvent(order=order))
        await self._update_position_from_fill(order)

    async def _update_position_from_fill(self, order: Order):
        """Create or update position from a filled order"""
        if order.side == "buy":
            # Open or add to long
            existing = await self.db.query(
                Position,
                where={"pair": order.pair, "strategy_id": order.strategy_id, "side": "long"}
            )
            if existing:
                new_qty = existing.quantity + order.filled_quantity
                new_entry = (
                    existing.entry_price * existing.quantity +
                    order.avg_fill_price * order.filled_quantity
                ) / new_qty
                existing.quantity = new_qty
                existing.entry_price = new_entry
                await self.db.save(existing)
            else:
                pos = Position(
                    id=uuid4(),
                    strategy_id=order.strategy_id,
                    pair=order.pair,
                    side="long",
                    quantity=order.filled_quantity,
                    entry_price=order.avg_fill_price,
                    current_price=order.avg_fill_price,
                    unrealized_pnl=0,
                    opened_at=now(),
                )
                await self.db.save(pos)
                await self.event_bus.publish(PositionOpenedEvent(position=pos))
        else:
            # Close or add to short (similar logic)
            pass

    async def cancel_order(self, order_id: UUID) -> bool:
        order = await self.db.get(Order, order_id)
        if order.status in ("filled", "cancelled"):
            return False
        order.status = "cancelled"
        order.updated_at = now()
        await self.db.save(order)
        await self.event_bus.publish(OrderCancelledEvent(order=order))
        return True
```

### Order State Machine

```
pending → submitted → partial → filled
                    ↘ cancelled
                    ↘ failed
```

---

## 11. Execution Layer

```python
class ExchangeAdapter(ABC):
    """Base class for all exchange integrations"""

    @abstractmethod
    async def fetch_ohlcv(self, pair: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]
    @abstractmethod
    async def submit_order(self, order: Order) -> str  # returns exchange order ID
    @abstractmethod
    async def cancel_order(self, exchange_order_id: str) -> bool
    @abstractmethod
    async def get_order_status(self, exchange_order_id: str) -> OrderStatus
    @abstractmethod
    async def get_positions(self) -> list[Position]


class BinanceAdapter(ExchangeAdapter):
    """Binance exchange integration via CCXT"""

    def __init__(self, api_key: str | None, api_secret: str | None, testnet: bool = True):
        self.ccxt = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if testnet:
            self.ccxt.set_sandbox_mode(True)

    async def fetch_ohlcv(self, pair: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        # Use CCXT's fetch_ohlcv with proper rate limiting
        # Parse into Candle dataclass
        pass

    async def submit_order(self, order: Order) -> str:
        return await self.ccxt.create_order(
            symbol=pair_to_exchange_format(order.pair),
            type=order.order_type,
            side=order.side,
            amount=order.quantity,
            price=order.price,
        )["id"]


class PortfolioTracker:
    """Tracks portfolio state in real-time"""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.cash = initial_capital
        self.open_positions: list[Position] = []
        self.closed_trades: list[Trade] = []

    async def update_from_candle(self, candle: Candle):
        """Update current prices and P&L for all positions"""
        for pos in self.open_positions:
            if pos.pair == candle.pair:
                pos.current_price = candle.close
                pos.unrealized_pnl = (candle.close - pos.entry_price) * pos.quantity
                pos.unrealized_pnl_pct = (
                    (candle.close - pos.entry_price) / pos.entry_price * 100
                )
        self._update_equity()

    def _update_equity(self):
        self.current_equity = self.cash + sum(
            pos.unrealized_pnl for pos in self.open_positions
        )

    @property
    def current_drawdown_pct(self) -> float:
        peak = max(e.equity for e in self.equity_curve)
        return (peak - self.current_equity) / peak * 100

    @property
    def total_exposure(self) -> float:
        return sum(
            pos.quantity * pos.current_price
            for pos in self.open_positions
        )
```

---

## 12. Frontend Pages

### Page Structure

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard Home | Portfolio overview, recent backtests, market ticker |
| `/strategies` | Strategy Library | Grid/list browse, search, filter |
| `/strategies/[id]` | Strategy Detail | Full analysis with equity curve + trade log |
| `/strategies/new` | Strategy Editor | Create / describe new strategy |
| `/backtest` | Backtest Runner | Configure + launch backtests |
| `/backtest/[id]` | Backtest Result | Deep dive into a single result |
| `/automate` | Automation | Schedule + manage recurring jobs |
| `/compare` | Comparison | Side-by-side strategy comparison |
| `/export` | Export | TradingView export, webhooks, signal CSV |
| `/portfolio` | Portfolio | Multi-strategy portfolio backtest + live positions |
| `/risk` | Risk Monitor | Real-time risk dashboard |
| `/settings` | Settings | API keys, notifications, display |

### Key Component Details

#### `/strategies` — Strategy Library

**Layout:**
- Full-width grid (default) or sortable table (toggle)
- Left filter panel (collapsible)
- Search bar with fuzzy matching

**Filters:**
- Strategy type (checkboxes): Momentum, Mean Reversion, Grid, Breakout, Arbitrage, Moon Phase, Custom
- Asset class: Crypto, Forex, Stocks, Commodities
- Pairs: Multi-select searchable dropdown (top 20 pairs)
- Timeframes: Multi-select (1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W)
- Performance: Max drawdown slider, Min Sharpe, Min Profit Factor
- Rating: 1–5 stars
- Tags: Multi-select from existing tags
- Created: within 7d, 30d, 90d, all time

**Sort options:** Rating ↓, Sharpe ↓, Return ↓, Drawdown ↑, Newest, Most Backtested

**Strategy Card:**
- Name + author avatar
- Strategy type badge
- Mini equity curve sparkline (inline SVG, 100×30px)
- Key metrics row: Return %, Max DD, Sharpe, Win Rate, Trades
- Tags (max 3 visible)
- Quick actions: Backtest, Compare, Fork, Save

#### `/strategies/[id]` — Strategy Detail

**Layout (full width):**
```
[Name + Author + Share Button]
[Tags + Rating + Version indicator]
[Strategy Type Badge]

[Return %] [Sharpe] [Win Rate] [PF] [Max DD] [Trades]
 ← 3-column stat cards

[Equity Curve — full width TradingView Lightweight Charts]
  Overlaid: drawdown curve, benchmark (if selected)

[Parameter Tree — JSON viewer with copy]
[Pine Script — syntax highlighted, copy button]
[Trade Log — sortable table]
  Columns: #, Entry Date, Exit Date, Side, Entry, Exit, P&L, P&L%, MAE, MFE, Duration

[Community Backtests — table with pair/timeframe/date/result]
[Similar Strategies — horizontal scroll]
```

#### `/backtest` — Backtest Runner

**Multi-step wizard:**

**Step 1 — Strategy Selection**
- Search existing strategies
- Paste Pine Script (parses params automatically)
- Describe in plain English → AI generates params
- "Load from URL" → parse from TradingView public indicator

**Step 2 — Universe**
- Pairs: multi-select (shows 24h volume as proxy for liquidity)
- Timeframes: multi-select
- Date range: presets or custom calendar
- Exchange: Binance (default), Coinbase, Kraken, Bybit

**Step 3 — Capital & Risk**
- Initial capital: $1,000 – $10,000,000
- Leverage: 1x–100x slider
- Position sizing: Fixed $ / % of equity / Kelly criterion / ATR-based
- Max positions: 1–20
- Direction: Long only, Short only, Both

**Step 4 — Costs**
- Maker fee %, Taker fee %
- Slippage model: None, Fixed BPS, Dynamic (size + vol)
- Funding rate (for futures): included

**Step 5 — Advanced**
- Walk-forward: Off / Expanding / Rolling (with train/test/skip settings)
- Monte Carlo: Off / 100 / 500 / 1000 runs
- Parameter ranges: grid search over defined ranges
- Multiple strategies: add more strategies to same portfolio

**Execution:**
- "Run Single" → one pair/timeframe
- "Run Batch" → all combinations
- "Schedule" → opens automation modal

**Results panel:** Replaces form on completion, shows equity curve + full metrics grid + trade log + export options

#### `/automate` — Automation

**Job List:**
| Name | Strategy | Schedule | Status | Last Run | Next Run | Actions |
|---|---|---|---|---|---|---|
| Daily ETH sweep | MA Crossover | 0 8 * * * | 🟢 Active | 2025-05-19 08:00 | 2025-05-20 08:00 | ⏸️ ▶️ 🗑️ |

**Job Editor:**
- Name
- Strategy selection
- Pairs + timeframes
- Cron builder: visual selector OR raw expression
- Presets: Every 15min, Hourly, Daily 8am, Weekly Sunday
- Notifications: Telegram / Discord webhook on complete / on failure
- Stop conditions: after N failures, after N runs, after X days

**Loop Templates (JSON configs):**
- Moon Phase Strategist
- Trend Following (3 SMA + ADX)
- Mean Reversion (BB + RSI)
- Momentum (MACD + Volume)
- Overfit Detector (N-seed randomization)
- Parameter Optimizer (grid search)

#### `/portfolio` — Multi-Strategy Portfolio

**Configuration:**
- Select 1–10 strategies to combine
- Set allocation weights (equal, risk-parity, custom)
- Set correlation limits (max correlation between strategy returns)
- Configure cross-strategy risk limits

**Backtest:**
- Runs all strategies simultaneously
- Aggregates positions (handles overlap)
- Shows individual strategy contribution
- Shows portfolio-level metrics

**Live view:**
- Real-time P&L per strategy
- Contribution to portfolio return
- Correlation heatmap

#### `/risk` — Risk Monitor

**Real-time dashboard:**
- Portfolio exposure by pair
- Portfolio exposure by side (long/short)
- Max drawdown current vs limit (progress bar)
- Daily P&L vs limit
- Open positions table with real-time P&L
- Risk score (composite metric 0–100)
- Circuit breaker status
- Recent risk events log

---

## 13. API Server (FastAPI)

### Endpoints

```
# Auth
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

# Strategies
GET    /api/strategies                     List (paginated, filtered)
POST   /api/strategies                     Create
GET    /api/strategies/:id                 Get detail
PUT    /api/strategies/:id                 Update (creates new version)
DELETE /api/strategies/:id                 Delete
POST   /api/strategies/:id/fork            Fork
GET    /api/strategies/:id/versions        Version history
POST   /api/strategies/:id/revert/:version Revert to version
GET    /api/strategies/:id/backtests       List backtests for strategy

# Backtest
POST   /api/backtest                       Run single backtest (async → job_id)
GET    /api/backtest/:id                   Get result
GET    /api/backtest/:id/equity            Equity curve points
GET    /api/backtest/:id/trades            Trade log
DELETE /api/backtest/:id                   Delete result
POST   /api/backtest/batch                 Run batch (returns job_id + count)
GET    /api/backtest/batch/:job_id         Get batch progress
GET    /api/backtest/batch/:job_id/results Get all batch results

# Portfolio Backtest
POST   /api/portfolio/backtest             Run multi-strategy portfolio backtest

# Walk-Forward
POST   /api/backtest/walk-forward          Run walk-forward analysis
GET    /api/backtest/walk-forward/:id      GetWF result + overfit score

# Monte Carlo
POST   /api/backtest/monte-carlo          Run Monte Carlo simulation
GET    /api/backtest/monte-carlo/:id       Get MC result

# Jobs (Automation)
GET    /api/jobs                           List jobs
POST   /api/jobs                           Create job
GET    /api/jobs/:id                       Get job detail + history
PUT    /api/jobs/:id                       Update (pause/resume/edit)
DELETE /api/jobs/:id                       Delete
POST   /api/jobs/:id/run                   Trigger immediate run
GET    /api/jobs/:id/history               Execution history

# Pairs & Data
GET    /api/pairs                          List supported pairs with metadata
GET    /api/timeframes                     List supported timeframes
GET    /api/candles?pair=ETH/USDT&timeframe=1h&start=...&end=...   Get OHLCV
GET    /api/candles/meta?pair=ETH/USDT     Get metadata (ADV, price range)
POST   /api/data/validate                  Validate candle data quality

# Risk
GET    /api/risk/report                    Get current risk report
GET    /api/risk/limits                    Get current risk limits

# AI Strategy Generation
POST   /api/ai/generate                    Generate strategy from description
POST   /api/ai/optimize                    Optimize strategy parameters
POST   /api/ai/describe                    Describe strategy in plain English
POST   /api/ai/suggest                     Suggest strategy improvements

# Export
GET    /api/export/pine/:strategy_id       Download Pine Script
GET    /api/export/signals/:backtest_id    Download trade signals CSV
POST   /api/export/webhook                 Configure webhook for signals

# Health
GET    /api/health                         Health check
GET    /api/health/candles                 Check data freshness
```

### WebSocket Events

| Event | Direction | Description |
|---|---|---|
| `backtest.started` | S→C | { job_id, strategy_name, pair, timeframe } |
| `backtest.progress` | S→C | { job_id, pct, equity, trades, open_positions } |
| `backtest.completed` | S→C | { job_id, result_id, summary_metrics } |
| `backtest.failed` | S→C | { job_id, error, stage } |
| `job.triggered` | S→C | { job_id, schedule } |
| `job.completed` | S→C | { job_id, result_count } |
| `market.ticker` | S→C | { pair, price, change_24h, volume } |
| `risk.alert` | S→C | { alert_type, message, severity } |
| `position.opened` | S→C | { position_id, pair, side, quantity, entry_price } |
| `position.closed` | S→C | { position_id, pair, pnl } |

---

## 14. Real-time Features

```python
class WebSocketManager:
    """Manages WebSocket connections per user"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    async def broadcast(self, event: str, data: dict, room: str | None = None):
        """Broadcast to specific room or all"""
        message = json.dumps({"event": event, "data": data})
        if room:
            for ws in self._connections.get(room, []):
                await ws.send_text(message)
        else:
            for user_id, ws_list in self._connections.items():
                for ws in ws_list:
                    await ws.send_text(message)

    async def notify_backtest_progress(
        self,
        job_id: str,
        pct: int,
        equity: float,
        trades: int,
    ):
        await self.broadcast("backtest.progress", {
            "job_id": job_id,
            "pct": pct,
            "equity": round(equity, 2),
            "trades": trades,
        })
```

### Backtest State Persistence

```python
class BacktestStatePersistence:
    """
    Saves backtest state to PostgreSQL every N candles.
    Ensures backtest survives server restarts.
    """

    async def save_state(self, job_id: UUID, state: BacktestState):
        await self.db.execute(
            """
            INSERT INTO backtest_state (job_id, state_json, saved_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (job_id) DO UPDATE SET state_json = $2, saved_at = NOW()
            """,
            job_id,
            json.dumps(state.to_dict()),
        )

    async def load_state(self, job_id: UUID) -> BacktestState | None:
        row = await self.db.query_one(
            "SELECT state_json FROM backtest_state WHERE job_id = $1",
            job_id,
        )
        if row:
            return BacktestState.from_dict(json.loads(row["state_json"]))
        return None
```

---

## 15. AI Strategy Generation

```python
class AIStrategyGenerator:
    """
    Uses Claude to generate and optimize strategies.
    Prompt: "Create a mean reversion strategy on ETH that triggers
    on Bollinger Band + RSI with proper risk management."
    """

    def __init__(self, client: Anthropic):
        self.client = client

    async def generate(
        self,
        description: str,
        existing_strategies: list[str] | None = None,
    ) -> Strategy:
        prompt = f"""
        Create a trading strategy based on this description:
        {description}

        Available strategy types: momentum, mean_reversion, grid, breakout, arbitrage, moon_phase
        Available pairs: BTC/USDT, ETH/USDT, SOL/USDT, AVAX/USDT, etc.
        Available timeframes: 1m, 5m, 15m, 30m, 1H, 4H, 1D

        Return a JSON object with:
        - name: strategy name
        - strategy_type: one of the available types
        - parameters: dict of parameter_name -> {value, min, max, description}
        - description: plain English description of the strategy logic
        - pine_script_template: Pine Script v5 template with {{param}} placeholders

        Constraints:
        - All parameters must have min/max bounds for optimization
        - Must include stop_loss and take_profit parameters
        - Must include position sizing parameters
        """

        response = await self.client.messages.create(
            model="claude-sonnet-4",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return Strategy.from_ai_response(response.content)

    async def optimize(
        self,
        strategy_id: UUID,
        metric: str = "sharpe_ratio",
        n_iterations: int = 100,
    ) -> OptimizationResult:
        """
        Use Bayesian optimization (or grid search) to find
        best parameter combinations for a strategy.
        """
        # Use optuna or custom Bayesian optimizer
        # Minimize overfit risk by using walk-forward validation
        pass

    async def describe(
        self,
        strategy_params: dict,
        strategy_type: str,
    ) -> str:
        """Convert strategy parameters into plain English"""
        prompt = f"""
        Explain this {strategy_type} strategy in plain English
        that a non-technical trader would understand.
        Include: entry conditions, exit conditions, risk management approach.
        Parameters: {strategy_params}
        """
        response = await self.client.messages.create(...)
        return response.content
```

---

## 16. File Structure

```
~/.hermes/profiles/coder/workspace/Trading/
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── strategies.py
│   │   │   ├── backtest.py
│   │   │   ├── portfolio.py
│   │   │   ├── jobs.py
│   │   │   ├── pairs.py
│   │   │   ├── risk.py
│   │   │   ├── ai.py
│   │   │   ├── export.py
│   │   │   └── auth.py
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── redis.py
│   ├── domain/
│   │   ├── models/
│   │   │   ├── strategy.py
│   │   │   ├── order.py
│   │   │   ├── position.py
│   │   │   ├── portfolio.py
│   │   │   ├── backtest_result.py
│   │   │   └── risk.py
│   │   └── events.py              # All event type definitions
│   ├── services/
│   │   ├── strategy_registry.py
│   │   ├── strategy_engine.py      # Signal generation
│   │   ├── backtest_engine.py
│   │   ├── batch_runner.py
│   │   ├── walk_forward_engine.py
│   │   ├── monte_carlo.py
│   │   ├── scheduler.py
│   │   ├── ai_generator.py
│   │   ├── tradingview_export.py
│   │   ├── risk_manager.py
│   │   ├── oms.py                  # Order Management System
│   │   ├── portfolio_tracker.py
│   │   ├── event_bus.py
│   │   ├── market_regime_analyzer.py
│   │   ├── slippage_model.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── sma.py
│   │   │   ├── ema.py
│   │   │   ├── rsi.py
│   │   │   ├── macd.py
│   │   │   ├── bollinger.py
│   │   │   ├── adx.py
│   │   │   ├── atr.py
│   │   │   └── supertrend.py
│   │   ├── strategies/
│   │   │   ├── base.py
│   │   │   ├── ma_crossover.py
│   │   │   ├── bollinger_rsi.py
│   │   │   ├── macd_momentum.py
│   │   │   ├── grid_trading.py
│   │   │   ├── donchian_breakout.py
│   │   │   ├── moon_phase.py
│   │   │   ├── supertrend.py
│   │   │   └── __init__.py
│   │   └── execution/
│   │       ├── base.py             # ExchangeAdapter abstract
│   │       ├── binance.py          # Binance via CCXT
│   │       └── coinbase.py
│   ├── schemas/
│   │   ├── strategy.py
│   │   ├── backtest.py
│   │   ├── portfolio.py
│   │   ├── job.py
│   │   └── risk.py
│   └── migrations/                  # Alembic
│       ├── versions/
│       └── env.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Home dashboard
│   │   │   ├── strategies/
│   │   │   │   ├── page.tsx        # Strategy library
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx   # Strategy editor
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx   # Strategy detail
│   │   │   ├── backtest/
│   │   │   │   ├── page.tsx        # Backtest runner
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx   # Backtest result
│   │   │   ├── portfolio/
│   │   │   │   └── page.tsx
│   │   │   ├── automate/
│   │   │   │   └── page.tsx
│   │   │   ├── compare/
│   │   │   │   └── page.tsx
│   │   │   ├── risk/
│   │   │   │   └── page.tsx
│   │   │   ├── export/
│   │   │   │   └── page.tsx
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Topbar.tsx
│   │   │   │   └── MarketTicker.tsx
│   │   │   ├── strategies/
│   │   │   │   ├── StrategyCard.tsx
│   │   │   │   ├── StrategyGrid.tsx
│   │   │   │   ├── StrategyFilters.tsx
│   │   │   │   ├── StrategyTable.tsx
│   │   │   │   ├── StrategyEditor.tsx
│   │   │   │   └── VersionHistory.tsx
│   │   │   ├── backtest/
│   │   │   │   ├── BacktestWizard.tsx
│   │   │   │   ├── BacktestProgress.tsx
│   │   │   │   ├── BacktestResults.tsx
│   │   │   │   ├── EquityCurveChart.tsx
│   │   │   │   ├── TradeLog.tsx
│   │   │   │   ├── MetricsGrid.tsx
│   │   │   │   ├── WalkForwardReport.tsx
│   │   │   │   └── MonteCarloChart.tsx
│   │   │   ├── portfolio/
│   │   │   │   ├── PortfolioConfig.tsx
│   │   │   │   ├── MultiStrategyChart.tsx
│   │   │   │   └── ContributionChart.tsx
│   │   │   ├── automate/
│   │   │   │   ├── JobList.tsx
│   │   │   │   ├── JobScheduler.tsx
│   │   │   │   └── CronBuilder.tsx
│   │   │   ├── risk/
│   │   │   │   ├── RiskDashboard.tsx
│   │   │   │   ├── ExposureChart.tsx
│   │   │   │   └── CircuitBreaker.tsx
│   │   │   └── ui/
│   │   │       ├── Button.tsx, Modal.tsx, Table.tsx,
│   │   │       ├── Badge.tsx, Chart.tsx, Slider.tsx,
│   │   │       ├── Select.tsx, Input.tsx, Tabs.tsx
│   │   ├── hooks/
│   │   │   ├── useStrategies.ts
│   │   │   ├── useBacktest.ts
│   │   │   ├── usePortfolio.ts
│   │   │   ├── useJobs.ts
│   │   │   ├── useRisk.ts
│   │   │   └── useWebSocket.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   └── store/
│   │       ├── strategyStore.ts    # Zustand
│   │       ├── backtestStore.ts
│   │       └── riskStore.ts
│   └── public/
│       └── favicon.ico
├── scripts/
│   ├── seed_strategies.py          # 100+ seed strategies
│   ├── backfill_candles.py          # Historical data downloader
│   ├── run_backtest.py             # CLI backtest runner
│   └── generate_pine_templates.py  # Generate Pine Script templates
├── tests/
│   ├── unit/
│   │   ├── test_indicators.py
│   │   ├── test_strategies.py
│   │   ├── test_risk_manager.py
│   │   ├── test_slippage_model.py
│   │   ├── test_event_pipeline.py
│   │   └── test_oms.py
│   └── integration/
│       ├── test_api_strategies.py
│       ├── test_api_backtest.py
│       └── test_backtest_engine.py
├── requirements.txt
├── package.json
└── README.md
```

---

## 17. Tech Stack

### Backend
| Component | Tool |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 + asyncpg |
| Migration | Alembic |
| Task Scheduling | APScheduler |
| Caching + Queue | Redis (aioredis) |
| Auth | JWT (python-jose) |
| Validation | Pydantic v2 |
| HTTP Client | httpx |
| Exchange Integration | CCXT |
| Backtest Engine | Custom event-driven (no external lib) |
| Indicators | pandas-ta + custom |
| Optimization | optuna (Bayesian optimization) |
| WebSocket | FastAPI WebSocket |
| Serialization | orjson |

### Frontend
| Component | Tool |
|---|---|
| Framework | Next.js 14 (App Router) |
| UI Components | Radix UI (shadcn/ui) |
| Styling | Tailwind CSS |
| State Management | Zustand |
| Data Fetching | TanStack Query |
| Charts | TradingView Lightweight Charts |
| Tables | TanStack Table |
| Forms | React Hook Form + Zod |
| Icons | Lucide React |
| WebSocket | Native WebSocket API |

### Infrastructure
| Component | Tool |
|---|---|
| Database | PostgreSQL 15 (`apt install`) |
| Cache/Queue | Redis 7 (`apt install`) |
| Object Storage | Local filesystem |

---

## 18. Implementation Phases

### Phase 1: Foundation (Week 1–2)
- [ ] Install PostgreSQL 15 + Redis 7 via apt
- [ ] Create database + user
- [ ] FastAPI skeleton with all route stubs
- [ ] Database models + Alembic migrations (all tables from Section 5)
- [ ] JWT auth (register, login, me)
- [ ] Domain models: Strategy, Order, Position, Portfolio
- [ ] Event bus (in-memory + Redis pub/sub)
- [ ] Next.js scaffold with layout (sidebar, topbar, market ticker)
- [ ] Strategy list page with mock data

### Phase 2: Data + Strategy Engine (Week 2–3)
- [ ] CCXT integration for Binance
- [ ] Data ingestion service with validation
- [ ] Indicator library (SMA, EMA, RSI, MACD, Bollinger, ADX, ATR, Supertrend)
- [ ] BaseStrategy class + all 10 built-in strategies
- [ ] Market Regime Analyzer
- [ ] Strategy engine on candle event
- [ ] Candle store (PostgreSQL time-series)
- [ ] First backtest: single strategy, single pair, single timeframe

### Phase 3: Backtest Engine (Week 3–4)
- [ ] Full event-driven backtest loop
- [ ] OMS (order state machine, fill tracking)
- [ ] Portfolio tracker (real-time equity, drawdown)
- [ ] Risk manager (pre-trade checks, circuit breakers)
- [ ] Slippage model (tiered, size + vol based)
- [ ] WebSocket progress streaming
- [ ] Backend backtest API endpoints
- [ ] Frontend backtest wizard (Steps 1–5)
- [ ] Results display (equity curve, metrics grid, trade log)
- [ ] Strategy versioning (save/restore)

### Phase 4: Advanced Backtesting (Week 4–5)
- [ ] Batch backtest runner with Redis rate limiter
- [ ] Walk-forward engine (expanding + rolling windows)
- [ ] Monte Carlo simulation
- [ ] Multi-strategy portfolio backtest
- [ ] All metrics computation (including Sterling, Burke, Calmar, MAE/MFE)
- [ ] Backtest state persistence (save/restore mid-run)
- [ ] Frontend: walk-forward report, Monte Carlo charts
- [ ] Frontend: portfolio page with multi-strategy support

### Phase 5: Automation + AI (Week 5–6)
- [ ] APScheduler integration
- [ ] Job CRUD API
- [ ] Scheduler UI (cron builder, presets)
- [ ] Loop templates (Moon Phase, Trend Following, etc.)
- [ ] Claude API integration (AI strategy generator)
- [ ] AI parameter optimizer (Bayesian)
- [ ] Strategy describe endpoint (params → plain English)
- [ ] Telegram/Discord notification hooks
- [ ] Frontend: automation page + job history

### Phase 6: Export + Polish (Week 6–7)
- [ ] Pine Script export (all strategy types)
- [ ] Trade signal CSV export
- [ ] Webhook integration
- [ ] Strategy comparison page (up to 5 strategies)
- [ ] Risk monitor page
- [ ] TradingView direct export (copy to clipboard)
- [ ] Performance optimization (query indexes, Redis caching)
- [ ] Data quality dashboard (detect gaps, anomalies)
- [ ] Documentation + README

---

## 19. Environment Setup

```bash
# Install system dependencies
sudo apt update
sudo apt install -y postgresql postgresql-contrib redis-server

# Start services
sudo systemctl enable postgresql redis-server
sudo systemctl start postgresql
sudo systemctl start redis-server

# Create database
sudo -u postgres createdb trading_db
sudo -u postgres createuser trading_user WITH PASSWORD 'your_secure_password'
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trading_db TO trading_user"
sudo -u postgres psql -d trading_db -c "GRANT ALL ON SCHEMA public TO trading_user"

# Create database tables (run migrations)
# cd backend && alembic upgrade head

# Clone/checkout project
# cd ~/.hermes/profiles/coder/workspace/Trading

# Backend env
cp .env.example .env
# Edit .env with:
#   DATABASE_URL=postgresql+asyncpg://trading_user:your_secure_password@localhost:5432/trading_db
#   REDIS_URL=redis://localhost:6379/0
#   JWT_SECRET=<generate-32-char-random-string>
#   CLAUDE_API_KEY=sk-ant-...

# Python deps
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend deps
cd frontend
npm install

# Run
# Terminal 1: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# Terminal 2: npm run dev (in frontend/)
```

---

## 20. Metrics Reference

All computed after backtest completion:

| Metric | Formula | Description |
|---|---|---|
| **Total Return** | `(final_equity - initial) / initial × 100` | Gross return |
| **Annualized Return** | `(final/initial)^(365/days) - 1` | Time-weighted return |
| **Max Drawdown %** | `max(peak - trough) / peak × 100` | Worst peak-to-trough |
| **Max Drawdown Duration** | Days between peak and new high | Longest drawdown period |
| **Sharpe Ratio** | `mean(ret) / std(ret) × sqrt(252)` | Risk-adjusted return |
| **Sortino Ratio** | `mean(ret) / std(downside_ret) × sqrt(252)` | Downside risk-adjusted |
| **Calmar Ratio** | `annualized_return / max_drawdown` | Return per unit max DD |
| **Sterling Ratio** | `annualized_return / avg_annual_drawdown` | Return per avg drawdown |
| **Burke Ratio** | `annualized_return / max_drawdown` | Similar to Calmar |
| **Profit Factor** | `gross_profit / gross_loss` | Ratio of wins to losses |
| **Win Rate** | `winning_trades / total_trades × 100` | % of winning trades |
| **Avg Win %** | Mean of positive trade returns | Average winner size |
| **Avg Loss %** | Mean of negative trade returns | Average loser size |
| **Expectancy** | `(win_rate × avg_win) - (loss_rate × avg_loss)` | Expected return per trade |
| **Tail Ratio** | `95th percentile return / 5th percentile return` | Asymmetry of returns |
| **Skewness** | `E[(r - mean)^3] / σ^3` | Return distribution asymmetry |
| **Kurtosis** | `E[(r - mean)^4] / σ^4 - 3` | Return distribution tail weight |
| **Information Ratio** | `active_return / tracking_error` | Benchmark-relative performance |
| **MAE** | Max adverse excursion per trade | Worst intraday drawdown |
| **MFE** | Max favorable excursion per trade | Best intraday gain |
| **Recovery Factor** | `total_return / max_drawdown` | How fast it recovers |
| **Avg Trade Duration** | Mean hours between entry and exit | Holding period |

---

## 21. Advanced Features

### 21.1 Regime-Aware Position Sizing

```python
def compute_position_size(
    signal_strength: float,
    regime: str,
    strategy_type: str,
    portfolio_equity: float,
    risk_limits: RiskLimits,
) -> float:
    """
    Adjust position size based on market regime.
    Mean reversion strategies reduce size in trending markets.
    Momentum strategies reduce size in ranging markets.
    """
    base_size = portfolio_equity * 0.1  # 10% of equity default

    regime_multipliers = {
        "trending_up":   {"momentum": 1.2, "mean_reversion": 0.5},
        "trending_down": {"momentum": 0.8, "mean_reversion": 0.5},
        "ranging":       {"momentum": 0.6, "mean_reversion": 1.0},
        "high_vol":      {"momentum": 0.7, "mean_reversion": 0.7},
        "low_vol":       {"momentum": 0.8, "mean_reversion": 0.9},
    }

    multiplier = regime_multipliers.get(regime, {}).get(strategy_type, 1.0)
    adjusted_size = base_size * signal_strength * multiplier

    # Hard cap at position size limit
    max_size = portfolio_equity * (risk_limits.max_position_size_pct / 100)
    return min(adjusted_size, max_size)
```

### 21.2 Cross-Strategy Correlation Filter

```python
class CorrelationFilter:
    """
    Prevents opening a position in a pair if another
    strategy already has a position in a highly correlated pair.
    """

    CORRELATION_THRESHOLD = 0.7

    async def check(
        self,
        new_signal: SignalEvent,
        open_positions: list[Position],
        historical_returns: dict[str, list[float]],
    ) -> bool:
        """
        Returns True if new position is acceptable.
        Checks correlation of new pair returns with all open pair returns.
        """
        new_returns = historical_returns.get(new_signal.pair, [])
        if not new_returns:
            return True

        for pos in open_positions:
            pos_returns = historical_returns.get(pos.pair, [])
            if not pos_returns:
                continue

            correlation = self._compute_correlation(new_returns, pos_returns)
            if correlation > self.CORRELATION_THRESHOLD:
                return False
        return True

    def _compute_correlation(self, a: list, b: list) -> float:
        """Pearson correlation coefficient"""
        if len(a) != len(b) or len(a) < 10:
            return 0.0
        return np.corrcoef(a, b)[0, 1]
```

### 21.3 Signal Scoring + Ranking

```python
class SignalRanker:
    """
    When multiple strategies generate signals for different or same pairs,
    rank them by composite score and allocate capital accordingly.
    """

    async def rank(
        self,
        signals: list[SignalEvent],
        portfolio_equity: float,
    ) -> list[AllocatedSignal]:
        """
        Returns signals with allocated capital, sorted by score descending.
        """
        scored = []
        for s in signals:
            score = (
                s.strength * 0.4 +
                (1.0 - s.pair_correlation) * 0.2 +
                s.regime_fit * 0.2 +
                s.historical_win_rate * 0.2
            )
            scored.append((s, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Allocate capital top-down until max positions reached
        allocated = []
        remaining_equity = portfolio_equity
        max_positions = 10

        for signal, score in scored[:max_positions]:
            size = min(
                remaining_equity * 0.1,  # 10% of remaining equity
                portfolio_equity * 0.2,  # 20% of total equity hard cap
            )
            allocated.append(AllocatedSignal(signal=signal, score=score, size=size))
            remaining_equity -= size

        return allocated
```

---

## 22. Risk Registry

All risk limits are configurable at runtime:

```python
@dataclass
class RiskLimits:
    # Portfolio-level
    max_portfolio_drawdown_pct: float = 20.0    # Auto-pause all if exceeded
    daily_loss_limit_pct: float = 5.0           # Stop trading for the day
    max_leverage: float = 3.0

    # Position-level
    max_position_size_pct: float = 20.0        # % of equity per position
    max_open_positions: int = 10
    max_pairs_per_strategy: int = 5

    # Risk per trade
    max_risk_per_trade_pct: float = 2.0        # Max loss per trade as % of equity

    # Correlation
    max_strategy_correlation: float = 0.7

    # Circuit breaker
    circuit_breaker_consecutive_losses: int = 5

    # Stop loss
    default_stop_loss_pct: float = 2.0         # Default if not specified by strategy
    default_take_profit_pct: float = 6.0


class RiskLimitsRepository:
    """Persisted risk limits — can be updated at runtime without restart"""

    async def get_limits(self, user_id: UUID) -> RiskLimits:
        ...
    async def update_limits(self, user_id: UUID, limits: RiskLimits):
        ...
```

---

## 23. Gaps Fixed From v1

| # | v1 Gap | v2 Fix |
|---|---|---|
| 1 | No event-driven architecture defined | Full event pipeline (Tick → Signal → Order → Fill → Position → Portfolio) |
| 2 | Risk buried in backtest form | Dedicated RiskManager service with pre-trade checks + circuit breakers |
| 3 | No OMS | Full OrderManagementSystem with state machine, fills, cancellations |
| 4 | No strategy versioning | strategy_versions table with revert capability |
| 5 | Single strategy only | Multi-strategy portfolio backtest with cross-strategy correlation filter |
| 6 | Slippage = fixed BPS | Tiered slippage (size + volatility + side asymmetry) |
| 7 | No point-in-time validation | DataValidationLayer: crossed market, stale tick, spread sanity, close out of range |
| 8 | No market regime analysis | MarketRegimeAnalyzer with 5 regimes + regime-aware position sizing |
| 9 | No execution/session modeling | Execution-aware (settlement, overnight gaps per asset class) |
| 10 | Walk-forward described as train/test split | Proper expanding/rolling windows with overfit_score = mean(test)/std(test) |
| 11 | No signal-to-order translation | SignalRanker + PortfolioConstruction + OrderType selection |
| 12 | Missing key metrics | All 20+ metrics from Section 20 (Calmar, Sterling, Burke, MAE, MFE, Tail, Skew, Kurtosis) |
| 13 | No batch throttling | Redis-based token bucket rate limiter, 3 parallel workers |
| 14 | Backtest not persisted mid-run | BacktestStatePersistence saves every 100 candles |

---

## Appendix A: Key Configuration Examples

### BacktestConfig JSON (full)

```json
{
  "id": "uuid",
  "name": "ETH Mean Reversion 1H",
  "strategies": ["uuid-ma-crossover", "uuid-bollinger-rsi"],
  "portfolio": {
    "allocation": "equal",
    "weights": [0.5, 0.5],
    "correlation_limit": 0.7
  },
  "pairs": ["ETH/USDT", "BTC/USDT"],
  "timeframes": ["1h", "4h"],
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "exchange": "binance",
  "initial_capital": 10000,
  "leverage": 1,
  "position_sizing": {
    "type": "percent_equity",
    "value": 10
  },
  "max_positions": 5,
  "direction": "both",
  "fees": {
    "maker": 0.001,
    "taker": 0.002
  },
  "slippage_model": {
    "type": "tiered",
    "base_bps": 2.0,
    "adv_pct_threshold": 0.01,
    "vol_multiplier": 1.5
  },
  "walk_forward": {
    "enabled": true,
    "mode": "expanding",
    "train_pct": 0.6,
    "test_pct": 0.2,
    "step_pct": 0.1
  },
  "monte_carlo": {
    "enabled": true,
    "runs": 1000
  },
  "risk_limits": {
    "max_portfolio_drawdown_pct": 20,
    "daily_loss_limit_pct": 5,
    "max_position_size_pct": 20,
    "max_open_positions": 10,
    "circuit_breaker_consecutive_losses": 5
  }
}
```

### Strategy Parameter JSON

```json
{
  "strategy_type": "bollinger_rsi",
  "description": "Buy when price touches lower Bollinger Band and RSI < 30. Sell when RSI > 70 or price touches upper band.",
  "parameters": {
    "bb_period": {"value": 20, "min": 10, "max": 50, "step": 1},
    "bb_std": {"value": 2.0, "min": 1.0, "max": 3.0, "step": 0.1},
    "rsi_period": {"value": 14, "min": 7, "max": 28, "step": 1},
    "rsi_entry": {"value": 30, "min": 20, "max": 40, "step": 1},
    "rsi_exit": {"value": 70, "min": 60, "max": 80, "step": 1},
    "stop_loss_pct": {"value": 2.0, "min": 1.0, "max": 5.0, "step": 0.1},
    "take_profit_pct": {"value": 4.0, "min": 2.0, "max": 10.0, "step": 0.1},
    "position_size_pct": {"value": 10, "min": 5, "max": 30, "step": 1}
  },
  "required_indicators": ["bb", "rsi"],
  "timeframes": ["1h", "4h", "1d"],
  "pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
}
```

---

*Plan version: 2.0*
*Created: 2025-05-19*
*Total pages: ~23 sections*
*Estimated build: 6–7 weeks*