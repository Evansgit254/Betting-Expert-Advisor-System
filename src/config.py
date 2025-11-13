"""Application configuration using Pydantic settings.

This module centralizes environment configuration with validation and
runtime safety checks introduced as part of the critical fixes rollout.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


LIVE_MODE_REQUIRED_FIELDS = (
    "BOOKIE_API_KEY",
    "BOOKIE_API_BASE_URL",
    "BETFAIR_APP_KEY",
    "BETFAIR_SESSION_TOKEN",
)


class Settings(BaseSettings):
    """Application settings loaded from environment with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        extra="ignore",
    )

    # Core environment configuration
    ENV: str = Field(default="development")
    DB_URL: str = Field(default="sqlite:///./data/bets.db")
    MODE: str = Field(default="DRY_RUN")
    LOG_LEVEL: str = Field(default="INFO")
    HTTP_TIMEOUT: int = Field(default=10, ge=1, le=120)

    # Risk management defaults
    DEFAULT_KELLY_FRACTION: float = Field(default=0.2, ge=0.0, le=1.0)
    MAX_STAKE_FRAC: float = Field(default=0.05, ge=0.0, le=0.2)
    DAILY_LOSS_LIMIT: float = Field(default=1000.0, gt=0)
    MAX_OPEN_BETS: int = Field(default=10, ge=0, le=500)
    CONSECUTIVE_LOSS_LIMIT: int = Field(default=5, ge=1, le=20)
    MAX_DRAWDOWN_FRACTION: float = Field(default=0.20, ge=0.0, le=0.9)
    RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, le=120)

    # API configuration
    BOOKIE_API_KEY: Optional[str] = Field(default=None)
    BOOKIE_API_BASE_URL: Optional[str] = Field(default=None)
    THEODDS_API_KEY: Optional[str] = Field(default=None)
    THEODDS_API_BASE: str = Field(default="https://api.the-odds-api.com/v4")
    BETFAIR_APP_KEY: Optional[str] = Field(default=None)
    BETFAIR_SESSION_TOKEN: Optional[str] = Field(default=None)
    BETFAIR_API_BASE: str = Field(default="https://api.betfair.com")

    # Alerting / telemetry
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None)
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None)

    PAPER_TRADING_DAYS_REQUIRED: int = Field(default=30, ge=0, le=365)

    @field_validator("ENV")
    @classmethod
    def normalize_env(cls, value: str) -> str:
        """Ensure ENV is stored in lowercase for consistency."""
        return value.strip().lower() if value else value

    @field_validator("MODE")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Constrain MODE to supported values and emit cautionary logs."""
        normalized = value.strip().upper()
        if normalized not in {"DRY_RUN", "LIVE"}:
            raise ValueError("MODE must be DRY_RUN or LIVE")
        if normalized == "LIVE":
            logger.warning("LIVE MODE ENABLED - ensure production safeguards are satisfied")
        return normalized

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate and normalize logging level strings."""
        level = value.strip().upper()
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if level not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(valid_levels)}")
        return level

    def validate_live_mode_requirements(self) -> List[str]:
        """Return missing configuration keys required before enabling LIVE mode."""
        missing: List[str] = []
        for field_name in LIVE_MODE_REQUIRED_FIELDS:
            if not getattr(self, field_name, None):
                missing.append(field_name)
        return missing

    def assert_live_mode_ready(self) -> None:
        """Raise ValueError if LIVE mode requirements are not satisfied."""
        missing = self.validate_live_mode_requirements()
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(
                "Cannot enable LIVE mode without configuration: " + missing_list
            )


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Internal helper to memoize settings instantiation."""
    return Settings()


settings = _load_settings()


__all__ = ["Settings", "settings", "LIVE_MODE_REQUIRED_FIELDS"]
