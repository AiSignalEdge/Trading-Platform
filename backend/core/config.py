"""Core configuration — all settings from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Hermes Trading Dashboard"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://trading_user:dev123@localhost:5432/trading_db"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Exchange API Keys (optional — public data works without these)
    binance_api_key: str = ""
    binance_secret: str = ""
    binance_testnet: bool = False

    okx_api_key: str = ""
    okx_secret: str = ""
    okx_password: str = ""

    kraken_api_key: str = ""
    kraken_secret: str = ""

    bybit_api_key: str = ""
    bybit_secret: str = ""

    # Trading defaults
    default_timeframe: str = "1h"
    default_initial_cash: float = 10_000.0
    default_commission: float = 0.001
    default_slippage: float = 0.0005

    # Paths
    data_dir: str = "./data"
    backtest_results_dir: str = "./backtest_results"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()