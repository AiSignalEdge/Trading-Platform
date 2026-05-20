# Trading Strategy Dashboard — Full Implementation Plan

## 1. Concept & Vision

A **production-grade trading strategy research lab** — not a toy demo. Think: Bloomberg Terminal meets TradingView Pine Script editor, powered by AI-assisted strategy generation and a massive backtesting engine.

The dashboard lets traders:
- Browse, search, and filter thousands of community-submitted strategies
- Run deep backtests across any combination of pair, timeframe, and date range
- Schedule automated batch backtesting (cron-like loops)
- Compare strategies side-by-side
- Export to TradingView / live execute

**Personality:** Dense, data-rich, professional. Every pixel earns its place. Dark theme. Numbers first.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React + Next.js + Tailwind + Lightweight Charts (TV)       │
│  WebSocket for live data, polling for strategy list          │
└────────────────┬────────────────────────────────────────────┘
                 │ REST + WebSocket
┌────────────────▼────────────────────────────────────────────┐
│                    API SERVER (FastAPI)                      │
│  /strategies   /backtest   /automate   /pairs   /auth       │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   CORE SERVICES                             │
│  • Strategy Registry (PostgreSQL)                            │
│  • Backtest Engine (backtrader / vectorbt)                  │
│  • Scheduler (APScheduler) — automated backtests             │
│  • AI Strategy Generator (Claude API / local)                │
│  • TradingView Integration (Pine Script export)              │
└─────────────────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   DATA LAYER                                 │
│  • PostgreSQL: strategies, backtest results, user prefs      │
│  • Redis: cache, session, pub/sub for job status             │
│  • MinIO/S3: equity curves, trade logs, export files         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

### Table: `strategies`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR(255) | Strategy display name |
| description | TEXT | Strategy description |
| author | VARCHAR(255) | Creator username |
| strategy_type | ENUM | 'momentum', 'mean_reversion', 'grid', 'arbitrage', 'moon_phase', 'custom' |
| asset_class | ENUM | 'crypto', 'forex', 'stocks', 'commodities' |
| pairs | TEXT[] | Array of trading pairs, e.g. ['ETH/USDT', 'BTC/USDT'] |
| timeframe | TEXT[] | Array e.g. ['1h', '4h', '1d'] |
| parameters | JSONB | Strategy parameters (moving window, threshold, etc.) |
| pine_script | TEXT | Full TradingView Pine Script code |
| tags | TEXT[] | Searchable tags |
| backtest_summary | JSONB | Cached summary stats |
| rating | FLOAT | Community rating 0-5 |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |
| is_public | BOOLEAN | Community visibility |

### Table: `backtest_results`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| strategy_id | UUID | FK → strategies |
| pair | VARCHAR(50) | e.g. 'ETH/USDT' |
| timeframe | VARCHAR(20) | e.g. '1h' |
| start_date | DATE | Backtest start |
| end_date | DATE | Backtest end |
| initial_capital | DECIMAL | Starting capital |
| final_equity | DECIMAL | Ending equity |
| total_return | DECIMAL | Percentage return |
| max_drawdown | DECIMAL | Max drawdown % |
| sharpe_ratio | DECIMAL | Risk-adjusted return |
| sortino_ratio | DECIMAL | Downside risk metric |
| profit_factor | DECIMAL | Gross profit / gross loss |
| win_rate | DECIMAL | Percentage of winning trades |
| total_trades | INTEGER | Number of closed trades |
| avg_trade_return | DECIMAL | Average return per trade |
| expectancy | DECIMAL | Win rate × avg win - loss rate × avg loss |
| equity_curve | JSONB | Array of daily equity values |
| trades | JSONB | Array of individual trade objects |
| settings | JSONB | Exact params used for this run |
| created_at | TIMESTAMP | Run time |

### Table: `automated_jobs`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR(255) | Job display name |
| strategy_id | UUID | FK → strategies |
| pairs | TEXT[] | Pairs to test |
| timeframes | TEXT[] | Timeframes to test |
| schedule | CRON | Cron expression |
| params | JSONB | Strategy param overrides |
| status | ENUM | 'active', 'paused', 'failed', 'completed' |
| last_run | TIMESTAMP | Last execution time |
| next_run | TIMESTAMP | Next scheduled run |
| results | UUID[] | FK → backtest_results |
| created_by | VARCHAR(255) | User who created it |

