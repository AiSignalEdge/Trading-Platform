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

    # AI Provider (Anthropic-compatible MiniMax API)
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.minimax.chat"

    # Binance
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

    # Notification Settings
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # App Config
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()