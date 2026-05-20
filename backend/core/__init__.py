"""
Core - Configuration, Database, Redis, and Event Bus.

All items should be imported from submodules directly:
  from core.config import settings, Settings
  from core.database import get_db, Base
  from core.redis import redis_manager

This package only re-exports config to avoid circular imports at startup.
"""

from .config import settings, get_settings, Settings

__all__ = [
    "settings",
    "get_settings",
    "Settings",
]