### Table: `users`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| username | VARCHAR(255) | Unique username |
| email | VARCHAR(255) | Email |
| api_key_hash | VARCHAR(255) | Hashed API key |
| plan | ENUM | 'free', 'pro', 'enterprise' |
| created_at | TIMESTAMP | Signup time |

---

## 4. Frontend — Page Structure

### 4.1 Layout
- **Sidebar** (240px fixed): Navigation, strategy categories, quick filters
- **Top bar**: Search, notifications bell, user menu, live market ticker strip
- **Main content**: Changes based on active route

```
┌────────────┬──────────────────────────────────────────┐
│            │  [Market Ticker Strip — scrolling]       │
│  SIDEBAR   ├──────────────────────────────────────────┤
│            │                                          │
│  • Home    │         MAIN CONTENT AREA                │
│  • Strateg │                                          │
│  • Backtest│                                          │
│  • Automate│                                          │
│  • Compare │                                          │
│  • Export  │                                          │
│  • Settings│                                          │
│            │                                          │
└────────────┴──────────────────────────────────────────┘
```

### 4.2 Pages

#### Page 1: `/strategies` — Strategy Library
**Purpose:** Browse, search, filter all strategies.

**Features:**
- Grid/List toggle view (grid shows cards, list shows sortable table)
- Search bar (fuzzy search across name, description, tags, author)
- Filter panel (collapsible left panel):
  - Strategy type (multi-select checkboxes)
  - Asset class
  - Pairs (multi-select)
  - Timeframe (multi-select)
  - Max drawdown (slider: 0–50%)
  - Min profit factor (input)
  - Min Sharpe ratio (input)
  - Rating (1–5 stars)
  - Date range (created within X days)
- Sort: by rating, by return, by Sharpe, by newest, by most backtested
- Each strategy card shows:
  - Name + author avatar
  - Strategy type badge
  - Pair + timeframe
  - Key stats: Return %, Max DD, Sharpe, Trades, Win Rate
  - Mini equity curve sparkline (SVG)
  - Tags
  - Quick action buttons: "Backtest" / "Add to Compare" / "Fork" / "Save"

**Actions on a strategy:**
- **Backtest now** → opens backtest modal pre-filled with strategy
- **Fork** → duplicates strategy into user's workspace, opens editor
- **Compare** → adds to comparison panel (up to 5 at a time)
- **View details** → opens full strategy detail page
- **Export to TradingView** → downloads .pine file

#### Page 2: `/strategies/[id]` — Strategy Detail
**Purpose:** Deep dive into a single strategy.

**Sections:**
1. **Header**: Name, author, rating, tags, share button
2. **Stats Overview**: 3-column card grid (Return, Max DD, Sharpe, Win Rate, PF, Trades)
3. **Equity Curve**: Full-width TradingView Lightweight Charts, zoomable, with drawdown overlay
4. **Trade Log**: Sortable/filterable table — columns: #, Date, Type (Long/Short), Entry Price, Exit Price, Size, P&L, P&L %, Cumulative Equity
5. **Parameters**: JSON tree view with editable fields
6. **Pine Script Preview**: Syntax-highlighted code block with copy button
7. **Community Backtests**: Table of all historical backtests on this strategy — filterable by pair/timeframe/date
8. **Similar Strategies**: "Users also viewed" carousel

#### Page 3: `/backtest` — Backtest Runner
**Purpose:** Configure and launch a backtest.

**Form sections:**

1. **Strategy Selection**
   - Search/select from library OR paste Pine Script / describe in plain English (AI generates params)
   - Option to "Use existing strategy" or "Create new from description"

2. **Universe Configuration**
   - **Pairs**: Multi-select with search (BTC/USDT, ETH/USDT, SOL/USDT, AVAX/USDT, etc.)
   - **Timeframes**: Multi-select (1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W)
   - **Date Range**: Preset buttons (Last 30D, 90D, 6M, 1Y, 2Y, 3Y, YTD, Custom)
   - **Exchange**: Binance (default), Coinbase, Kraken, Bybit

