"""
Migration script to create execution_orders and execution_positions tables.
Run with: python -m migrations.create_execution_tables
"""

import asyncio
import asyncpg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://trading_user:Trading%402025@localhost:5432/trading_db"


async def create_tables():
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Create execution_orders table (separate from backtest orders)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_orders (
                id UUID PRIMARY KEY,
                strategy_id UUID NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                order_type VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                price FLOAT,
                filled_quantity FLOAT NOT NULL DEFAULT 0,
                avg_fill_price FLOAT NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                filled_at TIMESTAMP
            );
        """)
        logger.info("✓ execution_orders table created/verified")

        # Create execution_positions table (separate from backtest positions)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_positions (
                id UUID PRIMARY KEY,
                strategy_id UUID NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                entry_price FLOAT NOT NULL,
                current_price FLOAT NOT NULL,
                unrealized_pnl FLOAT NOT NULL DEFAULT 0,
                realized_pnl FLOAT NOT NULL DEFAULT 0,
                opened_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
        """)
        logger.info("✓ execution_positions table created/verified")

        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_orders_strategy_id ON execution_orders(strategy_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_orders_symbol ON execution_orders(symbol);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_positions_strategy_id ON execution_positions(strategy_id);
        """)
        logger.info("✓ indexes created/verified")

        # Verify tables exist
        result = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('execution_orders', 'execution_positions');
        """)
        logger.info(f"Existing tables: {[r['table_name'] for r in result]}")

    finally:
        await conn.close()
        logger.info("Database migration complete")


if __name__ == "__main__":
    asyncio.run(create_tables())