"""Add performance indexes for query optimization.

Revision ID: add_perf_indexes
Revises:
Create Date: 2025-05-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_perf_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index on backtest_results(strategy_id, created_at) for fast strategy lookups
    op.create_index(
        'ix_backtest_results_strategy_created',
        'backtest_results',
        ['strategy_id', 'created_at'],
        unique=False,
    )

    # Index on backtest_results(pair, timeframe) for pair/timeframe queries
    op.create_index(
        'ix_backtest_results_pair_timeframe',
        'backtest_results',
        ['pair', 'timeframe'],
        unique=False,
    )

    # Index on candles(pair, timeframe, timestamp) for candle lookups
    # Note: candles table uses exchange/symbol, mapping to pair via symbol
    op.create_index(
        'ix_candles_symbol_timeframe_timestamp',
        'candles',
        ['symbol', 'timeframe', 'timestamp'],
        unique=False,
    )

    # Index on automated_jobs(status, next_run_at) for job scheduling
    op.create_index(
        'ix_automated_jobs_status_next_run',
        'automated_jobs',
        ['status', 'next_run_at'],
        unique=False,
    )

    # Additional composite index for backtest_results created_at ordering
    op.create_index(
        'ix_backtest_results_created_at',
        'backtest_results',
        ['created_at'],
        unique=False,
    )

    # Index on strategies for type/public filtering
    op.create_index(
        'ix_strategies_type_public',
        'strategies',
        ['strategy_type', 'is_public'],
        unique=False,
    )

    # Index on market_regimes for pair/timeframe queries
    op.create_index(
        'ix_market_regimes_pair_timeframe',
        'market_regimes',
        ['pair', 'timeframe'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_backtest_results_strategy_created', 'backtest_results')
    op.drop_index('ix_backtest_results_pair_timeframe', 'backtest_results')
    op.drop_index('ix_candles_symbol_timeframe_timestamp', 'candles')
    op.drop_index('ix_automated_jobs_status_next_run', 'automated_jobs')
    op.drop_index('ix_backtest_results_created_at', 'backtest_results')
    op.drop_index('ix_strategies_type_public', 'strategies')
    op.drop_index('ix_market_regimes_pair_timeframe', 'market_regimes')