3. **Capital & Risk Settings**
   - Initial capital (default $10,000)
   - Leverage (1x–100x slider)
   - Position sizing type: Fixed, % of equity, Kelly criterion
   - Max positions per pair
   - Allowed trade direction: Long only, Short only, Both

4. **Fees & Slippage**
   - Maker fee %
   - Taker fee %
   - Slippage model: None, Fixed bps, Dynamic

5. **Advanced**
   - Walk-forward testing: On/Off (enables out-of-sample validation)
   - Monte Carlo simulation: N runs (default 0 = off)
   - Parameter optimization: grid search over defined ranges

6. **Execution Controls**
   - "Run Single" button → runs one backtest synchronously
   - "Run Batch" button → queues all pair×timeframe combinations
   - Progress bar during execution with live trade counter
   - "Schedule Recurring" button → opens scheduler modal

**Results Panel (appears below form after run):**
- Same equity curve + trade log as Strategy Detail page
- Comparison table across all pair/timeframe combinations tested
- "Best combination" highlighted
- "Export CSV", "Export JSON", "Save to Strategy" buttons

#### Page 4: `/automate` — Automated Backtesting
**Purpose:** Schedule and manage recurring backtest jobs.

**Features:**

1. **Job List View**
   - Table: Job name, strategy, schedule (cron), status badge, last run, next run, action buttons
   - Status badges: 🟢 Active, 🟡 Paused, 🔴 Failed, ⬜ Completed

2. **Create Job Modal**
   - Select strategy
   - Select pairs + timeframes
   - Set cron schedule: presets (Every 15min, Hourly, Daily, Weekly) or custom cron expression
   - Notification settings: On complete, On failure, Never
   - Auto-stop conditions: After N consecutive failures, After N total runs

3. **Job Detail View**
   - Run history: table of all executions with timestamp, result, duration, error
   - Click any run → full backtest result
   - Logs: scrolling log of what happened during execution

