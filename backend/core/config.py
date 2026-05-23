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
    redis_password: str = ""
    redis_max_connections: int = 50

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Anthropic/MiniMax LLM
    anthropic_base_url: str = "https://api.minimax.io/anthropic"
    anthropic_api_key: str = ""

    # Exchange
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # OKX
    okx_api_key: str = ""
    okx_secret: str = ""
    okx_password: str = ""

    # Kraken
    kraken_api_key: str = ""
    kraken_secret: str = ""

    # App Config
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()