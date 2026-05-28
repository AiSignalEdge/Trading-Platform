# Trading Research Platform

A quantitative trading research platform for backtesting, strategy development, and portfolio analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│                   Dashboard, Charts, Strategy Editor             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Server (FastAPI)                       │
│  Routes: strategies, backtest, export, data-quality, signals     │
└─────────────────────────────────────────────────────────────────┘
         │               │              │              │
         ▼               ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  PostgreSQL │  │    Redis    │  │  Backtest   │  │   Signals   │
│  Database   │  │   Cache     │  │   Engine    │  │   Engine    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

## Quick Start

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis connection strings
   ```

3. **Run the server**:
   ```bash
   python main.py
   # Or: ./start.sh
   ```

## Features

- **Strategy Management**: Create, version, and manage trading strategies
- **Backtesting Engine**: VectorBT-powered backtesting with batch and walk-forward analysis
- **Monte Carlo Simulation**: Risk assessment through stochastic simulation
- **Data Quality Dashboard**: Monitor candle data integrity, detect gaps and anomalies
- **Portfolio Optimization**: Position sizing and risk management
- **Export System**: JSON/CSV exports for backtest results and equity curves
- **Signal Generation**: Technical indicator-based signal generation
- **Webhooks**: Event-driven integrations with external systems
- **Real-time Updates**: WebSocket support for live progress tracking

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/strategies` | List all strategies with pagination |
| GET | `/api/v1/strategies/{id}` | Get strategy by ID |
| POST | `/api/v1/strategies` | Create new strategy |
| PUT | `/api/v1/strategies/{id}` | Update strategy |
| DELETE | `/api/v1/strategies/{id}` | Delete strategy |
| POST | `/api/v1/strategies/{id}/versions` | Create strategy version |
| GET | `/api/v1/backtest` | List backtest results |
| POST | `/api/v1/backtest` | Run backtest |
| POST | `/api/v1/backtest/run` | Run backtest synchronously |
| GET | `/api/v1/backtest/{id}` | Get backtest result details |
| GET | `/api/v1/data-quality/candles` | Get candle data quality metrics |
| GET | `/api/v1/data-quality/candles/{pair}/{timeframe}/gaps` | Get gap info for pair/timeframe |
| GET | `/api/v1/data-quality/summary` | Get overall data quality score |
| POST | `/api/v1/export/backtest/{id}` | Export backtest results |
| GET | `/api/v1/signals` | Generate trading signals |
| GET | `/api/v1/health` | Health check |

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Server | FastAPI (Python 3.11+) |
| Database | PostgreSQL with SQLAlchemy |
| Cache | Redis |
| Backtesting | VectorBT |
| Frontend | React |
| Task Queue | APScheduler |
| Data Storage | Pandas |

## Project Structure

```
Trading/
├── backend/
│   ├── api/
│   │   └── routes/          # API endpoints
│   │       ├── strategies.py
│   │       ├── backtest.py
│   │       ├── data_quality.py
│   │       ├── export.py
│   │       └── signals.py
│   ├── core/
│   │   ├── config.py         # Settings management
│   │   ├── database.py       # DB connection
│   │   ├── redis.py          # Redis client
│   │   └── tables.py         # SQLAlchemy table definitions
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── strategy.py
│   │   ├── backtest.py
│   │   └── job.py
│   ├── services/
│   │   ├── backtest/        # Backtest engine
│   │   └── data/            # Data store (candles)
│   └── migrations/          # Alembic migrations
│       └── versions/
├── frontend/                 # React application
├── PLAN-v2.md              # Full project specification
└── README.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | postgresql://localhost/trading |
| `REDIS_URL` | Redis connection string | redis://localhost:6379/0 |
| `REDIS_MAX_CONNECTIONS` | Max Redis connections | 50 |
| `API_HOST` | Server host | 0.0.0.0 |
| `API_PORT` | Server port | 8000 |
| `LOG_LEVEL` | Logging level | INFO |

## Data Quality Monitoring

The platform includes a comprehensive data quality dashboard:

- **Gap Detection**: Identifies missing candle ranges using timestamp analysis
- **Staleness Monitoring**: Alerts when data is older than expected thresholds
- **Volume Anomalies**: Flags candles with volume > 3x rolling average
- **Price Anomalies**: Detects candles with > 5% price change from previous

Quality score (0-100) is calculated based on:
- Gaps detected (max -30 points)
- Stale pairs (max -30 points)
- Volume anomalies (max -20 points)
- Price anomalies (max -20 points)