4. **Loop Templates**
   - Pre-built loop strategies (like Trader Dev's GitHub repo):
     - **Moon Phase Strategist**: trades based on lunar cycles
     - **Trend Following**: 3 SMAs + ADX filter
     - **Mean Reversion**: Bollinger Bands + RSI
     - **Momentum**: MACD + Volume spike
     - **Overfit Detector**: run strategy across N random seeds → report overfit score
     - **Parameter Optimizer**: gradient descent on strategy params
   - Each template is a JSON config that drives the backtester

#### Page 5: `/compare` — Strategy Comparison
**Purpose:** Compare up to 5 strategies side-by-side.

**Layout:** Side-by-side columns, each showing a strategy's equity curve and stats.

**Features:**
- Drag strategies from library into comparison slots
- Sync zoom/pan across all equity curves
- Stats comparison table (all metrics in one grid)
- "Winner" column highlight (best in each metric)
- Radar chart for multi-dimensional comparison
- Export comparison report as PDF

#### Page 6: `/export` — TradingView Export
**Purpose:** Export strategies and signals for live trading.

**Features:**
- One-click "Add to TradingView" → opens TradingView Pine Editor with strategy code
- Export as .pine file (download)
- Export trade signals as CSV (entry/exit dates + prices)
- Webhook integration: POST trade signals to external URL

#### Page 7: `/settings` — User Settings
**Purpose:** Configure API keys, notifications, display preferences.

**Sections:**
- **Exchange API Keys**: Add/remove exchange credentials (for live trading)
- **Notification Preferences**: Telegram, Discord webhook, email
- **Display**: Dark/Light mode, default timeframe, default capital
- **API Access**: Personal API key for programmatic access

---

## 5. Backtest Engine

### 5.1 Supported Strategies (Core)
| Strategy | Description | Key Params |
|---|---|---|
| Moving Average Crossover | Fast MA vs slow MA | fast_period, slow_period, MA_type |
| Mean Reversion | Bollinger + RSI | bb_period, bb_std, rsi_period, rsi_entry |
| Momentum | MACD + Volume | macd_fast, macd_slow, volume_threshold |
| Grid Trading | Buy/sell at price levels | grid_spacing_pct, num_levels, auto_rebalance |
| Moon Phase | Lunar cycle trading | phase_sensitivity |
| RSI Divergence | Custom RSI signals | rsi_period, divergence_lookback |
| Donchian Breakout | Break of n-period high/low | breakout_period |
| Kelly Criterion Sizing | Dynamic position sizing | kelly_fraction |

### 5.2 Backtest Configuration
```json
{
  "strategy_id": "uuid",
  "pair": "ETH/USDT",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "exchange": "binance",
  "initial_capital": 10000,
  "leverage": 1,
  "position_sizing": {
    "type": "percent_equity",
    "value": 10
  },
  "max_positions": 3,
  "direction": "both",
  "fees": {
    "maker": 0.001,
    "taker": 0.002
  },
  "slippage_model": "fixed_bps",
  "slippage_bps": 5,
  "walk_forward": {
    "enabled": false,
    "train_pct": 0.7,
    "test_pct": 0.3
  },
  "monte_carlo": {
    "enabled": false,
    "runs": 1000
  }
}
```

### 5.3 Output Metrics
- Total Return (%)
- Annualized Return (%)
- Max Drawdown (%)
- Max Drawdown Duration (days)
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Profit Factor
- Win Rate (%)
- Average Win (%)
- Average Loss (%)
- Expectancy
- Total Trades
- Avg Trade Duration
- Recovery Factor

---

## 6. API Server (FastAPI)

### Endpoints

#### Strategies
```
GET    /api/strategies                 List strategies (paginated, filterable)
POST   /api/strategies                 Create new strategy
GET    /api/strategies/{id}            Get strategy details
PUT    /api/strategies/{id}            Update strategy
DELETE /api/strategies/{id}             Delete strategy
POST   /api/strategies/{id}/fork       Fork a strategy
GET    /api/strategies/{id}/backtests  List all backtests for strategy
```

#### Backtest
```
POST   /api/backtest                   Run a single backtest (async or sync)
POST   /api/backtest/batch             Run batch across multiple pairs/timeframes
GET    /api/backtest/{id}              Get backtest result
GET    /api/backtest/{id}/equity       Get equity curve data points
GET    /api/backtest/{id}/trades       Get trade log
DELETE /api/backtest/{id}              Delete backtest result
```

#### Automate
```
GET    /api/jobs                       List automated jobs
POST   /api/jobs                       Create automated job
GET    /api/jobs/{id}                  Get job details + history
PUT    /api/jobs/{id}                  Update job (pause/resume/edit)
DELETE /api/jobs/{id}                  Delete job
POST   /api/jobs/{id}/run              Trigger immediate run
GET    /api/jobs/{id}/history          Get execution history
```

#### Pairs & Data
```
GET    /api/pairs                      List available trading pairs
GET    /api/timeframes                 List available timeframes
GET    /api/candles?pair=ETH/USDT&timeframe=1h&start=...&end=...  Get OHLCV data
```

#### User
```
POST   /api/auth/register
POST   /api/auth/login
GET    /api/user/me
PUT    /api/user/me
```

#### AI Strategy Generation
```
POST   /api/ai/generate                 Generate strategy from description
POST   /api/ai/optimize                 Optimize strategy parameters
POST   /api/ai/describe                 Describe a strategy in plain English
```

---

## 7. Real-time Features

### WebSocket Events
| Event | Direction | Payload |
|---|---|---|
| `backtest.started` | Server→Client | { job_id, strategy_name, pair, timeframe } |
| `backtest.progress` | Server→Client | { job_id, progress_pct, trades_so_far, current_equity } |
| `backtest.completed` | Server→Client | { job_id, summary_metrics, result_id } |
| `backtest.failed` | Server→Client | { job_id, error_message } |
| `job.triggered` | Server→Client | { job_id, schedule_info } |
| `market.ticker` | Server→Client | { pair, price, change_24h, volume } |

### Polling (fallback)
- Strategy list: refresh every 30s
- Job status: every 10s
- Backtest progress: via WebSocket (primary) or polling

---

## 8. File Structure

```
/trading-dashboard
├── backend/
│   ├── main.py                    FastAPI app entry
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── strategies.py
│   │   │   ├── backtest.py
│   │   │   ├── jobs.py
│   │   │   ├── pairs.py
│   │   │   └── auth.py
│   │   └── deps.py               Auth dependencies
│   ├── core/
│   │   ├── config.py             Settings/env
│   │   ├── database.py           PostgreSQL connection
│   │   └── redis.py              Redis connection
│   ├── services/
│   │   ├── strategy_registry.py
│   │   ├── backtest_engine.py     The actual backtesting logic
│   │   ├── scheduler.py           APScheduler job management
│   │   ├── ai_generator.py        Claude AI strategy generation
│   │   └── tradingview_export.py Pine Script export
│   ├── models/
│   │   ├── strategy.py
│   │   ├── backtest_result.py
│   │   ├── job.py
│   │   └── user.py
│   └── schemas/                  Pydantic models
│       ├── strategy.py
│       ├── backtest.py
│       └── job.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           Home
│   │   │   ├── strategies/
│   │   │   │   ├── page.tsx       Strategy library
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx   Strategy detail
│   │   │   ├── backtest/
│   │   │   │   └── page.tsx
│   │   │   ├── automate/
│   │   │   │   └── page.tsx
│   │   │   ├── compare/
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
│   │   │   │   └── StrategyTable.tsx
│   │   │   ├── backtest/
│   │   │   │   ├── BacktestForm.tsx
│   │   │   │   ├── BacktestProgress.tsx
│   │   │   │   ├── BacktestResults.tsx
│   │   │   │   └── EquityCurveChart.tsx
│   │   │   ├── automate/
│   │   │   │   ├── JobList.tsx
│   │   │   │   ├── JobScheduler.tsx
│   │   │   │   └── CronBuilder.tsx
│   │   │   └── ui/
│   │   │       ├── Button.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Table.tsx
│   │   │       ├── Badge.tsx
│   │   │       └── Chart.tsx
│   │   ├── hooks/
│   │   │   ├── useStrategies.ts
│   │   │   ├── useBacktest.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useJobs.ts
│   │   ├── lib/
│   │   │   ├── api.ts              Axios/fetch wrapper
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   └── store/
│   │       ├── strategyStore.ts   Zustand
│   │       └── backtestStore.ts
├── scripts/
│   ├── seed_strategies.py          Seed DB with 100+ strategies
│   ├── backfill_candles.py         Download historical OHLCV data
│   └── run_backtests.py            CLI backtest runner
├── tests/
│   ├── unit/
│   │   ├── test_backtest_engine.py
│   │   ├── test_strategy_registry.py
│   │   └── test_ai_generator.py
│   └── integration/
│       ├── test_api_strategies.py
│       └── test_api_backtest.py
├── requirements.txt
├── package.json
└── README.md
```

---

## 9. Tech Stack

### Backend
| Component | Tool |
|---|---|
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2.0 + asyncpg |
| Migration | Alembic |
| Task Queue | APScheduler (in-process) or Celery (Redis) |
| Caching | Redis |
| Auth | JWT (python-jose) |
| Validation | Pydantic v2 |
| Backtest Engine | backtrader or vectorbt |
| HTTP Client | httpx |
| WebSocket | FastAPI WebSocket |

### Frontend
| Component | Tool |
|---|---|
| Framework | Next.js 14 (App Router) |
| UI Library | Radix UI (shadcn/ui components) |
| Styling | Tailwind CSS |
| State | Zustand |
| Data Fetching | TanStack Query (React Query) |
| Charts | TradingView Lightweight Charts |
| Tables | TanStack Table |
| Forms | React Hook Form + Zod |
| WebSocket | Native WebSocket API |
| Icons | Lucide React |

### Infrastructure (Native)
| Component | Tool |
|---|---|
| Database | PostgreSQL 15 (apt install) |
| Cache | Redis 7 (apt install) |
| Object Storage | Local filesystem (MinIO optional later) |

---

## 10. Implementation Phases

### Phase 1: Foundation (Week 1–2)
- [ ] Install PostgreSQL + Redis via apt
- [ ] Create trading_db database + user
- [ ] FastAPI skeleton with all route stubs
- [ ] Database models + Alembic migrations
- [ ] Basic auth (JWT)
- [ ] Frontend Next.js scaffold with layout (sidebar, topbar)
- [ ] Strategy list page (mock data)

### Phase 2: Backtest Engine (Week 2–3)
- [ ] Implement backtrader integration
- [ ] Download historical data (Binance public API)
- [ ] Backtest API endpoints
- [ ] Equity curve + trade log storage
- [ ] Frontend backtest form + results display
- [ ] WebSocket progress updates

### Phase 3: Strategy Library (Week 3–4)
- [ ] Full CRUD for strategies
- [ ] Search + filter UI
- [ ] Strategy detail page with equity curve
- [ ] Pine Script export
- [ ] Seed script with 100+ example strategies

### Phase 4: Automation (Week 4–5)
- [ ] APScheduler integration
- [ ] Job CRUD API
- [ ] Scheduler UI (cron builder)
- [ ] Loop templates (Moon Phase, Trend Following, etc.)
- [ ] Notification system (Telegram webhook)

### Phase 5: AI Generation (Week 5–6)
- [ ] Claude API integration
- [ ] Strategy generation from description
- [ ] Parameter optimizer
- [ ] Walk-forward + Monte Carlo
- [ ] "Vibe to rules" workflow

### Phase 6: Polish & Launch (Week 6–7)
- [ ] Comparison page
- [ ] Community features (rating, comments)
- [ ] TradingView direct import
- [ ] Performance optimization (caching, indexing)
- [ ] Documentation

---

## 11. Key Implementation Details

### 11.1 Backtest Progress Streaming
```python
# When a backtest is running, stream progress via WebSocket
# Frontend subscribes to ws://host/backtest/{job_id}
# Backend emits: { "type": "progress", "trades": 45, "equity": 11234.56, "pct": 34 }
```

### 11.2 Batch Backtest Queue
```python
# Batch run: 5 pairs × 4 timeframes = 20 combinations
# Each combination is an independent backtest job
# Use Redis queue with worker pool
# Limit concurrency to avoid rate limiting exchange API
```

### 11.3 Strategy Parameter JSON Schema
```json
{
  "strategy_type": "moving_average_crossover",
  "params": {
    "fast_ma_period": 10,
    "slow_ma_period": 50,
    "ma_type": "EMA",
    "entry_threshold_pct": 0.5,
    "stop_loss_pct": 2.0,
    "take_profit_pct": 5.0
  }
}
```

### 11.4 Pine Script Export Template
```python
def export_to_pine(strategy_params: dict) -> str:
    # Takes strategy params JSON → outputs valid Pine Script v5
    # Uses templating to generate fully functional strategy
```

### 11.5 Walk-Forward Testing
```
Train period: 70% of data → optimize parameters
Test period: 30% of data → validate
Repeat with rolling window (e.g., step = 30 days)
Report: average train_metric vs test_metric (overfit score)
```

---

## 12. Environment Variables & Setup

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql postgresql-contrib redis-server

# Start services
sudo systemctl enable postgresql redis-server
sudo systemctl start postgresql
sudo systemctl start redis-server

# Create database
sudo -u postgres createdb trading_db
sudo -u postgres createuser trading_user
sudo -u postgres psql -c "ALTER USER trading_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trading_db TO trading_user;"

# Backend
DATABASE_URL=postgresql+asyncpg://trading_user:your_password@localhost:5432/trading_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-min-32-chars
CLAUDE_API_KEY=sk-ant-...

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 13. Risks & Open Questions

1. **Backtest quality**: Crypto candles from Binance public API may have gaps. Need to validate data integrity.
2. **Overfitting**: High-return strategies may be curve-fitted. Walk-forward testing is essential.
3. **Rate limits**: Binance API rate limiting (1200/min). Batch backtests need throttling.
4. **WebSocket scalability**: If many users run backtests simultaneously, WebSocket connections multiply. Consider Redis pub/sub for multi-instance.
5. **Strategy storage**: Pine Script can be large. Consider storing compressed or in S3.
6. **Live trading**: This dashboard is research-only initially. Live execution requires exchange API keys + risk controls.

---

*Plan created: 2025-05-19*
*Estimated build time: 6–7 weeks (full team)*