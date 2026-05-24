"""Core configuration — all settings from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Hermes Trading Dashboard"
    debug: bool = True
    api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://trading_user:dev123@localhost:5432/trading_db"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
    redis_max_connections: int = 50

    # JWT Authentication
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # Binance Exchange (CCXT)
    binance_api_key: str = ""
    binance_secret: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # OKX Exchange
    okx_api_key: str = ""
    okx_secret: str = ""
    okx_password: str = ""

    # Kraken Exchange
    kraken_api_key: str = ""
    kraken_secret: str = ""

    # Claude AI (for strategy generation + optimization)
    claude_api_key: str = ""

    # Anthropic/MiniMax LLM (Anthropic-compatible API)
    anthropic_base_url: str = "https://api.minimax.io/anthropic"
    anthropic_api_key: str = ""

    # Telegram Bot Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Discord Webhook Notifications
    discord_webhook_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()